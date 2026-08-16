from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from pymol_plip.appearance import (
    clear_saved_appearance,
    load_saved_appearance,
    plip_appearance,
    save_appearance,
    validate_appearance,
)
from pymol_plip.cache import ProfileCache, make_cache_key
from pymol_plip.constants import INTERACTION_TYPES
from pymol_plip.exporting import (
    ExportError,
    build_ligand_pdb,
    choose_target,
    clean_state_title,
    parse_states,
)
from pymol_plip.profiles import empty_profile, validate_profile
from pymol_plip.rendering import normalize_pocket_mode


class CoreTests(unittest.TestCase):
    class Settings:
        def __init__(self):
            self.values = {}

        def value(self, key, default=""):
            return self.values.get(key, default)

        def setValue(self, key, value):
            self.values[key] = value

        def remove(self, key):
            self.values.pop(key, None)

    def test_parse_states(self):
        self.assertEqual(parse_states("all", current=3, total=5), [1, 2, 3, 4, 5])
        self.assertEqual(parse_states("current", current=3, total=5), [3])
        self.assertEqual(parse_states("1-3,5", current=1, total=5), [1, 2, 3, 5])
        with self.assertRaises(ExportError):
            parse_states("6", current=1, total=5)

    def test_pocket_mode_aliases(self):
        self.assertEqual(normalize_pocket_mode("current"), "current")
        self.assertEqual(normalize_pocket_mode(1), "current")
        self.assertEqual(normalize_pocket_mode("union"), "all")
        self.assertEqual(normalize_pocket_mode("hidden"), "off")
        self.assertEqual(normalize_pocket_mode(0), "off")
        with self.assertRaises(ValueError):
            normalize_pocket_mode("sometimes")

    def test_appearance_preferences_round_trip_and_restore(self):
        settings = self.Settings()
        styles = plip_appearance()
        styles["hydrogen_bonds"].update(
            color=[1.0, 1.0, 0.0],
            pattern="dashed",
            dash_length=0.15,
            dash_gap=0.50,
        )
        saved = save_appearance(settings, styles)
        self.assertEqual(load_saved_appearance(settings), saved)
        clear_saved_appearance(settings)
        self.assertEqual(load_saved_appearance(settings), plip_appearance())
        invalid = plip_appearance()
        invalid["hydrogen_bonds"]["color"] = [2.0, 0.0, 0.0]
        with self.assertRaises(ValueError):
            validate_appearance(invalid)

    def test_plugin_metadata_uses_qt_citation_instead_of_legacy_prompt(self):
        header = (Path(__file__).resolve().parent.parent / "pymol_plip" / "__init__.py").read_text(
            encoding="utf-8"
        ).split('"""', 1)[0]
        self.assertIn("# Citation:", header)
        self.assertNotIn("Citation-Required", header)

    def test_plip_2d_bridge_uses_active_ligand_without_hard_dependency(self):
        import pymol_plip

        original_controller = pymol_plip._controller
        original_dialog = pymol_plip._dialog
        calls = []
        companion = SimpleNamespace(ligand_review_gui=lambda ligand: calls.append(ligand))
        try:
            pymol_plip._controller = SimpleNamespace(active_ligand_object="poses")
            pymol_plip._dialog = None
            with mock.patch.dict(sys.modules, {"pymol_ligand_review": companion}):
                pymol_plip.plip_2d()
            self.assertEqual(calls, ["poses"])
            with mock.patch.dict(sys.modules, {"pymol_ligand_review": None}):
                with self.assertRaisesRegex(RuntimeError, "not installed"):
                    pymol_plip.plip_2d()
        finally:
            pymol_plip._controller = original_controller
            pymol_plip._dialog = original_dialog

    def test_pymol_sdf_title_cleanup(self):
        self.assertEqual(clean_state_title("ZINC123 none", state=1), "ZINC123")
        self.assertEqual(clean_state_title("none", state=4), "State 4")

    def test_collision_checked_target(self):
        lines = [
            "HETATM    1  C1  LIG Z9999       0.000   0.000   0.000  1.00  0.00           C  "
        ]
        self.assertEqual(choose_target(lines), ("Y", 9999, "LIG"))

    def test_ligand_serialization_keeps_charge_and_bond_order(self):
        atoms = [
            SimpleNamespace(symbol="N", coord=(1, 2, 3), formal_charge=1),
            SimpleNamespace(symbol="O", coord=(2, 2, 3), formal_charge=-1),
        ]
        bonds = [SimpleNamespace(index=(0, 1), order=2)]
        text = build_ligand_pdb(
            SimpleNamespace(atom=atoms, bond=bonds),
            serial_offset=10,
            chain="Z",
            resnum=9999,
        )
        self.assertIn("1+", text)
        self.assertIn("1-", text)
        self.assertIn("CONECT   11   12   12", text)
        self.assertIn("CONECT   12   11   11", text)

    def test_profile_requires_every_interaction_class(self):
        profile = empty_profile(
            title="pose", receptor_hash="r", pose_hash="p", hydrogen_policy="add_missing"
        )
        validate_profile(profile)
        del profile["interactions"][INTERACTION_TYPES[-1]]
        with self.assertRaises(ValueError):
            validate_profile(profile)

    def test_profile_rejects_invalid_geometry(self):
        profile = empty_profile(
            title="pose", receptor_hash="r", pose_hash="p", hydrogen_policy="use_input"
        )
        profile["interactions"]["hydrogen_bonds"].append(
            {"start": [0, 1], "end": [0, 1, 2], "metadata": {}}
        )
        with self.assertRaises(ValueError):
            validate_profile(profile)

    def test_cache_round_trip_and_invalidation(self):
        profile = empty_profile(
            title="pose", receptor_hash="r", pose_hash="p", hydrogen_policy="add_missing"
        )
        engine = {"plip": "3.0.1", "openbabel": "3.2.1", "python": "3.14.0"}
        job = {
            "receptor_hash": "r",
            "pose_hash": "p",
            "hydrogen_policy": "add_missing",
            "target": "LIG:Z:9999",
            "analysis_options": {"filter": "polymer.protein"},
        }
        with tempfile.TemporaryDirectory() as directory:
            cache = ProfileCache(directory)
            key = make_cache_key(job, engine)
            cache.store(key, profile)
            self.assertEqual(cache.load(key), profile)
            changed = dict(job, pose_hash="different")
            self.assertNotEqual(key, make_cache_key(changed, engine))
            changed_filter = dict(job, analysis_options={"filter": "all"})
            self.assertNotEqual(key, make_cache_key(changed_filter, engine))
            changed_engine = dict(engine, openbabel="3.2.2")
            self.assertNotEqual(key, make_cache_key(job, changed_engine))

            path = cache.path_for(key)
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                envelope = json.load(handle)
            envelope["key"] = "tampered"
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                json.dump(envelope, handle)
            self.assertIsNone(cache.load(key))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from pymol import cmd
except ImportError:  # Allows the pure-Python test suite to skip cleanly.
    cmd = None

from pymol_plip.constants import INTERACTION_STYLES, INTERACTION_TYPES
from pymol_plip.profiles import empty_profile

ROOT = Path(__file__).resolve().parent.parent


def profile(title: str, residues=()):
    result = empty_profile(
        title=title,
        receptor_hash="r",
        pose_hash=title,
        hydrogen_policy="add_missing",
    )
    result["residues"] = list(residues)
    return result


@unittest.skipIf(cmd is None, "PyMOL is not installed in this Python")
class RenderingTests(unittest.TestCase):
    def setUp(self):
        cmd.reinitialize()

    def test_every_measurement_has_explicit_empty_states(self):
        from pymol_plip.rendering import render_profiles

        first = profile("one")
        first["interactions"]["hydrogen_bonds"].append(
            {
                "start": [0.0, 0.0, 0.0],
                "end": [2.0, 0.0, 0.0],
                "residue": None,
                "metadata": {},
            }
        )
        run = render_profiles(cmd, ligand_object="test", profiles={1: first}, total_states=5)
        for name in INTERACTION_TYPES:
            object_name = run.object_names[name]
            self.assertEqual(cmd.get_type(object_name), "object:measurement")
            self.assertEqual(cmd.count_states(object_name), 5)
            for actual, expected in zip(
                cmd.get_color_tuple(cmd.get("dash_color", object_name)),
                INTERACTION_STYLES[name]["color"],
            ):
                self.assertAlmostEqual(actual, expected, places=5)
        self.assertNotIn(
            run.object_names["hydrophobic_contacts"],
            cmd.get_names("all", enabled_only=1),
        )

    def test_dash_radius_inherits_global_setting(self):
        from pymol_plip.rendering import render_profiles

        cmd.set("dash_radius", 0.04)
        cmd.pseudoatom("user_a", pos=(0, 0, 0))
        cmd.pseudoatom("user_b", pos=(1, 0, 0))
        cmd.distance("user_measurement", "user_a", "user_b", label=0)
        run = render_profiles(cmd, ligand_object="test", profiles={}, total_states=2)

        self.assertAlmostEqual(float(cmd.get("dash_radius")), 0.04)
        plugin_measurement = run.object_names["hydrogen_bonds"]
        cmd.set("dash_radius", 0.09)
        self.assertAlmostEqual(float(cmd.get("dash_radius", plugin_measurement)), 0.09)
        self.assertAlmostEqual(float(cmd.get("dash_radius", "user_measurement")), 0.09)

    def test_custom_appearance_persists_in_pse(self):
        from pymol_plip.appearance import apply_appearance, plip_appearance
        from pymol_plip.rendering import render_profiles

        run = render_profiles(cmd, ligand_object="test", profiles={}, total_states=2)
        styles = plip_appearance()
        styles["hydrogen_bonds"].update(
            color=[1.0, 1.0, 0.0],
            pattern="dashed",
            dash_length=0.15,
            dash_gap=0.50,
        )
        apply_appearance(cmd, run, styles)
        object_name = run.object_names["hydrogen_bonds"]
        self.assertAlmostEqual(float(cmd.get("dash_gap", object_name)), 0.50)
        self.assertEqual(
            tuple(round(value, 5) for value in cmd.get_color_tuple(cmd.get("dash_color", object_name))),
            (1.0, 1.0, 0.0),
        )
        with tempfile.NamedTemporaryFile(suffix=".pse") as handle:
            cmd.save(handle.name)
            cmd.reinitialize()
            cmd.load(handle.name)
        self.assertAlmostEqual(float(cmd.get("dash_gap", object_name)), 0.50)
        self.assertEqual(
            tuple(round(value, 5) for value in cmd.get_color_tuple(cmd.get("dash_color", object_name))),
            (1.0, 1.0, 0.0),
        )

    def test_pocket_modes_are_state_aligned_and_do_not_touch_receptor(self):
        from pymol_plip.rendering import (
            POCKET_SENTINEL_SEGI,
            render_pockets,
            render_profiles,
            set_pocket_visibility,
        )

        cmd.load(str(ROOT / "fixtures" / "ep4" / "ep4r_rec.crg.pdb"), "receptor")
        cmd.show("sticks", "receptor and chain A and resi 113")
        source_reps = []
        cmd.iterate(
            "receptor and chain A and resi 113",
            "values.append(reps)",
            space={"values": source_reps},
        )
        profiles = {
            1: profile("one", [{"chain": "A", "resi": "113", "resn": "MET"}]),
            2: profile("two", [{"chain": "A", "resi": "76", "resn": "THR"}]),
        }
        run = render_profiles(cmd, ligand_object="test", profiles=profiles, total_states=5)
        render_pockets(
            cmd,
            run=run,
            receptor_selection="receptor",
            receptor_state=1,
            profiles=profiles,
            total_states=5,
            mode="current",
        )
        self.assertEqual(cmd.count_states(run.pocket_name), 5)
        self.assertEqual(cmd.count_states(run.pocket_all_name), 1)
        self.assertEqual(
            self._pocket_residues(run.pocket_name, 1, POCKET_SENTINEL_SEGI),
            {("A", "113", "MET")},
        )
        self.assertEqual(
            self._pocket_residues(run.pocket_name, 2, POCKET_SENTINEL_SEGI),
            {("A", "76", "THR")},
        )
        self.assertEqual(
            self._pocket_residues(run.pocket_name, 5, POCKET_SENTINEL_SEGI),
            set(),
        )

        set_pocket_visibility(cmd, run, "all")
        self.assertEqual(
            self._pocket_residues(run.pocket_all_name, 1, POCKET_SENTINEL_SEGI),
            {("A", "113", "MET"), ("A", "76", "THR")},
        )
        final_reps = []
        cmd.iterate(
            "receptor and chain A and resi 113",
            "values.append(reps)",
            space={"values": final_reps},
        )
        self.assertEqual(final_reps, source_reps)

        set_pocket_visibility(cmd, run, "off")
        enabled = set(cmd.get_names("all", enabled_only=1))
        self.assertNotIn(run.pocket_name, enabled)
        self.assertNotIn(run.pocket_all_name, enabled)
        self.assertIn(run.pocket_name, cmd.get_names("all"))
        self.assertIn(run.pocket_all_name, cmd.get_names("all"))

    def test_overlay_and_pocket_survive_pse_round_trip(self):
        from pymol_plip.rendering import POCKET_SENTINEL_SEGI, render_pockets, render_profiles

        cmd.load(str(ROOT / "fixtures" / "ep4" / "ep4r_rec.crg.pdb"), "receptor")
        profiles = {
            2: profile("two", [{"chain": "A", "resi": "76", "resn": "THR"}]),
        }
        run = render_profiles(cmd, ligand_object="test", profiles=profiles, total_states=3)
        render_pockets(
            cmd,
            run=run,
            receptor_selection="receptor",
            receptor_state=1,
            profiles=profiles,
            total_states=3,
            mode="current",
        )
        with tempfile.NamedTemporaryFile(suffix=".pse") as handle:
            cmd.save(handle.name)
            cmd.reinitialize()
            cmd.load(handle.name)
        for object_name in run.object_names.values():
            self.assertEqual(cmd.count_states(object_name), 3)
        self.assertEqual(cmd.count_states(run.pocket_name), 3)
        self.assertEqual(cmd.count_states(run.pocket_all_name), 1)
        self.assertEqual(
            self._pocket_residues(run.pocket_name, 2, POCKET_SENTINEL_SEGI),
            {("A", "76", "THR")},
        )

    def test_beta_02_pocket_migrates_without_profiles_or_plip(self):
        from pymol_plip.rendering import (
            POCKET_SENTINEL_SEGI,
            ensure_all_pocket,
            render_pockets,
            render_profiles,
        )

        cmd.load(str(ROOT / "fixtures" / "ep4" / "ep4r_rec.crg.pdb"), "receptor")
        profiles = {
            1: profile("one", [{"chain": "A", "resi": "113", "resn": "MET"}]),
            2: profile("two", [{"chain": "A", "resi": "76", "resn": "THR"}]),
        }
        run = render_profiles(cmd, ligand_object="test", profiles=profiles, total_states=3)
        render_pockets(
            cmd,
            run=run,
            receptor_selection="receptor",
            receptor_state=1,
            profiles=profiles,
            total_states=3,
            mode="current",
        )
        cmd.delete(run.pocket_all_name)
        self.assertTrue(
            ensure_all_pocket(
                cmd,
                run=run,
                receptor_selection="receptor",
                receptor_state=1,
            )
        )
        self.assertEqual(
            self._pocket_residues(run.pocket_all_name, 1, POCKET_SENTINEL_SEGI),
            {("A", "113", "MET"), ("A", "76", "THR")},
        )

    @staticmethod
    def _pocket_residues(object_name: str, state: int, sentinel_segi: str):
        return {
            (str(atom.chain), str(atom.resi), str(atom.resn))
            for atom in cmd.get_model(object_name, state).atom
            if str(atom.segi) != sentinel_segi
        }


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from pymol_ligand_review.cache import DepictionCache, depiction_key
from pymol_ligand_review.exporting import ExportError, clean_state_title, export_bundle, ordered_states
from pymol_ligand_review.selection import SelectionStore, identity_key


SDF = """example
  PyMOL          3D

  2  1  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  2  0
M  END
$$$$
"""


class FakeCmd:
    def __init__(self):
        self.state = 2

    def get_object_list(self, _selection):
        return ["poses"]

    def count_states(self, _object):
        return 3

    def get_state(self):
        return self.state

    def get_title(self, _object, state):
        return f" Ligand {state} none"

    def count_atoms(self, _selection, state=0):
        return 2 if state != 3 else 0

    def get_str(self, _format, _selection, state=0):
        return SDF.replace("example", f"Ligand {state}", 1)


def record(state=1, title="CMPD", smiles="CCO"):
    return {
        "state": state,
        "title": title,
        "smiles": smiles,
        "identity_key": identity_key(title, smiles),
        "ligand_object": "poses",
    }


class CoreTests(unittest.TestCase):
    def test_title_cleanup_and_current_first_order(self):
        self.assertEqual(clean_state_title(" ZINC123 none", state=1), "ZINC123")
        self.assertEqual(clean_state_title("none", state=4), "State 4")
        self.assertEqual(ordered_states(3, 5), [3, 1, 2, 4, 5])

    def test_export_bundle_is_immutable_and_records_empty_states(self):
        cmd = FakeCmd()
        bundle = export_bundle(cmd, "poses")
        try:
            import json

            manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual([job["state"] for job in manifest["jobs"]], [2, 1, 3])
            self.assertEqual(manifest["jobs"][0]["title"], "Ligand 2")
            self.assertIn("input_hash", manifest["jobs"][0])
            self.assertIn("empty", manifest["jobs"][2]["error"])
        finally:
            bundle.cleanup()

    def test_export_rejects_multi_object_selection(self):
        cmd = FakeCmd()
        cmd.get_object_list = lambda _selection: ["one", "two"]
        with self.assertRaises(ExportError):
            export_bundle(cmd, "all")

    def test_cache_key_and_atomic_round_trip(self):
        self.assertNotEqual(depiction_key("CCO", "1"), depiction_key("CCN", "1"))
        self.assertNotEqual(depiction_key("CCO", "1"), depiction_key("CCO", "2"))
        with tempfile.TemporaryDirectory() as directory:
            cache = DepictionCache(directory)
            key = depiction_key("CCO", "1")
            path = cache.store(key, b"\x89PNG\r\n\x1a\ncontent")
            self.assertEqual(cache.load(key), path)
            self.assertEqual(cache.stats()[0], 1)
            cache.clear()
            self.assertIsNone(cache.load(key))

    def test_compound_identity_deduplicates_and_tracks_sources(self):
        store = SelectionStore()
        first = record(1)
        second = dict(record(7), ligand_object="other")
        store.register(first)
        store.mark(first)
        store.register(second)
        store.mark(second)
        self.assertEqual(len(store.selected), 1)
        self.assertEqual(
            store.records()[0]["matching_sources"],
            "other:7;poses:1",
        )

    def test_editing_metadata_does_not_change_stable_identity(self):
        store = SelectionStore()
        item = record()
        compound = store.mark(item)
        key = compound.key
        store.update(key, name="Ethanol", identifier="VENDOR,42")
        self.assertIn(key, store.selected)
        self.assertEqual(store.selected[key].name, "Ethanol")
        self.assertEqual(store.selected[key].identifier, "VENDOR,42")

    def test_csv_export_quotes_and_preserves_required_columns(self):
        store = SelectionStore()
        item = record(title="Vendor, compound")
        store.mark(item, name="Line one\nLine two", identifier="ID,7")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "selected.csv"
            self.assertEqual(store.export_csv(path), 1)
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["name"], "Line one\nLine two")
        self.assertEqual(rows[0]["identifier"], "ID,7")
        self.assertEqual(rows[0]["smiles"], "CCO")


if __name__ == "__main__":
    unittest.main()


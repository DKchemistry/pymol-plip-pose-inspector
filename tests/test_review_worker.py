from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from rdkit import Chem, rdBase
except ImportError:
    Chem = None
    rdBase = None

from pymol_plip.ligand_review.cache import DepictionCache
from pymol_plip.ligand_review.worker import depict_job


SDF = """charged alcohol
  RDKit          3D

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.4000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
M  CHG  1   3  -1
M  END
$$$$
"""


@unittest.skipIf(Chem is None, "RDKit is not installed in this Python")
class WorkerTests(unittest.TestCase):
    def test_depiction_smiles_png_and_cache_hit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdf = root / "state.sdf"
            sdf.write_text(SDF, encoding="utf-8")
            job = {
                "state": 1,
                "title": "CMPD",
                "ligand_object": "poses",
                "sdf_path": str(sdf),
                "input_hash": "abc",
            }
            cache = DepictionCache(root / "cache")
            first = depict_job(job, cache, rdBase.rdkitVersion)
            second = depict_job(job, cache, rdBase.rdkitVersion)
            self.assertEqual(first["smiles"], "CC[O-]")
            self.assertTrue(Path(first["image_path"]).is_file())
            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])

    def test_invalid_structure_fails_without_cache_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdf = root / "bad.sdf"
            sdf.write_text("not a molecule", encoding="utf-8")
            with self.assertRaises(ValueError):
                depict_job(
                    {
                        "state": 2,
                        "title": "bad",
                        "ligand_object": "poses",
                        "sdf_path": str(sdf),
                    },
                    DepictionCache(root / "cache"),
                    rdBase.rdkitVersion,
                )

    def test_stereochemistry_and_explicit_hydrogens_survive_normalization(self):
        from rdkit.Chem import rdDepictor

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = Chem.AddHs(Chem.MolFromSmiles("N[C@@H](C)C(=O)O"))
            rdDepictor.Compute2DCoords(original)
            sdf = root / "stereo.sdf"
            sdf.write_text(Chem.MolToMolBlock(original) + "\n$$$$\n", encoding="utf-8")
            result = depict_job(
                {
                    "state": 1,
                    "title": "L-alanine",
                    "ligand_object": "poses",
                    "sdf_path": str(sdf),
                },
                DepictionCache(root / "cache"),
                rdBase.rdkitVersion,
            )
            expected = Chem.MolToSmiles(
                Chem.RemoveHs(original), canonical=True, isomericSmiles=True
            )
            self.assertEqual(result["smiles"], expected)
            self.assertIn("@", result["smiles"])


if __name__ == "__main__":
    unittest.main()

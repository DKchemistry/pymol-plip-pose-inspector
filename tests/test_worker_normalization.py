from __future__ import annotations

import unittest
from types import SimpleNamespace as NS

from pymol_plip.profiles import empty_profile
from pymol_plip.worker import normalize_interactions, profile_for_job


def atom(x, y, z):
    return NS(coords=(x, y, z))


class WorkerNormalizationTests(unittest.TestCase):
    def test_cache_hit_uses_current_pose_title(self):
        cached = empty_profile(
            title="first duplicate",
            receptor_hash="r",
            pose_hash="p",
            hydrogen_policy="add_missing",
        )
        current = profile_for_job(cached, {"title": "second duplicate"})
        self.assertEqual(current["title"], "second duplicate")
        self.assertEqual(cached["title"], "first duplicate")

    def test_all_supported_classes_are_present(self):
        residue = {"reschain": "A", "restype": "TYR", "resnr": 10}
        complex_ = NS(
            hydrophobic_contacts=[NS(**residue, bsatom=atom(0, 0, 0), ligatom=atom(1, 0, 0), distance=1)],
            hbonds_pdon=[NS(**residue, protisdon=True, a=atom(1, 0, 0), d=atom(0, 0, 0), distance_ad=1, angle=170)],
            hbonds_ldon=[],
            halogen_bonds=[NS(**residue, acc=NS(o=atom(0, 0, 0)), don=NS(x=atom(1, 0, 0)), distance=1, don_angle=170, acc_angle=120)],
            water_bridges=[NS(**residue, protisdon=False, a=atom(0, 0, 0), d=atom(2, 0, 0), water=atom(1, 0, 0))],
            saltbridge_lneg=[NS(**residue, protispos=True, positive=NS(center=atom(0, 0, 0)), negative=NS(center=atom(1, 0, 0)), distance=1)],
            saltbridge_pneg=[],
            pistacking=[
                NS(**residue, type="P", proteinring=NS(center=atom(0, 0, 0)), ligandring=NS(center=atom(1, 0, 0)), distance=1, angle=0, offset=0),
                NS(**residue, type="T", proteinring=NS(center=atom(0, 0, 0)), ligandring=NS(center=atom(1, 0, 0)), distance=1, angle=90, offset=0),
            ],
            pication_laro=[NS(**residue, protcharged=True, charge=NS(center=atom(0, 0, 0)), ring=NS(center=atom(1, 0, 0)), distance=1, offset=0)],
            pication_paro=[],
            metal_complexes=[NS(**residue, metal=atom(0, 0, 0), target=NS(atom=atom(1, 0, 0)), distance=1, location="protein", geometry="tetrahedral", metal_type="ZN")],
        )
        interactions, residues = normalize_interactions(complex_)
        self.assertEqual(len(interactions["water_bridges"]), 2)
        self.assertTrue(all(interactions[name] for name in interactions))
        self.assertEqual(residues, [{"chain": "A", "resi": "10", "resn": "TYR"}])


if __name__ == "__main__":
    unittest.main()

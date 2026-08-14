from __future__ import annotations

import unittest

try:
    from pymol import cmd
except ImportError:  # Allows the pure-Python test suite to skip cleanly.
    cmd = None

from pymol_plip.constants import INTERACTION_TYPES
from pymol_plip.profiles import empty_profile


@unittest.skipIf(cmd is None, "PyMOL is not installed in this Python")
class RenderingTests(unittest.TestCase):
    def setUp(self):
        cmd.reinitialize()

    def test_every_cgo_has_explicit_empty_states(self):
        from pymol_plip.rendering import render_profiles

        profile = empty_profile(
            title="one", receptor_hash="r", pose_hash="p", hydrogen_policy="add_missing"
        )
        profile["interactions"]["hydrogen_bonds"].append(
            {
                "start": [0.0, 0.0, 0.0],
                "end": [2.0, 0.0, 0.0],
                "residue": None,
                "metadata": {},
            }
        )
        run = render_profiles(cmd, ligand_object="test", profiles={1: profile}, total_states=5)
        for name in INTERACTION_TYPES:
            self.assertEqual(cmd.count_states(run.object_names[name]), 5)
        self.assertNotIn(
            run.object_names["hydrophobic_contacts"],
            cmd.get_names("all", enabled_only=1),
        )

    def test_overlay_survives_pse_round_trip(self):
        from pymol_plip.rendering import render_profiles

        run = render_profiles(cmd, ligand_object="test", profiles={}, total_states=3)
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pse") as handle:
            cmd.save(handle.name)
            cmd.reinitialize()
            cmd.load(handle.name)
        for object_name in run.object_names.values():
            self.assertEqual(cmd.count_states(object_name), 3)


if __name__ == "__main__":
    unittest.main()

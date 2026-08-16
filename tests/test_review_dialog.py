from __future__ import annotations

import unittest

try:
    from pymol import cmd
    from pymol.Qt import QtWidgets
except ImportError:
    cmd = None
    QtWidgets = None


@unittest.skipIf(cmd is None, "PyMOL is not installed in this Python")
class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from pymol_plip.ligand_review.controller import LigandReviewController
        from pymol_plip.ligand_review.dialog import LigandReviewDialog

        cmd.reinitialize()
        cmd.pseudoatom("poses", elem="C", resn="LIG")
        self.controller = LigandReviewController(cmd)
        self.dialog = LigandReviewDialog(self.controller)

    def tearDown(self):
        self.controller.state_timer.stop()
        self.dialog.hide()
        self.dialog.deleteLater()
        self.controller.deleteLater()
        self.app.processEvents()

    def test_geometry_controls_and_read_only_smiles(self):
        self.dialog.show()
        self.app.processEvents()
        self.assertGreaterEqual(self.dialog.width(), 700)
        self.assertGreaterEqual(self.dialog.image.width(), 400)
        self.assertTrue(self.dialog.smiles.isReadOnly())
        self.assertEqual(self.dialog.mark_button.text(), "Mark Compound")
        self.assertIn("Selected Compounds", self.dialog.review_button.text())

    def test_plugin_owned_pockets_are_not_ligand_candidates(self):
        cmd.pseudoatom("PLIP_Pose_Inspector_poses_Pocket", elem="C")
        names = [item["name"] for item in self.controller.molecular_objects()]
        self.assertIn("poses", names)
        self.assertNotIn("PLIP_Pose_Inspector_poses_Pocket", names)


if __name__ == "__main__":
    unittest.main()


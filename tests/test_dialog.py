from __future__ import annotations

import unittest

try:
    from pymol import cmd
    from pymol.Qt import QtWidgets
except ImportError:  # Allows the pure-Python test suite to skip cleanly.
    cmd = None
    QtWidgets = None


@unittest.skipIf(cmd is None, "PyMOL is not installed in this Python")
class DialogGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from pymol_plip.controller import PoseInspectorController
        from pymol_plip.dialog import PoseInspectorDialog

        cmd.reinitialize()
        cmd.pseudoatom("receptor", resn="ALA", resi="1", chain="A", elem="C")
        self.controller = PoseInspectorController(cmd)
        self.dialog = PoseInspectorDialog(self.controller)

    def tearDown(self):
        self.controller.state_timer.stop()
        self.dialog.hide()
        self.dialog.deleteLater()
        self.controller.deleteLater()
        self.app.processEvents()

    def test_status_rows_are_separate_read_only_fields(self):
        self.dialog.current_pose.setText("2/118: a deliberately long docking pose title")
        self.dialog.chemistry_status.setText(
            "Hydrogen policy: PLIP adds missing polar hydrogens; 20 diagnostic messages"
        )
        self.dialog.show()
        self.app.processEvents()

        current = self.dialog.current_pose.geometry()
        profile = self.dialog.chemistry_status.geometry()
        self.assertLess(current.bottom(), profile.top())
        self.assertEqual(current.height(), profile.height())
        self.assertTrue(self.dialog.current_pose.isReadOnly())
        self.assertTrue(self.dialog.chemistry_status.isReadOnly())
        self.assertGreaterEqual(self.dialog.width(), 720)

    def test_labels_tooltips_pocket_modes_and_show_rescan(self):
        self.assertEqual(self.dialog.analyze_current.text(), "Analyze Current Only")
        self.assertEqual(self.dialog.refresh_button.text(), "Refresh Object Lists")
        self.assertIn("loaded, deleted, or renamed", self.dialog.refresh_button.toolTip())
        self.assertEqual(
            [self.dialog.pocket.itemData(index) for index in range(self.dialog.pocket.count())],
            ["current", "all", "off"],
        )

        cmd.pseudoatom("new_ligand", resn="LIG", resi="1", elem="C")
        self.dialog.show()
        self.app.processEvents()
        items = {
            self.dialog.ligand.itemText(index)
            for index in range(self.dialog.ligand.count())
        }
        self.assertIn("new_ligand", items)


if __name__ == "__main__":
    unittest.main()

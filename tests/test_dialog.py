from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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
        with tempfile.TemporaryDirectory() as directory:
            screenshot = Path(directory) / "dialog.png"
            self.assertTrue(self.dialog.grab().save(str(screenshot)))
            self.assertGreater(screenshot.stat().st_size, 1_000)

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

    def test_diagnostics_and_citation_are_accessible(self):
        from pymol_plip.profiles import empty_profile

        profile = empty_profile(
            title="warning pose",
            receptor_hash="r",
            pose_hash="p",
            hydrogen_policy="use_input",
        )
        profile["warnings"] = ["A diagnostic from PLIP"]
        self.controller.profiles = {1: profile}
        self.controller.total_states = 1
        self.dialog._profiles_changed()
        self.assertTrue(self.dialog.diagnostics_button.isEnabled())
        self.dialog._show_diagnostics()
        self.assertIn(
            "A diagnostic from PLIP",
            self.dialog._diagnostics_dialog.text.toPlainText(),
        )
        self.assertIn("selected automatically", self.dialog._diagnostics_dialog.summary.text())

        key = "citation_dialog_shown"
        original = self.controller.settings.value(key, None)
        self.controller.settings.remove(key)
        try:
            self.dialog.show_citation_once()
            self.app.processEvents()
            self.assertTrue(self.dialog._citation_dialog.isVisible())
            self.assertIn("gkab294", self.dialog._citation_dialog.text.toPlainText())
            self.dialog._citation_dialog.hide()
            self.dialog.show_citation_once()
            self.app.processEvents()
            self.assertFalse(self.dialog._citation_dialog.isVisible())
        finally:
            if original is None:
                self.controller.settings.remove(key)
            else:
                self.controller.settings.setValue(key, original)

    def test_saved_session_attachment_uses_unknown_counts(self):
        from pymol_plip.profiles import empty_profile
        from pymol_plip.rendering import render_pockets, render_profiles

        cmd.pseudoatom("poses", resn="LIG", resi="1", elem="C")
        profile = empty_profile(
            title="pose",
            receptor_hash="r",
            pose_hash="p",
            hydrogen_policy="add_missing",
        )
        run = render_profiles(cmd, ligand_object="poses", profiles={1: profile}, total_states=1)
        render_pockets(
            cmd,
            run=run,
            receptor_selection="receptor",
            receptor_state=1,
            profiles={1: profile},
            total_states=1,
            mode="current",
        )
        cmd.delete(run.pocket_all_name)  # Simulate a Beta 0.2 saved session.
        self.assertTrue(self.controller.attach_existing_run("poses", "receptor"))
        self.assertIn(run.pocket_all_name, cmd.get_names("all"))
        self.dialog._profiles_changed()
        self.assertTrue(self.controller.session_attached)
        self.assertTrue(all(label.text() == "— / —" for label in self.dialog.type_counts.values()))
        self.assertIn("profile details unavailable", self.dialog.chemistry_status.text())
        self.assertFalse(self.dialog.diagnostics_button.isEnabled())

    def test_appearance_dialog_exposes_every_class_and_scopes(self):
        from pymol_plip.dialog import AppearanceDialog

        appearance = AppearanceDialog(self.controller, self.dialog)
        self.assertEqual(set(appearance.rows), set(self.dialog.type_checks))
        self.assertEqual(appearance.rows["hydrogen_bonds"]["pattern"].count(), 4)
        button_texts = {
            button.text()
            for button in appearance.findChildren(QtWidgets.QPushButton)
        }
        self.assertIn("Apply to Current Overlay", button_texts)
        self.assertIn("Apply && Save as My Defaults", button_texts)
        self.assertIn("Restore PLIP Defaults", button_texts)
        appearance.close()

    def test_2d_review_launcher_is_visible(self):
        self.assertEqual(self.dialog.review_2d_button.text(), "2D Review…")
        self.assertIn("Ligand Review Panel", self.dialog.review_2d_button.toolTip())

    def test_multiple_saved_runs_require_an_explicit_ligand(self):
        from pymol_plip.profiles import empty_profile
        from pymol_plip.rendering import render_pockets, render_profiles

        profile = empty_profile(
            title="pose",
            receptor_hash="r",
            pose_hash="p",
            hydrogen_policy="add_missing",
        )
        for ligand in ("poses_one", "poses_two"):
            cmd.pseudoatom(ligand, resn="LIG", resi="1", elem="C")
            run = render_profiles(cmd, ligand_object=ligand, profiles={1: profile}, total_states=1)
            render_pockets(
                cmd,
                run=run,
                receptor_selection="receptor",
                receptor_state=1,
                profiles={1: profile},
                total_states=1,
                mode="current",
            )
        self.controller.run = None
        with self.assertRaises(ValueError):
            self.controller.set_pocket_mode("off")
        self.controller.set_pocket_mode("off", "poses_one")
        self.assertEqual(self.controller.run.run_name, "poses_one")


if __name__ == "__main__":
    unittest.main()

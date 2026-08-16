"""Long-lived application container shared by every plugin command and window."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from pymol.Qt import QtCore, QtWidgets

from .controller import PoseInspectorController
from .ligand_review.controller import LigandReviewController
from .runtime import WorkerRuntime, unified_settings
from .workspace import WorkspaceSession


class PoseInspectorApplication:
    def __init__(self, cmd: Any):
        self.cmd = cmd
        self.settings = unified_settings()
        self.runtime = WorkerRuntime(self.settings)
        self.session = WorkspaceSession(cmd)
        self.plip_controller = PoseInspectorController(
            cmd, session=self.session, runtime=self.runtime
        )
        self.review_controller = LigandReviewController(
            cmd, session=self.session, runtime=self.runtime
        )
        self.plip_controller.application = self
        self.review_controller.application = self
        self.main_dialog = None
        self.review_dialog = None
        self.settings_dialog = None
        self._legacy_notice = None

    def show_main(self):
        from .dialog import PoseInspectorDialog

        if self.main_dialog is None:
            self.main_dialog = PoseInspectorDialog(self.plip_controller)
        self.main_dialog.show()
        self.main_dialog.raise_()
        self.main_dialog.activateWindow()
        QtCore.QTimer.singleShot(0, self.main_dialog.show_citation_once)
        QtCore.QTimer.singleShot(0, self.show_legacy_companion_notice_once)
        return self.main_dialog

    def show_review(self, ligand: str = ""):
        from .ligand_review.dialog import LigandReviewDialog

        if self.review_dialog is None:
            self.review_dialog = LigandReviewDialog(self.review_controller)
        self.review_dialog.show()
        self.review_dialog.raise_()
        self.review_dialog.activateWindow()
        ligand = str(ligand).strip() or self.session.active_selection
        if ligand:
            self.review_dialog.attach_ligand(ligand)
        return self.review_dialog

    def show_settings(self, parent: QtWidgets.QWidget | None = None):
        from .dialog import SettingsDialog

        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self.plip_controller, parent)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()
        return self.settings_dialog

    def show_legacy_companion_notice_once(self) -> None:
        key = "legacy_companion_notice_shown"
        if bool(self.settings.value(key, False, type=bool)):
            return
        try:
            spec = importlib.util.find_spec("pymol_ligand_review")
            origin = Path(spec.origin).resolve() if spec and spec.origin else None
            bundled = Path(__file__).resolve().parent.parent / "pymol_ligand_review.py"
            if origin is None or origin == bundled.resolve():
                return
        except Exception:
            return
        self.settings.setValue(key, True)
        notice = QtWidgets.QMessageBox(
            QtWidgets.QMessageBox.Information,
            "Legacy Ligand Review Panel detected",
            "The standalone Ligand Review Panel is now built into PyMOL Pose Inspector. "
            "You may remove the old plugin from Plugin Manager to avoid a duplicate menu entry. "
            "The integrated 2D Review action is already available.",
            QtWidgets.QMessageBox.Ok,
        )
        notice.setModal(False)
        notice.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        notice.destroyed.connect(lambda: setattr(self, "_legacy_notice", None))
        self._legacy_notice = notice
        notice.show()


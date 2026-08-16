#!/usr/bin/env python3
"""Render deterministic offscreen beta UI screenshots."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from pymol import cmd
from pymol.Qt import QtWidgets

from pymol_ligand_review.controller import LigandReviewController
from pymol_ligand_review.dialog import LigandReviewDialog


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--worker-python", type=Path, required=True)
    args = parser.parse_args()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    cmd.reinitialize()
    cmd.load(str(args.session))
    controller = LigandReviewController(cmd)
    controller.set_worker_python(str(args.worker_python))
    dialog = LigandReviewDialog(controller)
    dialog.attach_ligand("EP4_poses")
    deadline = time.perf_counter() + 60
    while controller.is_running and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)
    if controller.is_running or len(controller.records) != 5:
        raise RuntimeError(f"Could not prepare screenshot: {controller.failures}")
    cmd.frame(2)
    controller._poll_state()
    dialog._display_current(force=True)
    controller.mark_current(enabled="on", name="ZINC000263294111", identifier="ZINC000263294111")
    cmd.frame(4)
    controller._poll_state()
    controller.mark_current(enabled="on", name="EP4 candidate", identifier="ZINC000497198662")
    cmd.frame(2)
    controller._poll_state()
    dialog._display_current(force=True)
    dialog.status.setText("Ready: 5/5 depictions; synchronized with the PyMOL state")
    dialog.show()
    app.processEvents()
    if not dialog.grab().save(str(ROOT / "docs" / "Ligand_Review_Panel.png")):
        raise RuntimeError("Could not save main dialog screenshot")
    dialog._show_selected()
    app.processEvents()
    if not dialog._selected_dialog.grab().save(
        str(ROOT / "docs" / "Selected_Compounds.png")
    ):
        raise RuntimeError("Could not save selected compounds screenshot")
    controller.state_timer.stop()
    dialog.hide()


if __name__ == "__main__":
    main()


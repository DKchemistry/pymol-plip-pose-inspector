#!/usr/bin/env python3
"""Regenerate molecular and unified offscreen UI screenshots."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pymol import cmd
from pymol.Qt import QtWidgets

from pymol_plip.application import PoseInspectorApplication
from pymol_plip.dialog import PoseInspectorDialog
from pymol_plip.ligand_review.dialog import LigandReviewDialog
from pymol_plip.profiles import empty_profile


def demo_profiles():
    counts = {
        1: {"hydrogen_bonds": 2, "hydrophobic_contacts": 5, "salt_bridges": 1},
        2: {"hydrogen_bonds": 2, "hydrophobic_contacts": 4, "halogen_bonds": 1, "salt_bridges": 1},
        3: {"hydrogen_bonds": 5, "hydrophobic_contacts": 4},
        4: {"hydrogen_bonds": 5, "hydrophobic_contacts": 5},
        5: {"hydrogen_bonds": 4, "hydrophobic_contacts": 6, "halogen_bonds": 1, "salt_bridges": 1},
    }
    profiles = {}
    for state, state_counts in counts.items():
        profile = empty_profile(
            title="ZINC000263294111" if state == 2 else f"Demo pose {state}",
            receptor_hash="demo",
            pose_hash=f"demo-{state}",
            hydrogen_policy="add_missing",
        )
        edge = {"start": [0, 0, 0], "end": [1, 0, 0], "metadata": {}}
        for interaction_type, count in state_counts.items():
            profile["interactions"][interaction_type] = [dict(edge) for _ in range(count)]
        profiles[state] = profile
    profiles[2]["warnings"] = ["Demo profile status"]
    return profiles


def main() -> None:
    session = ROOT / "demos/EP4_first5_beta.pse"
    cmd.reinitialize()
    cmd.load(str(session))
    cmd.set("state", 2)
    cmd.refresh()
    cmd.png(
        str(ROOT / "docs/EP4_first5_beta.png"),
        width=1600,
        height=1000,
        dpi=150,
        ray=1,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    application = PoseInspectorApplication(cmd)
    application.runtime.set_worker_python(
        str(Path.home() / "miniconda3/envs/pymol-pose-inspector/bin/python")
    )
    application.session.set_ligand("EP4_poses")
    app.processEvents()
    deadline = time.perf_counter() + 90
    while application.review_controller.is_running and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)
    if application.review_controller.is_running or len(application.review_controller.records) != 5:
        raise RuntimeError(
            f"Could not prepare RDKit screenshots: {application.review_controller.failures}"
        )

    controller = application.plip_controller
    controller.active_receptor_selection = (
        "(EP4_receptor) and (polymer.protein or solvent or inorganic)"
    )
    controller.active_receptor_state = 1
    controller.active_ligand_object = "EP4_poses"
    controller.total_states = 5
    controller.profiles = demo_profiles()
    controller.session_attached = False
    controller.engine = {
        "plip": "3.0.1",
        "openbabel": "3.2.1",
        "rdkit": "2025.03.5",
        "python": "3.12.13",
    }

    main_dialog = PoseInspectorDialog(controller)
    application.main_dialog = main_dialog
    controller.profiles = demo_profiles()
    controller.failures = {}
    controller.session_attached = False
    controller.engine = {
        "plip": "3.0.1",
        "openbabel": "3.2.1",
        "rdkit": "2025.03.5",
        "python": "3.12.13",
    }
    main_dialog.receptor.setEditText("EP4_receptor")
    main_dialog.ligand.setEditText("EP4_poses")
    main_dialog._profiles_changed()
    main_dialog.status.setText("Ready: 5/5 poses analyzed; synchronized 2D depictions cached")
    main_dialog.show()
    app.processEvents()
    main_dialog.grab().save(str(ROOT / "docs/PyMOL_Pose_Inspector_GUI.png"))
    main_dialog._show_appearance()
    app.processEvents()
    main_dialog._appearance_dialog.grab().save(
        str(ROOT / "docs/PLIP_Interaction_Appearance.png")
    )
    main_dialog._appearance_dialog.hide()
    application.show_settings(main_dialog)
    application.settings_dialog._test()
    app.processEvents()
    application.settings_dialog.grab().save(
        str(ROOT / "docs/PyMOL_Pose_Inspector_Settings.png")
    )
    application.settings_dialog.hide()

    review = application.review_controller
    review_dialog = LigandReviewDialog(review)
    application.review_dialog = review_dialog
    cmd.frame(2)
    application.session._poll_state()
    review._poll_state()
    review.mark_current(
        enabled="on", name="ZINC000263294111", identifier="ZINC000263294111"
    )
    cmd.frame(4)
    application.session._poll_state()
    review._poll_state()
    review.mark_current(
        enabled="on", name="EP4 candidate", identifier="ZINC000497198662"
    )
    cmd.frame(2)
    application.session._poll_state()
    review._poll_state()
    review_dialog._display_current(force=True)
    review_dialog._records_changed()
    review_dialog.status.setText(
        "Ready: 5/5 depictions; synchronized with the PyMOL state"
    )
    review_dialog.show()
    app.processEvents()
    review_dialog.grab().save(str(ROOT / "docs/Ligand_Review_Panel.png"))
    review_dialog._show_selected()
    app.processEvents()
    review_dialog._selected_dialog.grab().save(
        str(ROOT / "docs/Selected_Compounds.png")
    )
    review_dialog._selected_dialog.hide()
    review_dialog.hide()
    main_dialog.hide()
    application.session.state_timer.stop()


if __name__ == "__main__":
    main()

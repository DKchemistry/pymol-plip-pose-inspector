#!/usr/bin/env python3
"""Regenerate the documented molecular and offscreen dialog screenshots."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pymol import cmd
from pymol.Qt import QtWidgets

from pymol_plip.controller import PoseInspectorController
from pymol_plip.dialog import PoseInspectorDialog
from pymol_plip.profiles import empty_profile


def main() -> None:
    session = ROOT / "demos" / "EP4_first5_beta.pse"
    cmd.reinitialize()
    cmd.load(str(session))
    cmd.set("state", 2)
    cmd.refresh()
    cmd.png(
        str(ROOT / "docs" / "EP4_first5_beta.png"),
        width=1600,
        height=1000,
        dpi=150,
        ray=1,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    controller = PoseInspectorController(cmd)
    controller.active_receptor_selection = "(EP4_receptor) and (polymer.protein or solvent or inorganic)"
    controller.active_receptor_state = 1
    controller.active_ligand_object = "EP4_poses"
    controller.total_states = 5
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
    controller.profiles = profiles
    controller.engine = {"plip": "3.0.1", "openbabel": "3.2.1", "python": "3.14.6"}

    dialog = PoseInspectorDialog(controller)
    dialog.receptor.setEditText("EP4_receptor")
    dialog.ligand.setEditText("EP4_poses")
    dialog._profiles_changed()
    dialog.status.setText("Ready: 5/5 poses analyzed; 5 cache hits, 0 misses")
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(ROOT / "docs" / "PLIP_Pose_Inspector_GUI.png"))
    controller.state_timer.stop()
    dialog.hide()


if __name__ == "__main__":
    main()

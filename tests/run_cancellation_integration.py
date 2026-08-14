#!/usr/bin/env python3
"""Verify that cancellation leaves the last complete overlay untouched."""

from __future__ import annotations

import copy
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pymol import cmd
from pymol.Qt import QtCore

from pymol_plip.controller import PoseInspectorController


def main() -> int:
    cache_directory = tempfile.TemporaryDirectory(prefix="plip-cancel-cache-")
    os.environ["PYMOL_PLIP_CACHE"] = cache_directory.name
    cmd.reinitialize()
    cmd.load(str(ROOT / "fixtures" / "ep4" / "ep4r_rec.crg.pdb"), "EP4_receptor")
    cmd.load(
        str(ROOT / "fixtures" / "ep4" / "ep4r_matched_poses.sdf"),
        "EP4_poses",
        discrete=1,
    )

    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    controller = PoseInspectorController(cmd)
    controller.set_worker_python(
        str(Path.home() / "miniconda3/envs/pymol-plip-plugin/bin/python")
    )
    phase = {"number": 1, "failed": None}
    baseline = {}

    def failed(message: str) -> None:
        phase["failed"] = message

    def running_changed(running: bool) -> None:
        if running:
            return
        if phase["number"] == 1:
            if len(controller.profiles) != 1 or controller.run is None:
                phase["failed"] = "current-state setup analysis did not render"
                app.exit(2)
                return
            baseline["profiles"] = copy.deepcopy(controller.profiles)
            baseline["objects"] = set(controller.run.owned_names)
            baseline["states"] = {
                name: cmd.count_states(name)
                for name in controller.run.object_names.values()
            }
            phase["number"] = 2
            controller.analyze(
                receptor="EP4_receptor",
                ligand="EP4_poses",
                states="all",
                filtered=True,
            )
            QtCore.QTimer.singleShot(100, controller.cancel)
            return

        if controller.profiles != baseline["profiles"]:
            phase["failed"] = "cancelled run replaced or merged the prior profiles"
            app.exit(3)
            return
        if not baseline["objects"].intersection(cmd.get_names("all")):
            phase["failed"] = "cancelled run removed the prior overlay"
            app.exit(4)
            return
        if any(cmd.count_states(name) != states for name, states in baseline["states"].items()):
            phase["failed"] = "cancelled run changed state alignment"
            app.exit(5)
            return
        app.quit()

    controller.error_occurred.connect(failed)
    controller.running_changed.connect(running_changed)
    QtCore.QTimer.singleShot(120_000, lambda: app.exit(124))
    controller.analyze(
        receptor="EP4_receptor",
        ligand="EP4_poses",
        states="current",
        filtered=True,
    )
    result = app.exec_()
    cache_directory.cleanup()
    if phase["failed"]:
        print(f"FAILED: {phase['failed']}")
        return int(result or 1)
    if result:
        print(f"FAILED: event loop exited with {result}")
        return result
    print("PASS: cancellation preserved the existing 118-state overlay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

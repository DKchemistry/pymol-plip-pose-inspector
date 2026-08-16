#!/usr/bin/env python3
"""Internal CAU/2RH1 comparison against the supplied PLIP 2.4 session."""

from __future__ import annotations

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
    cache_directory = tempfile.TemporaryDirectory(prefix="plip-cau-cache-")
    os.environ["PYMOL_PLIP_CACHE"] = cache_directory.name
    cmd.reinitialize()
    cmd.load(str(ROOT / "fixtures" / "2rh1" / "2RH1_CAU_A_408.pse"))
    cmd.create("CAU_pose", "Ligand_CAU", 1, 1)
    cmd.set_title("CAU_pose", 1, "CAU / 2RH1")
    source_atoms = cmd.count_atoms("CAU_pose")

    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    controller = PoseInspectorController(cmd)
    controller.set_worker_python(
        str(Path.home() / "miniconda3/envs/pymol-pose-inspector/bin/python")
    )
    failure = {"message": None}

    def failed(message: str) -> None:
        failure["message"] = message

    def running_changed(running: bool) -> None:
        if running:
            return
        if failure["message"]:
            app.exit(2)
            return
        if len(controller.profiles) != 1 or controller.failures:
            failure["message"] = "CAU analysis did not produce one successful profile"
            app.exit(3)
            return
        if cmd.count_atoms("CAU_pose") != source_atoms:
            failure["message"] = "CAU source object was modified"
            app.exit(4)
            return
        if any(cmd.count_states(name) != 1 for name in controller.run.object_names.values()):
            failure["message"] = "CAU interaction objects were not state-aligned"
            app.exit(5)
            return
        counts = {
            name: len(edges)
            for name, edges in controller.profiles[1]["interactions"].items()
            if edges
        }
        print(f"PLIP 3.0.1 CAU counts: {counts}")
        app.quit()

    controller.error_occurred.connect(failed)
    controller.running_changed.connect(running_changed)
    QtCore.QTimer.singleShot(120_000, lambda: app.exit(124))
    controller.analyze(
        receptor="2RH1",
        ligand="CAU_pose",
        states="all",
        filtered=True,
    )
    result = app.exec_()
    cache_directory.cleanup()
    if failure["message"]:
        print(f"FAILED: {failure['message']}")
        return int(result or 1)
    if result:
        print(f"FAILED: event loop exited with {result}")
        return result
    print("PASS: CAU/2RH1 internal comparison")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

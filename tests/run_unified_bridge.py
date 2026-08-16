#!/usr/bin/env python3
"""Integration test for concurrent saved PLIP overlays and the 2D reviewer."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pymol import cmd
from pymol.Qt import QtWidgets

import pymol_ligand_review
import pymol_plip


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--worker-python", type=Path, required=True)
    args = parser.parse_args()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    cmd.reinitialize()
    cmd.load(str(args.session))
    reviewer = pymol_ligand_review.get_controller()
    reviewer.set_worker_python(str(args.worker_python))
    plip = pymol_plip.get_controller()
    assert plip.attach_existing_run("EP4_poses", "EP4_receptor")
    dialog = pymol_plip.plip_2d()
    deadline = time.perf_counter() + 60
    while reviewer.is_running and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert not reviewer.is_running
    assert len(reviewer.records) == 5, reviewer.failures
    cmd.frame(2)
    reviewer._poll_state()
    plip._poll_state()
    assert reviewer.current_state() == 2
    assert reviewer.current_record()["title"] == "ZINC000263294111"
    assert plip.current_status()[0] == 2
    measurements = [
        name
        for name in cmd.get_names("all")
        if name.startswith("PLIP_Pose_Inspector_")
        and cmd.get_type(name) == "object:measurement"
    ]
    assert len(measurements) == 9
    assert all(cmd.count_states(name) == 5 for name in measurements)
    dialog.hide()
    cmd.frame(3)
    reviewer._poll_state()
    assert reviewer.current_state() == 3
    print(
        json.dumps(
            {
                "bridge": "PASS",
                "state": reviewer.current_state(),
                "title": reviewer.current_record()["title"],
                "measurements": len(measurements),
            },
            sort_keys=True,
        )
    )
    reviewer.state_timer.stop()
    plip.state_timer.stop()


if __name__ == "__main__":
    main()

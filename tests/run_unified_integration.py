#!/usr/bin/env python3
"""Run PLIP and RDKit concurrently through the unified application container."""

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

from pymol_plip.application import PoseInspectorApplication


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--states", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    cmd.reinitialize()
    cmd.load(str(ROOT / "fixtures/ep4/ep4r_rec.crg.pdb"), "EP4_receptor")
    ligand_path = (
        ROOT / "fixtures/ep4/ep4r_matched_poses_first5.sdf"
        if args.states == 5
        else ROOT / "fixtures/ep4/ep4r_matched_poses.sdf"
    )
    cmd.load(str(ligand_path), "EP4_poses", discrete=1)
    source_atoms = cmd.count_atoms("EP4_poses")
    application = PoseInspectorApplication(cmd)
    worker = ROOT.parent.parent / "miniconda3/envs/pymol-pose-inspector/bin/python"
    application.runtime.set_worker_python(str(worker))

    application.session.set_ligand("EP4_poses")
    application.plip_controller.analyze(
        receptor="EP4_receptor", ligand="EP4_poses", states="all", filtered=True
    )
    deadline = time.monotonic() + args.timeout
    while (
        application.plip_controller.is_running
        or application.review_controller.is_running
    ) and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()

    assert not application.plip_controller.is_running, "PLIP worker timed out"
    assert not application.review_controller.is_running, "RDKit worker timed out"
    assert len(application.plip_controller.profiles) == args.states, application.plip_controller.failures
    assert len(application.review_controller.records) == args.states, application.review_controller.failures
    assert not application.plip_controller.failures
    assert not application.review_controller.failures
    cmd.frame(min(2, args.states))
    application.session._poll_state()
    application.plip_controller._poll_state()
    application.review_controller._poll_state()
    current = min(2, args.states)
    assert application.review_controller.current_record()["state"] == current
    assert application.plip_controller.current_status()[0] == current
    assert cmd.count_atoms("EP4_poses") == source_atoms
    assert application.plip_controller.state_timer is application.review_controller.state_timer
    print(
        json.dumps(
            {
                "status": "PASS",
                "states": args.states,
                "current": current,
                "title": application.review_controller.current_record()["title"],
                "plip_profiles": len(application.plip_controller.profiles),
                "rdkit_depictions": len(application.review_controller.records),
            },
            sort_keys=True,
        )
    )
    application.session.state_timer.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

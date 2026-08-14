#!/usr/bin/env python3
"""Exercise the real QProcess worker from an installed PyMOL Python."""

from __future__ import annotations

import argparse
import os
import resource
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pymol import cmd
from pymol.Qt import QtCore

from pymol_plip.controller import PoseInspectorController


EXPECTED_COUNTS = {
    1: {"hydrogen_bonds": 2, "hydrophobic_contacts": 5, "salt_bridges": 1},
    2: {
        "hydrogen_bonds": 2,
        "hydrophobic_contacts": 4,
        "halogen_bonds": 1,
        "salt_bridges": 1,
    },
    3: {"hydrogen_bonds": 5, "hydrophobic_contacts": 4},
    4: {"hydrogen_bonds": 5, "hydrophobic_contacts": 5},
    5: {
        "hydrogen_bonds": 4,
        "hydrophobic_contacts": 6,
        "halogen_bonds": 1,
        "salt_bridges": 1,
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--ligands",
        type=Path,
        default=ROOT / "examples" / "ep4r_matched_poses_first5.sdf",
    )
    parser.add_argument("--expected-states", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    cache_directory = tempfile.TemporaryDirectory(prefix="plip-integration-cache-")
    os.environ["PYMOL_PLIP_CACHE"] = cache_directory.name

    cmd.reinitialize()
    cmd.load(str(ROOT / "ep4r_rec.crg.pdb"), "EP4_receptor")
    cmd.load(
        str(args.ligands),
        "EP4_poses",
        discrete=1,
    )
    receptor_atoms = cmd.count_atoms("EP4_receptor")
    ligand_atoms = cmd.count_atoms("EP4_poses")

    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    controller = PoseInspectorController(cmd)
    controller.set_worker_python(
        str(Path.home() / "miniconda3" / "envs" / "pymol-plip-plugin" / "bin" / "python")
    )
    phase = {"number": 1, "cache_hits": 0, "failed": None, "started": time.monotonic()}

    def progress(completed: int, total: int, hits: int, failures: int) -> None:
        phase["cache_hits"] = hits
        print(
            f"phase={phase['number']} progress={completed}/{total} hits={hits} failures={failures}",
            flush=True,
        )

    def error(message: str) -> None:
        phase["failed"] = message

    def finished(running: bool) -> None:
        if running:
            return
        if phase["failed"]:
            app.exit(2)
            return
        if phase["number"] == 1:
            if len(controller.profiles) != args.expected_states or controller.failures:
                phase["failed"] = (
                    f"first pass produced {len(controller.profiles)} profiles and "
                    f"{len(controller.failures)} failures"
                )
                app.exit(3)
                return
            phase["number"] = 2
            phase["cache_hits"] = 0
            phase["cold_seconds"] = time.monotonic() - phase["started"]
            phase["started"] = time.monotonic()
            controller.analyze(
                receptor="EP4_receptor",
                ligand="EP4_poses",
                states="all",
                filtered=True,
            )
            return

        if phase["cache_hits"] != args.expected_states:
            phase["failed"] = f"warm pass had only {phase['cache_hits']} cache hits"
            app.exit(4)
            return
        for object_name in controller.run.object_names.values():
            if cmd.count_states(object_name) != args.expected_states:
                phase["failed"] = f"{object_name} is not state-aligned"
                app.exit(5)
                return

        controller.toggle(types="all", enabled="off")
        enabled = set(cmd.get_names("all", enabled_only=1))
        if any(name in enabled for name in controller.run.object_names.values()):
            phase["failed"] = "master hide did not disable every interaction class"
            app.exit(6)
            return
        controller.toggle(types="hbonds,salt", enabled="on")
        if cmd.count_atoms("EP4_receptor") != receptor_atoms or cmd.count_atoms("EP4_poses") != ligand_atoms:
            phase["failed"] = "source molecular objects changed"
            app.exit(7)
            return

        for state, profile in sorted(controller.profiles.items()):
            counts = {
                name: len(edges)
                for name, edges in profile["interactions"].items()
                if edges
            }
            if args.expected_states == 5:
                print(f"state={state} title={profile['title']} counts={counts}", flush=True)
            if args.expected_states == 5 and counts != EXPECTED_COUNTS[state]:
                phase["failed"] = (
                    f"state {state} interaction counts changed: "
                    f"expected {EXPECTED_COUNTS[state]}, found {counts}"
                )
                app.exit(9)
                return

        controller.toggle(types="all", enabled="on")
        controller.toggle(types="hydrophobic", enabled="off")
        cmd.hide("everything", "all")
        cmd.show("cartoon", "EP4_receptor and polymer.protein")
        cmd.show("sticks", "EP4_poses")
        cmd.show("sticks", controller.run.pocket_name)
        for object_name in controller.run.object_names.values():
            cmd.show("cgo", object_name)
        cmd.color("gray70", "EP4_receptor and elem C")
        cmd.color("cyan", "EP4_poses and elem C")
        cmd.set("cartoon_transparency", 0.45, "EP4_receptor")
        cmd.set("stick_radius", 0.18, controller.run.pocket_name)
        cmd.bg_color("white")
        cmd.orient("EP4_poses")
        cmd.turn("x", 110)
        cmd.zoom(f"EP4_poses or {controller.run.pocket_name}", 4)

        warm_seconds = time.monotonic() - phase["started"]
        max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(
            f"timing cold={phase['cold_seconds']:.2f}s warm={warm_seconds:.2f}s "
            f"max_rss={max_rss}",
            flush=True,
        )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        cmd.save(str(args.output))
        object_names = dict(controller.run.object_names)
        cmd.reinitialize()
        cmd.load(str(args.output))
        if any(cmd.count_states(name) != args.expected_states for name in object_names.values()):
            phase["failed"] = "state alignment did not survive PSE reload"
            app.exit(8)
            return
        app.quit()

    controller.progress_changed.connect(progress)
    controller.error_occurred.connect(error)
    controller.running_changed.connect(finished)
    QtCore.QTimer.singleShot(args.timeout * 1000, lambda: app.exit(124))
    controller.analyze(
        receptor="EP4_receptor",
        ligand="EP4_poses",
        states="all",
        filtered=True,
    )
    result = app.exec_()
    cache_directory.cleanup()
    if phase["failed"]:
        print(f"FAILED: {phase['failed']}", flush=True)
        return int(result or 1)
    if result:
        print(f"FAILED: event loop exited with {result}", flush=True)
        return result
    print(f"PASS: {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

from pymol_plip.constants import INTERACTION_STYLES
from pymol_plip.controller import PoseInspectorController
from pymol_plip.rendering import POCKET_SENTINEL_SEGI


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


def pocket_residues(object_name: str, state: int) -> set[tuple[str, str, str]]:
    return {
        (str(atom.chain), str(atom.resi), str(atom.resn))
        for atom in cmd.get_model(object_name, state).atom
        if str(atom.segi) != POCKET_SENTINEL_SEGI
    }


def profile_residues(profile: dict) -> set[tuple[str, str, str]]:
    return {
        (str(residue["chain"]), str(residue["resi"]), str(residue["resn"]))
        for residue in profile.get("residues", ())
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--ligands",
        type=Path,
        default=ROOT / "fixtures" / "ep4" / "ep4r_matched_poses_first5.sdf",
    )
    parser.add_argument("--expected-states", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    cache_directory = tempfile.TemporaryDirectory(prefix="plip-integration-cache-")
    os.environ["PYMOL_PLIP_CACHE"] = cache_directory.name

    cmd.reinitialize()
    cmd.load(str(ROOT / "fixtures" / "ep4" / "ep4r_rec.crg.pdb"), "EP4_receptor")
    cmd.load(
        str(args.ligands),
        "EP4_poses",
        discrete=1,
    )
    receptor_atoms = cmd.count_atoms("EP4_receptor")
    ligand_atoms = cmd.count_atoms("EP4_poses")
    cmd.set("dash_radius", 0.052)
    original_dash_radius = float(cmd.get("dash_radius"))

    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    controller = PoseInspectorController(cmd)
    controller.set_worker_python(
        str(Path.home() / "miniconda3" / "envs" / "pymol-pose-inspector" / "bin" / "python")
    )
    phase = {"number": 0, "cache_hits": 0, "failed": None, "started": time.monotonic()}

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
        if phase["number"] == 0:
            if set(controller.profiles) != {1} or controller.failures:
                phase["failed"] = "current-only analysis did not produce exactly state 1"
                app.exit(3)
                return
            if any(
                cmd.count_states(name) != args.expected_states
                for name in controller.run.object_names.values()
            ):
                phase["failed"] = "current-only measurements do not include every ligand state"
                app.exit(3)
                return
            if cmd.count_states(controller.run.pocket_name) != args.expected_states:
                phase["failed"] = "current-only pocket does not include every ligand state"
                app.exit(3)
                return
            if args.expected_states > 1 and pocket_residues(controller.run.pocket_name, 2):
                phase["failed"] = "unanalyzed current-only pocket state is not empty"
                app.exit(3)
                return
            phase["number"] = 1
            phase["cache_hits"] = 0
            phase["started"] = time.monotonic()
            controller.analyze(
                receptor="EP4_receptor",
                ligand="EP4_poses",
                states="all",
                filtered=True,
            )
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
            if cmd.get_type(object_name) != "object:measurement":
                phase["failed"] = f"{object_name} is not a native measurement"
                app.exit(5)
                return
        for interaction_type, object_name in controller.run.object_names.items():
            style = INTERACTION_STYLES[interaction_type]
            expected_length = style["dash_length"] if style["dash_length"] > 0 else 0.15
            if abs(float(cmd.get("dash_length", object_name)) - expected_length) > 1e-5:
                phase["failed"] = f"{object_name} has the wrong PLIP dash length"
                app.exit(5)
                return
            if abs(float(cmd.get("dash_gap", object_name)) - style["dash_gap"]) > 1e-5:
                phase["failed"] = f"{object_name} has the wrong PLIP dash gap"
                app.exit(5)
                return
        if abs(float(cmd.get("dash_radius")) - original_dash_radius) > 1e-6:
            phase["failed"] = "normal plugin analysis changed the global dash radius"
            app.exit(5)
            return

        pocket_name = controller.run.pocket_name
        if cmd.count_states(pocket_name) != args.expected_states:
            phase["failed"] = "current-pose pocket is not state-aligned"
            app.exit(5)
            return
        for state in range(1, args.expected_states + 1):
            expected = profile_residues(controller.profiles[state])
            actual = pocket_residues(pocket_name, state)
            if actual != expected:
                phase["failed"] = (
                    f"state {state} pocket differs from profile: expected {expected}, found {actual}"
                )
                app.exit(5)
                return
        if args.expected_states == 5 and ("A", "76", "THR") not in pocket_residues(pocket_name, 2):
            phase["failed"] = "state 2 pocket is missing THR A/76"
            app.exit(5)
            return

        expected_union = set().union(
            *(profile_residues(profile) for profile in controller.profiles.values())
        )
        controller.set_pocket_mode("all")
        if (
            cmd.count_states(controller.run.pocket_all_name) != 1
            or pocket_residues(controller.run.pocket_all_name, 1) != expected_union
        ):
            phase["failed"] = "all-analyzed pocket is not the exact residue union"
            app.exit(5)
            return
        controller.set_pocket_mode("off")
        enabled = set(cmd.get_names("all", enabled_only=1))
        if pocket_name in enabled or controller.run.pocket_all_name in enabled:
            phase["failed"] = "hidden pocket mode did not disable both persistent pockets"
            app.exit(5)
            return
        if pocket_name not in cmd.get_names("all") or controller.run.pocket_all_name not in cmd.get_names("all"):
            phase["failed"] = "hidden pocket mode deleted persistent pocket geometry"
            app.exit(5)
            return
        controller.set_pocket_mode("current")

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
            cmd.show("dashes", object_name)
        cmd.color("gray70", "EP4_receptor and elem C")
        cmd.color("cyan", "EP4_poses and elem C")
        cmd.set("cartoon_transparency", 0.45, "EP4_receptor")
        cmd.set("stick_radius", 0.18, controller.run.pocket_name)
        cmd.set("dash_radius", 0.09)
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
        cmd.set("state", 2)
        cmd.save(str(args.output))
        object_names = dict(controller.run.object_names)
        pocket_name = controller.run.pocket_name
        pocket_all_name = controller.run.pocket_all_name
        cmd.reinitialize()
        cmd.load(str(args.output))
        if any(cmd.count_states(name) != args.expected_states for name in object_names.values()):
            phase["failed"] = "state alignment did not survive PSE reload"
            app.exit(8)
            return
        if cmd.count_states(pocket_name) != args.expected_states:
            phase["failed"] = "pocket state alignment did not survive PSE reload"
            app.exit(8)
            return
        if cmd.count_states(pocket_all_name) != 1:
            phase["failed"] = "union pocket did not survive PSE reload"
            app.exit(8)
            return
        if abs(float(cmd.get("dash_radius")) - 0.09) > 1e-6:
            phase["failed"] = "beta PSE did not retain the 0.09 global dash radius"
            app.exit(8)
            return
        if args.expected_states == 5 and ("A", "76", "THR") not in pocket_residues(pocket_name, 2):
            phase["failed"] = "state 2 THR A/76 pocket did not survive PSE reload"
            app.exit(8)
            return
        attached = PoseInspectorController(cmd)
        if not attached.attach_existing_run("EP4_poses", "EP4_receptor"):
            phase["failed"] = "fresh controller could not attach to saved overlays"
            app.exit(8)
            return
        if attached.process is not None or attached.pocket_mode != "current":
            phase["failed"] = "saved overlay attachment unexpectedly started analysis"
            app.exit(8)
            return
        attached.set_pocket_mode("all")
        if pocket_all_name not in cmd.get_names("all", enabled_only=1):
            phase["failed"] = "attached session could not show union pocket without PLIP"
            app.exit(8)
            return
        attached.set_pocket_mode("off")
        with tempfile.NamedTemporaryFile(suffix=".pse") as hidden:
            cmd.save(hidden.name)
            cmd.reinitialize()
            cmd.load(hidden.name)
        hidden_controller = PoseInspectorController(cmd)
        hidden_controller.attach_existing_run("EP4_poses", "EP4_receptor")
        if hidden_controller.pocket_mode != "off":
            phase["failed"] = "hidden pocket mode did not survive PSE reload"
            app.exit(8)
            return
        hidden_controller.set_pocket_mode("current")
        if pocket_name not in cmd.get_names("all", enabled_only=1):
            phase["failed"] = "hidden saved session could not restore current pocket"
            app.exit(8)
            return
        styles = hidden_controller.current_appearance()
        styles["hydrogen_bonds"].update(
            color=[1.0, 1.0, 0.0],
            pattern="dashed",
            dash_length=0.15,
            dash_gap=0.50,
        )
        hidden_controller.apply_interaction_appearance(styles)
        hydrogen_bonds = object_names["hydrogen_bonds"]
        if abs(float(cmd.get("dash_gap", hydrogen_bonds)) - 0.50) > 1e-6:
            phase["failed"] = "attached-session appearance did not apply"
            app.exit(8)
            return
        with tempfile.NamedTemporaryFile(suffix=".pse") as styled:
            cmd.save(styled.name)
            cmd.reinitialize()
            cmd.load(styled.name)
        styled_controller = PoseInspectorController(cmd)
        styled_controller.attach_existing_run("EP4_poses", "EP4_receptor")
        styled_hbond = styled_controller.current_appearance()["hydrogen_bonds"]
        if styled_hbond["pattern"] != "dashed" or any(
            abs(actual - expected) > 1e-5
            for actual, expected in zip(styled_hbond["color"], (1.0, 1.0, 0.0))
        ):
            phase["failed"] = "custom appearance did not survive PSE reload"
            app.exit(8)
            return
        attached.state_timer.stop()
        hidden_controller.state_timer.stop()
        styled_controller.state_timer.stop()
        app.quit()

    controller.progress_changed.connect(progress)
    controller.error_occurred.connect(error)
    controller.running_changed.connect(finished)
    QtCore.QTimer.singleShot(args.timeout * 1000, lambda: app.exit(124))
    controller.analyze(
        receptor="EP4_receptor",
        ligand="EP4_poses",
        states="current",
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

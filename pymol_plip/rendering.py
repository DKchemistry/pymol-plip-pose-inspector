"""State-aligned native PyMOL rendering for PLIP profiles."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .constants import INTERACTION_LABELS, INTERACTION_STYLES, INTERACTION_TYPES

POCKET_MODES = ("current", "all", "off")
POCKET_SENTINEL_SEGI = "PPID"


def safe_name(value: str, *, fallback: str = "poses") -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not value:
        value = fallback
    if value[0].isdigit():
        value = "x_" + value
    return value[:80]


@dataclass
class OverlayRun:
    run_name: str
    top_group: str
    interactions_group: str
    structures_group: str
    pocket_name: str
    pocket_all_name: str
    object_names: dict[str, str] = field(default_factory=dict)
    group_names: list[str] = field(default_factory=list)

    @property
    def owned_names(self) -> list[str]:
        return (
            list(self.object_names.values())
            + [self.pocket_name, self.pocket_all_name]
            + self.group_names
        )


def make_run(ligand_object: str) -> OverlayRun:
    slug = safe_name(ligand_object)
    top = f"PLIP_Pose_Inspector_{slug}"
    interactions = f"{top}.Interactions"
    structures = f"{top}.Structures"
    return OverlayRun(
        run_name=slug,
        top_group=top,
        interactions_group=interactions,
        structures_group=structures,
        pocket_name=f"{top}_Pocket",
        pocket_all_name=f"{top}_Pocket_All",
        object_names={
            name: f"{top}_{safe_name(INTERACTION_LABELS[name])}"
            for name in INTERACTION_TYPES
        },
        group_names=[interactions, structures, top],
    )


def delete_run(cmd: Any, run: OverlayRun | None) -> None:
    if run is None:
        return
    existing = set(cmd.get_names("all"))
    for name in run.owned_names:
        if name in existing:
            cmd.delete(name)


def _temporary_names(cmd: Any) -> tuple[str, str]:
    return (
        cmd.get_unused_name("_PLIP_Pose_Inspector_endpoint_A"),
        cmd.get_unused_name("_PLIP_Pose_Inspector_endpoint_B"),
    )


def _add_measurement(
    cmd: Any,
    *,
    object_name: str,
    start: Iterable[float],
    end: Iterable[float],
    state: int,
    reset: bool,
    endpoint_names: tuple[str, str],
) -> None:
    first, second = endpoint_names
    cmd.delete(f"{first} {second}")
    cmd.pseudoatom(first, pos=tuple(float(value) for value in start), state=state)
    cmd.pseudoatom(second, pos=tuple(float(value) for value in end), state=state)
    cmd.distance(
        object_name,
        first,
        second,
        state=state,
        label=0,
        reset=int(reset),
    )


def _render_measurement_object(
    cmd: Any,
    *,
    object_name: str,
    interaction_type: str,
    profiles: dict[int, dict[str, Any]],
    total_states: int,
) -> None:
    endpoint_names = _temporary_names(cmd)
    first_measurement = True
    try:
        for state in range(1, total_states + 1):
            profile = profiles.get(state)
            edges = () if profile is None else profile["interactions"].get(interaction_type, ())
            for edge in edges:
                _add_measurement(
                    cmd,
                    object_name=object_name,
                    start=edge["start"],
                    end=edge["end"],
                    state=state,
                    reset=first_measurement,
                    endpoint_names=endpoint_names,
                )
                first_measurement = False

        # A zero-length measurement is invisible, but forces PyMOL to retain
        # the final state and all explicit empty states before it.
        _add_measurement(
            cmd,
            object_name=object_name,
            start=(0.0, 0.0, 0.0),
            end=(0.0, 0.0, 0.0),
            state=total_states,
            reset=first_measurement,
            endpoint_names=endpoint_names,
        )
    finally:
        cmd.delete(f"{endpoint_names[0]} {endpoint_names[1]}")

    style = INTERACTION_STYLES[interaction_type]
    cmd.set("dash_color", style["color_name"], object_name)
    cmd.set("dash_gap", float(style["dash_gap"]), object_name)
    cmd.set(
        "dash_length",
        float(style["dash_length"] if style["dash_length"] > 0 else 0.15),
        object_name,
    )
    # Radius intentionally inherits PyMOL's global setting. This preserves
    # normal behavior for commands such as: set dash_radius, .09
    cmd.unset("dash_radius", object_name)
    cmd.hide("labels", object_name)


def render_profiles(
    cmd: Any,
    *,
    ligand_object: str,
    profiles: dict[int, dict[str, Any]],
    total_states: int,
    previous_run: OverlayRun | None = None,
    enabled_types: set[str] | None = None,
) -> OverlayRun:
    if total_states < 1:
        raise ValueError("Interaction overlays require at least one state")
    run = make_run(ligand_object)
    delete_run(cmd, previous_run)
    if previous_run is None or previous_run.top_group != run.top_group:
        # Also replaces namespaced Beta 0.1 CGO objects in place.
        delete_run(cmd, run)

    cmd.group(run.top_group, "")
    cmd.group(run.interactions_group, "")
    cmd.group(run.structures_group, "")
    cmd.group(run.top_group, run.interactions_group)
    cmd.group(run.top_group, run.structures_group)

    for interaction_type in INTERACTION_TYPES:
        object_name = run.object_names[interaction_type]
        _render_measurement_object(
            cmd,
            object_name=object_name,
            interaction_type=interaction_type,
            profiles=profiles,
            total_states=total_states,
        )
        cmd.group(run.interactions_group, object_name)
        enabled = (
            interaction_type != "hydrophobic_contacts"
            if enabled_types is None
            else interaction_type in enabled_types
        )
        (cmd.enable if enabled else cmd.disable)(object_name)

    return run


def interaction_enabled(cmd: Any, run: OverlayRun, interaction_type: str) -> bool:
    enabled = set(cmd.get_names("all", enabled_only=1))
    return run.object_names[interaction_type] in enabled


def normalize_pocket_mode(value: Any) -> str:
    if isinstance(value, bool):
        return "current" if value else "off"
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "1": "current",
        "on": "current",
        "true": "current",
        "yes": "current",
        "current_pose": "current",
        "dynamic": "current",
        "union": "all",
        "all_poses": "all",
        "all_analyzed": "all",
        "0": "off",
        "false": "off",
        "no": "off",
        "hidden": "off",
        "hide": "off",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in POCKET_MODES:
        raise ValueError("Pocket mode must be current, all, or off")
    return normalized


def _quoted(value: Any) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _residue_selection(
    receptor_selection: str,
    residues: Iterable[dict[str, Any]],
) -> str | None:
    clauses = []
    for residue in residues:
        clauses.append(
            "(chain {chain} and resi {resi} and resn {resn})".format(
                chain=_quoted(residue.get("chain", "")),
                resi=_quoted(residue.get("resi", "")),
                resn=_quoted(residue.get("resn", "")),
            )
        )
    if not clauses:
        return None
    return f"({receptor_selection}) and ({' or '.join(clauses)})"


def _union_residues(profiles: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    residues: dict[tuple[str, str, str], dict[str, Any]] = {}
    for profile in profiles.values():
        for residue in profile.get("residues", ()):
            key = (
                str(residue.get("chain", "")),
                str(residue.get("resi", "")),
                str(residue.get("resn", "")),
            )
            residues[key] = residue
    return [residues[key] for key in sorted(residues)]


def _style_pocket(cmd: Any, run: OverlayRun, object_name: str) -> None:
    sentinel_selection = f"({object_name}) and segi {_quoted(POCKET_SENTINEL_SEGI)}"
    cmd.hide("everything", object_name)
    cmd.show("sticks", object_name)
    cmd.hide("everything", sentinel_selection)
    cmd.hide("sticks", f"({object_name}) and elem H")
    try:
        cmd.util.cnc(object_name)
    except Exception:
        pass
    cmd.group(run.structures_group, object_name)


def set_pocket_visibility(cmd: Any, run: OverlayRun, mode: str) -> None:
    mode = normalize_pocket_mode(mode)
    existing = set(cmd.get_names("all"))
    current_exists = run.pocket_name in existing
    all_exists = run.pocket_all_name in existing
    if mode == "current" and not current_exists:
        raise ValueError("The current-pose pocket is unavailable")
    if mode == "all" and not all_exists:
        raise ValueError("The all-analyzed-poses pocket is unavailable")
    for object_name, enabled in (
        (run.pocket_name, mode == "current"),
        (run.pocket_all_name, mode == "all"),
    ):
        if object_name in existing:
            (cmd.enable if enabled else cmd.disable)(object_name)


def detect_pocket_mode(cmd: Any, run: OverlayRun) -> str:
    enabled = set(cmd.get_names("all", enabled_only=1))
    if run.pocket_name in enabled:
        return "current"
    if run.pocket_all_name in enabled:
        return "all"
    return "off"


def render_pockets(
    cmd: Any,
    *,
    run: OverlayRun,
    receptor_selection: str,
    receptor_state: int,
    profiles: dict[int, dict[str, Any]],
    total_states: int,
    mode: str,
) -> None:
    mode = normalize_pocket_mode(mode)
    cmd.delete(run.pocket_name)
    cmd.delete(run.pocket_all_name)
    if total_states < 1:
        raise ValueError("Pocket rendering requires at least one state")

    receptor_model = cmd.get_model(receptor_selection, receptor_state)
    if not receptor_model.atom:
        raise ValueError("The active receptor selection is unavailable")
    anchor = tuple(float(value) for value in receptor_model.atom[0].coord)
    sentinel = cmd.get_unused_name("_PLIP_Pose_Inspector_pocket_sentinel")
    cmd.pseudoatom(
        sentinel,
        name="DUM",
        resn="PPI",
        resi="0",
        chain="",
        segi=POCKET_SENTINEL_SEGI,
        elem="X",
        pos=anchor,
        state=receptor_state,
    )
    try:
        for state in range(1, total_states + 1):
            profile = profiles.get(state)
            residues = () if profile is None else profile.get("residues", ())
            residue_selection = _residue_selection(receptor_selection, residues)
            selection = (
                f"({sentinel}) or ({residue_selection})"
                if residue_selection
                else sentinel
            )
            cmd.create(
                run.pocket_name,
                selection,
                receptor_state,
                state,
                discrete=1,
            )

        residue_selection = _residue_selection(
            receptor_selection,
            _union_residues(profiles),
        )
        selection = (
            f"({sentinel}) or ({residue_selection})"
            if residue_selection
            else sentinel
        )
        cmd.create(
            run.pocket_all_name,
            selection,
            receptor_state,
            1,
            discrete=1,
        )
        cmd.set("static_singletons", 1, run.pocket_all_name)
    finally:
        cmd.delete(sentinel)

    _style_pocket(cmd, run, run.pocket_name)
    _style_pocket(cmd, run, run.pocket_all_name)
    set_pocket_visibility(cmd, run, mode)


def ensure_all_pocket(
    cmd: Any,
    *,
    run: OverlayRun,
    receptor_selection: str,
    receptor_state: int,
) -> bool:
    """Build a Beta 0.3 union pocket from a Beta 0.2 current pocket."""

    existing = set(cmd.get_names("all"))
    if run.pocket_all_name in existing:
        return True
    if run.pocket_name not in existing or not receptor_selection:
        return False

    residues: dict[tuple[str, str, str], dict[str, str]] = {}
    for state in range(1, max(1, int(cmd.count_states(run.pocket_name))) + 1):
        for atom in cmd.get_model(run.pocket_name, state).atom:
            if str(atom.segi) == POCKET_SENTINEL_SEGI:
                continue
            key = (str(atom.chain), str(atom.resi), str(atom.resn))
            residues[key] = {"chain": key[0], "resi": key[1], "resn": key[2]}

    receptor_model = cmd.get_model(receptor_selection, receptor_state)
    if not receptor_model.atom:
        return False
    anchor = tuple(float(value) for value in receptor_model.atom[0].coord)
    sentinel = cmd.get_unused_name("_PLIP_Pose_Inspector_pocket_sentinel")
    cmd.pseudoatom(
        sentinel,
        name="DUM",
        resn="PPI",
        resi="0",
        chain="",
        segi=POCKET_SENTINEL_SEGI,
        elem="X",
        pos=anchor,
        state=receptor_state,
    )
    try:
        residue_selection = _residue_selection(
            receptor_selection,
            [residues[key] for key in sorted(residues)],
        )
        selection = (
            f"({sentinel}) or ({residue_selection})"
            if residue_selection
            else sentinel
        )
        cmd.create(
            run.pocket_all_name,
            selection,
            receptor_state,
            1,
            discrete=1,
        )
        cmd.set("static_singletons", 1, run.pocket_all_name)
    finally:
        cmd.delete(sentinel)
    _style_pocket(cmd, run, run.pocket_all_name)
    cmd.disable(run.pocket_all_name)
    return True

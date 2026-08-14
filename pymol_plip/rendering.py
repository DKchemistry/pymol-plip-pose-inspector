"""State-aligned CGO rendering for normalized PLIP profiles."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from pymol.cgo import SAUSAGE

from .constants import (
    DEFAULT_DASH_RADIUS,
    INTERACTION_LABELS,
    INTERACTION_STYLES,
    INTERACTION_TYPES,
)


def safe_name(value: str, *, fallback: str = "poses") -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not value:
        value = fallback
    if value[0].isdigit():
        value = "x_" + value
    return value[:80]


def _point_along(
    start: tuple[float, float, float],
    unit: tuple[float, float, float],
    distance: float,
) -> tuple[float, float, float]:
    return tuple(start[index] + unit[index] * distance for index in range(3))


def rounded_segment(
    start: Iterable[float],
    end: Iterable[float],
    *,
    color: tuple[float, float, float],
    radius: float = DEFAULT_DASH_RADIUS,
) -> list[float]:
    first = tuple(float(value) for value in start)
    second = tuple(float(value) for value in end)
    if math.dist(first, second) < 1e-8:
        return []
    return [
        SAUSAGE,
        *first,
        *second,
        float(radius),
        *color,
        *color,
    ]


def dashed_segment(
    start: Iterable[float],
    end: Iterable[float],
    *,
    color: tuple[float, float, float],
    dash_length: float,
    dash_gap: float,
    radius: float = DEFAULT_DASH_RADIUS,
) -> list[float]:
    first = tuple(float(value) for value in start)
    second = tuple(float(value) for value in end)
    vector = tuple(second[index] - first[index] for index in range(3))
    distance = math.sqrt(sum(value * value for value in vector))
    if distance < 1e-8:
        return []
    if dash_length <= 0.0 or dash_gap <= 0.0:
        return rounded_segment(first, second, color=color, radius=radius)

    unit = tuple(value / distance for value in vector)
    geometry: list[float] = []
    position = 0.0
    while position < distance:
        segment_end = min(distance, position + dash_length)
        geometry.extend(
            rounded_segment(
                _point_along(first, unit, position),
                _point_along(first, unit, segment_end),
                color=color,
                radius=radius,
            )
        )
        position += dash_length + dash_gap
    return geometry


def profile_cgo(profile: dict[str, Any] | None, interaction_type: str) -> list[float]:
    if not profile:
        return []
    style = INTERACTION_STYLES[interaction_type]
    geometry: list[float] = []
    for interaction in profile["interactions"].get(interaction_type, []):
        geometry.extend(
            dashed_segment(
                interaction["start"],
                interaction["end"],
                color=style["color"],
                dash_length=float(style["dash_length"]),
                dash_gap=float(style["dash_gap"]),
            )
        )
    return geometry


@dataclass
class OverlayRun:
    run_name: str
    top_group: str
    interactions_group: str
    structures_group: str
    pocket_name: str
    object_names: dict[str, str] = field(default_factory=dict)
    group_names: list[str] = field(default_factory=list)

    @property
    def owned_names(self) -> list[str]:
        return list(self.object_names.values()) + [self.pocket_name] + self.group_names


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


def render_profiles(
    cmd: Any,
    *,
    ligand_object: str,
    profiles: dict[int, dict[str, Any]],
    total_states: int,
    previous_run: OverlayRun | None = None,
    enabled_types: set[str] | None = None,
) -> OverlayRun:
    run = make_run(ligand_object)
    delete_run(cmd, previous_run)
    if previous_run is None or previous_run.top_group != run.top_group:
        delete_run(cmd, run)

    cmd.group(run.top_group, "")
    cmd.group(run.interactions_group, "")
    cmd.group(run.structures_group, "")
    cmd.group(run.top_group, run.interactions_group)
    cmd.group(run.top_group, run.structures_group)

    for interaction_type in INTERACTION_TYPES:
        object_name = run.object_names[interaction_type]
        for state in range(1, total_states + 1):
            geometry = profile_cgo(profiles.get(state), interaction_type)
            cmd.load_cgo(geometry, object_name, state=state)
            count = 0
            if state in profiles:
                count = len(
                    profiles[state]["interactions"].get(interaction_type, ())
                )
            try:
                cmd.set_title(
                    object_name,
                    state,
                    f"{INTERACTION_LABELS[interaction_type]}: {count}",
                )
            except Exception:
                pass
        cmd.group(run.interactions_group, object_name)
        if enabled_types is None:
            enabled = interaction_type != "hydrophobic_contacts"
        else:
            enabled = interaction_type in enabled_types
        if enabled:
            cmd.enable(object_name)
        else:
            cmd.disable(object_name)

    return run


def interaction_enabled(cmd: Any, run: OverlayRun, interaction_type: str) -> bool:
    enabled = set(cmd.get_names("all", enabled_only=1))
    return run.object_names[interaction_type] in enabled

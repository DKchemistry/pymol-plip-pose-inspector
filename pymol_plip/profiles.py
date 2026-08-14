"""Versioned interaction-profile helpers with no PyMOL dependency."""

from __future__ import annotations

from typing import Any

from .constants import INTERACTION_TYPES, PROFILE_SCHEMA_VERSION

Vector3 = tuple[float, float, float]
Profile = dict[str, Any]


def empty_interactions() -> dict[str, list[dict[str, Any]]]:
    return {name: [] for name in INTERACTION_TYPES}


def empty_profile(
    *,
    title: str,
    receptor_hash: str,
    pose_hash: str,
    hydrogen_policy: str,
) -> Profile:
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "title": title,
        "receptor_hash": receptor_hash,
        "pose_hash": pose_hash,
        "hydrogen_policy": hydrogen_policy,
        "engine": {},
        "interactions": empty_interactions(),
        "residues": [],
        "warnings": [],
    }


def validate_profile(profile: Profile) -> None:
    if profile.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise ValueError("Unsupported profile schema")
    interactions = profile.get("interactions")
    if not isinstance(interactions, dict):
        raise ValueError("Profile has no interaction mapping")
    for name in INTERACTION_TYPES:
        edges = interactions.get(name)
        if not isinstance(edges, list):
            raise ValueError(f"Profile interaction class is missing: {name}")
        for edge in edges:
            if not isinstance(edge, dict):
                raise ValueError(f"Invalid {name} interaction record")
            for endpoint in ("start", "end"):
                vector = edge.get(endpoint)
                if not isinstance(vector, (list, tuple)) or len(vector) != 3:
                    raise ValueError(f"Invalid {name} {endpoint} coordinate")
                try:
                    [float(value) for value in vector]
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid {name} {endpoint} coordinate") from exc
            if not isinstance(edge.get("metadata", {}), dict):
                raise ValueError(f"Invalid {name} interaction metadata")
    if not isinstance(profile.get("residues"), list):
        raise ValueError("Profile interacting residues are missing")
    if profile.get("hydrogen_policy") not in {"use_input", "add_missing"}:
        raise ValueError("Profile hydrogen policy is invalid")


def interaction_counts(profile: Profile) -> dict[str, int]:
    validate_profile(profile)
    return {
        name: len(profile["interactions"].get(name, ()))
        for name in INTERACTION_TYPES
    }

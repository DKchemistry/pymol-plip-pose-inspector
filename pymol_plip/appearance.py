"""Validated interaction-appearance preferences and PyMOL application helpers."""

from __future__ import annotations

import json
from typing import Any

from .constants import INTERACTION_STYLES, INTERACTION_TYPES

APPEARANCE_SCHEMA_VERSION = 1
APPEARANCE_SETTINGS_KEY = "interaction_appearance_v1"
PATTERNS = ("solid", "dashed", "long_dashed", "custom")
PATTERN_LABELS = {
    "solid": "Solid",
    "dashed": "Dashed",
    "long_dashed": "Long dashed",
    "custom": "Custom",
}
PATTERN_VALUES = {
    "solid": (0.15, 0.0),
    "dashed": (0.15, 0.50),
    "long_dashed": (0.60, 0.30),
}


def infer_pattern(length: float, gap: float) -> str:
    for pattern, values in PATTERN_VALUES.items():
        if abs(float(length) - values[0]) < 1e-5 and abs(float(gap) - values[1]) < 1e-5:
            return pattern
    return "custom"


def plip_appearance() -> dict[str, dict[str, Any]]:
    result = {}
    for name in INTERACTION_TYPES:
        source = INTERACTION_STYLES[name]
        length = float(source["dash_length"] if source["dash_length"] > 0 else 0.15)
        gap = float(source["dash_gap"])
        result[name] = {
            "color": [float(value) for value in source["color"]],
            "pattern": infer_pattern(length, gap),
            "dash_length": length,
            "dash_gap": gap,
        }
    return result


def validate_appearance(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("Appearance settings must be a mapping")
    result = {}
    for name in INTERACTION_TYPES:
        style = value.get(name)
        if not isinstance(style, dict):
            raise ValueError(f"Appearance settings are missing {name}")
        color = style.get("color")
        if not isinstance(color, (list, tuple)) or len(color) != 3:
            raise ValueError(f"Invalid color for {name}")
        color = [float(component) for component in color]
        if any(component < 0.0 or component > 1.0 for component in color):
            raise ValueError(f"Color components for {name} must be between zero and one")
        pattern = str(style.get("pattern", "custom"))
        if pattern not in PATTERNS:
            raise ValueError(f"Invalid line pattern for {name}")
        dash_length = float(style.get("dash_length", 0.15))
        dash_gap = float(style.get("dash_gap", 0.0))
        if dash_length < 0.0 or dash_gap < 0.0:
            raise ValueError(f"Dash length and gap for {name} cannot be negative")
        if pattern in PATTERN_VALUES:
            dash_length, dash_gap = PATTERN_VALUES[pattern]
        result[name] = {
            "color": color,
            "pattern": pattern,
            "dash_length": dash_length,
            "dash_gap": dash_gap,
        }
    return result


def load_saved_appearance(settings: Any) -> dict[str, dict[str, Any]]:
    raw = str(settings.value(APPEARANCE_SETTINGS_KEY, "") or "").strip()
    if not raw:
        return plip_appearance()
    try:
        envelope = json.loads(raw)
        if envelope.get("schema_version") != APPEARANCE_SCHEMA_VERSION:
            raise ValueError("Unsupported appearance settings schema")
        return validate_appearance(envelope.get("styles"))
    except Exception:
        return plip_appearance()


def save_appearance(settings: Any, styles: Any) -> dict[str, dict[str, Any]]:
    validated = validate_appearance(styles)
    settings.setValue(
        APPEARANCE_SETTINGS_KEY,
        json.dumps(
            {
                "schema_version": APPEARANCE_SCHEMA_VERSION,
                "styles": validated,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    return validated


def clear_saved_appearance(settings: Any) -> None:
    settings.remove(APPEARANCE_SETTINGS_KEY)


def apply_appearance(cmd: Any, run: Any, styles: Any) -> dict[str, dict[str, Any]]:
    validated = validate_appearance(styles)
    existing = set(cmd.get_names("all"))
    for interaction_type, style in validated.items():
        object_name = run.object_names[interaction_type]
        if object_name not in existing:
            continue
        color_name = f"{run.top_group}_Color_{interaction_type}"
        cmd.set_color(color_name, style["color"])
        cmd.set("dash_color", color_name, object_name)
        cmd.set("dash_length", style["dash_length"], object_name)
        cmd.set("dash_gap", style["dash_gap"], object_name)
    return validated


def read_appearance(cmd: Any, run: Any) -> dict[str, dict[str, Any]]:
    defaults = plip_appearance()
    existing = set(cmd.get_names("all"))
    for interaction_type, object_name in run.object_names.items():
        if object_name not in existing:
            continue
        length = float(cmd.get("dash_length", object_name))
        gap = float(cmd.get("dash_gap", object_name))
        defaults[interaction_type] = {
            "color": [
                float(value)
                for value in cmd.get_color_tuple(cmd.get("dash_color", object_name))
            ],
            "pattern": infer_pattern(length, gap),
            "dash_length": length,
            "dash_gap": gap,
        }
    return defaults

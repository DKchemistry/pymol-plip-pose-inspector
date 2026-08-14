"""Shared constants for the PyMOL plugin and external worker."""

from __future__ import annotations

PLUGIN_NAME = "PLIP Pose Inspector"
PLUGIN_VERSION = "0.3.0"
PROFILE_SCHEMA_VERSION = 2
CACHE_SCHEMA_VERSION = 1
EXPORT_SCHEMA_VERSION = 1

EXPECTED_PLIP_VERSION = "3.0.1"
MINIMUM_OPENBABEL_VERSION = (3, 2, 0)
WORKER_ENV_NAME = "pymol-plip-plugin"

TARGET_RESNAME = "LIG"
TARGET_RESNUM = 9999
TARGET_CHAIN_CANDIDATES = "ZYXWVUTSRQPONMLKJIHGFEDCBA"

INTERACTION_TYPES = (
    "hydrogen_bonds",
    "hydrophobic_contacts",
    "halogen_bonds",
    "water_bridges",
    "salt_bridges",
    "pi_stacking_parallel",
    "pi_stacking_t",
    "pi_cation",
    "metal_coordination",
)

INTERACTION_LABELS = {
    "hydrogen_bonds": "Hydrogen bonds",
    "hydrophobic_contacts": "Hydrophobic contacts",
    "halogen_bonds": "Halogen bonds",
    "water_bridges": "Water bridges",
    "salt_bridges": "Salt bridges",
    "pi_stacking_parallel": "Pi stacking (parallel)",
    "pi_stacking_t": "Pi stacking (T-shaped)",
    "pi_cation": "Pi-cation",
    "metal_coordination": "Metal coordination",
}

# RGB values match the named colors used by PLIP's PyMOL visualizer.
INTERACTION_STYLES = {
    "hydrogen_bonds": {
        "color": (0.0, 0.0, 1.0),
        "color_name": "blue",
        "dash_length": 0.0,
        "dash_gap": 0.0,
    },
    "hydrophobic_contacts": {
        "color": (0.50505, 0.50505, 0.50505),
        "color_name": "grey50",
        "dash_length": 0.15,
        "dash_gap": 0.50,
    },
    "halogen_bonds": {
        "color": (0.25, 1.0, 0.75),
        "color_name": "greencyan",
        "dash_length": 0.0,
        "dash_gap": 0.0,
    },
    "water_bridges": {
        "color": (0.75, 0.75, 1.0),
        "color_name": "lightblue",
        "dash_length": 0.0,
        "dash_gap": 0.0,
    },
    "salt_bridges": {
        "color": (1.0, 1.0, 0.0),
        "color_name": "yellow",
        "dash_length": 0.15,
        "dash_gap": 0.50,
    },
    "pi_stacking_parallel": {
        "color": (0.0, 1.0, 0.0),
        "color_name": "green",
        "dash_length": 0.60,
        "dash_gap": 0.30,
    },
    "pi_stacking_t": {
        "color": (0.55, 0.70, 0.40),
        "color_name": "smudge",
        "dash_length": 0.60,
        "dash_gap": 0.30,
    },
    "pi_cation": {
        "color": (1.0, 0.5, 0.0),
        "color_name": "orange",
        "dash_length": 0.60,
        "dash_gap": 0.30,
    },
    "metal_coordination": {
        "color": (0.55, 0.25, 0.60),
        "color_name": "violetpurple",
        "dash_length": 0.15,
        "dash_gap": 0.50,
    },
}

DEFAULT_RECEPTOR_FILTER = "polymer.protein or solvent or inorganic"

"""Shared constants for the PyMOL and worker runtimes."""

from __future__ import annotations

PLUGIN_NAME = "Ligand Review Panel"
PLUGIN_VERSION = "0.1.0"
WORKER_ENV_NAME = "pymol-ligand-review"

MANIFEST_SCHEMA_VERSION = 1
DEPICTION_SCHEMA_VERSION = 1
CACHE_SCHEMA_VERSION = 1

DRAW_WIDTH = 600
DRAW_HEIGHT = 400

CSV_FIELDS = (
    "name",
    "identifier",
    "smiles",
    "ligand_object",
    "selected_state",
    "matching_sources",
    "selected_at_utc",
)


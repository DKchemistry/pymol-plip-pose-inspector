#!/usr/bin/env python3
"""Health check for the complete external chemistry runtime."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymol_plip.constants import (
    EXPECTED_OPENBABEL_VERSION,
    EXPECTED_PLIP_VERSION,
    EXPECTED_RDKIT_VERSION,
)


def engine_info() -> dict[str, str]:
    from openbabel import openbabel
    from rdkit import rdBase

    return {
        "python": platform.python_version(),
        "plip": importlib.metadata.version("plip"),
        "openbabel": str(openbabel.OBReleaseVersion()),
        "rdkit": str(rdBase.rdkitVersion),
    }


def validate_engine(engine: dict[str, str]) -> None:
    expected = {
        "plip": EXPECTED_PLIP_VERSION,
        "openbabel": EXPECTED_OPENBABEL_VERSION,
        "rdkit": EXPECTED_RDKIT_VERSION,
    }
    mismatches = [
        f"{name} {version} is required; found {engine.get(name, '?')}"
        for name, version in expected.items()
        if engine.get(name) != version
    ]
    if mismatches:
        raise RuntimeError("; ".join(mismatches))


def main() -> int:
    try:
        engine = engine_info()
        validate_engine(engine)
        print(json.dumps({"event": "health", "ok": True, "engine": engine}))
        return 0
    except Exception as exc:
        print(json.dumps({"event": "fatal", "ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


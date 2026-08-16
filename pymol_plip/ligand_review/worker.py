#!/usr/bin/env python3
"""External RDKit worker. This module must not import PyMOL."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pymol_plip.ligand_review.cache import DepictionCache, depiction_key
from pymol_plip.ligand_review.constants import (
    DRAW_HEIGHT,
    DRAW_WIDTH,
    MANIFEST_SCHEMA_VERSION,
)
from pymol_plip.ligand_review.selection import identity_key


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True), flush=True)


def engine_info() -> dict[str, str]:
    from rdkit import rdBase

    return {"python": platform.python_version(), "rdkit": rdBase.rdkitVersion}


def health() -> int:
    try:
        emit({"event": "health", "ok": True, "engine": engine_info()})
        return 0
    except Exception as exc:
        emit({"event": "fatal", "ok": False, "error": str(exc)})
        return 1


def depict_job(job: dict[str, Any], cache: DepictionCache, rdkit_version: str) -> dict[str, Any]:
    from rdkit import Chem
    from rdkit.Chem import rdDepictor
    from rdkit.Chem.Draw import rdMolDraw2D

    if job.get("error"):
        raise ValueError(str(job["error"]))
    text = Path(job["sdf_path"]).read_text(encoding="utf-8")
    mol = Chem.MolFromMolBlock(text, sanitize=True, removeHs=True, strictParsing=True)
    if mol is None:
        raise ValueError("RDKit could not parse or sanitize this ligand state")
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    smiles = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    if not smiles:
        raise ValueError("RDKit did not produce a canonical SMILES")
    key = depiction_key(smiles, rdkit_version)
    image_path = cache.load(key)
    cache_hit = image_path is not None
    if image_path is None:
        rdDepictor.Compute2DCoords(mol, canonOrient=True, clearConfs=True)
        drawer = rdMolDraw2D.MolDraw2DCairo(DRAW_WIDTH, DRAW_HEIGHT)
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        image_path = cache.store(key, bytes(drawer.GetDrawingText()))
    title = str(job["title"])
    return {
        "event": "depiction",
        "state": int(job["state"]),
        "title": title,
        "ligand_object": str(job["ligand_object"]),
        "smiles": smiles,
        "identity_key": identity_key(title, smiles),
        "image_path": str(image_path),
        "input_hash": str(job.get("input_hash", "")),
        "cache_hit": cache_hit,
        "warnings": [],
    }


def run_manifest(filename: str) -> int:
    try:
        manifest = json.loads(Path(filename).read_text(encoding="utf-8"))
        if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            raise ValueError("Unsupported worker manifest schema")
        engine = engine_info()
        emit({"event": "started", "engine": engine, "total": len(manifest["jobs"])})
        cache = DepictionCache()
        hits = failures = 0
        for completed, job in enumerate(manifest["jobs"], 1):
            try:
                result = depict_job(job, cache, engine["rdkit"])
                hits += int(result["cache_hit"])
                emit(result)
            except Exception as exc:
                failures += 1
                emit(
                    {
                        "event": "failure",
                        "state": int(job["state"]),
                        "title": str(job["title"]),
                        "error": str(exc),
                    }
                )
            emit(
                {
                    "event": "progress",
                    "completed": completed,
                    "total": len(manifest["jobs"]),
                    "cache_hits": hits,
                    "failures": failures,
                }
            )
        emit(
            {
                "event": "complete",
                "total": len(manifest["jobs"]),
                "cache_hits": hits,
                "failures": failures,
            }
        )
        return 0
    except Exception as exc:
        emit({"event": "fatal", "error": str(exc)})
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?")
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    if args.health:
        return health()
    if not args.manifest:
        parser.error("manifest is required")
    return run_manifest(args.manifest)


if __name__ == "__main__":
    raise SystemExit(main())

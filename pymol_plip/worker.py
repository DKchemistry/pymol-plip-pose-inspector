"""External PLIP analysis worker.

The worker communicates exclusively with line-delimited JSON on stdout. It has
no dependency on PyMOL and is intended to run in the isolated PLIP environment.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import io
import json
import logging
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Iterable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymol_plip.cache import ProfileCache, make_cache_key
from pymol_plip.constants import (
    EXPECTED_PLIP_VERSION,
    INTERACTION_TYPES,
    MINIMUM_OPENBABEL_VERSION,
    PROFILE_SCHEMA_VERSION,
)
from pymol_plip.profiles import empty_interactions, validate_profile

OUTPUT = sys.stdout


def emit(event: dict[str, Any]) -> None:
    print(json.dumps(event, sort_keys=True, separators=(",", ":")), file=OUTPUT)
    OUTPUT.flush()


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(value) for value in re.findall(r"\d+", version)[:3])


def engine_versions() -> dict[str, str]:
    from openbabel import openbabel

    try:
        openbabel_version = str(openbabel.OBReleaseVersion())
    except Exception:
        openbabel_version = importlib.metadata.version("openbabel")
    return {
        "plip": importlib.metadata.version("plip"),
        "openbabel": openbabel_version,
        "python": sys.version.split()[0],
    }


def validate_engine(engine: dict[str, str]) -> None:
    if engine["plip"] != EXPECTED_PLIP_VERSION:
        raise RuntimeError(
            f"PLIP {EXPECTED_PLIP_VERSION} is required; found {engine['plip']}"
        )
    if _version_tuple(engine["openbabel"]) < MINIMUM_OPENBABEL_VERSION:
        minimum = ".".join(str(value) for value in MINIMUM_OPENBABEL_VERSION)
        raise RuntimeError(
            f"OpenBabel {minimum} or newer is required; "
            f"found {engine['openbabel']}"
        )


def _coords(value: Any) -> list[float]:
    if hasattr(value, "coords"):
        value = value.coords
    return [float(value[0]), float(value[1]), float(value[2])]


def _scalar(value: Any) -> Any:
    if isinstance(value, (str, bool, int)) or value is None:
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _residue(interaction: Any) -> dict[str, Any] | None:
    chain = str(getattr(interaction, "reschain", "") or "")
    resn = str(getattr(interaction, "restype", "") or "")
    resi = getattr(interaction, "resnr", None)
    if resi is None:
        return None
    return {"chain": chain, "resi": str(resi), "resn": resn}


def _edge(
    start: Any,
    end: Any,
    *,
    residue: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "start": _coords(start),
        "end": _coords(end),
        "residue": residue,
        "metadata": {key: _scalar(value) for key, value in (metadata or {}).items()},
    }


def _unique_residues(edges: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    values: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        residue = edge.get("residue")
        if not residue:
            continue
        key = (residue["chain"], residue["resi"], residue["resn"])
        values[key] = residue
    return [values[key] for key in sorted(values)]


def normalize_interactions(plcomplex: Any) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    result = empty_interactions()

    for interaction in plcomplex.hydrophobic_contacts:
        result["hydrophobic_contacts"].append(
            _edge(
                interaction.bsatom,
                interaction.ligatom,
                residue=_residue(interaction),
                metadata={"distance": interaction.distance},
            )
        )

    for interaction in plcomplex.hbonds_pdon + plcomplex.hbonds_ldon:
        ligand_atom, protein_atom = (
            (interaction.a, interaction.d)
            if interaction.protisdon
            else (interaction.d, interaction.a)
        )
        result["hydrogen_bonds"].append(
            _edge(
                protein_atom,
                ligand_atom,
                residue=_residue(interaction),
                metadata={
                    "protein_is_donor": interaction.protisdon,
                    "distance_da": interaction.distance_ad,
                    "angle": interaction.angle,
                },
            )
        )

    for interaction in plcomplex.halogen_bonds:
        result["halogen_bonds"].append(
            _edge(
                interaction.acc.o,
                interaction.don.x,
                residue=_residue(interaction),
                metadata={
                    "distance": interaction.distance,
                    "donor_angle": interaction.don_angle,
                    "acceptor_angle": interaction.acc_angle,
                },
            )
        )

    for bridge_index, interaction in enumerate(plcomplex.water_bridges, 1):
        ligand_atom, protein_atom = (
            (interaction.a, interaction.d)
            if interaction.protisdon
            else (interaction.d, interaction.a)
        )
        residue = _residue(interaction)
        result["water_bridges"].append(
            _edge(
                protein_atom,
                interaction.water,
                residue=residue,
                metadata={"bridge": bridge_index, "segment": "protein-water"},
            )
        )
        result["water_bridges"].append(
            _edge(
                interaction.water,
                ligand_atom,
                residue=residue,
                metadata={"bridge": bridge_index, "segment": "water-ligand"},
            )
        )

    for interaction in plcomplex.saltbridge_lneg + plcomplex.saltbridge_pneg:
        if interaction.protispos:
            protein_center = interaction.positive.center
            ligand_center = interaction.negative.center
        else:
            protein_center = interaction.negative.center
            ligand_center = interaction.positive.center
        result["salt_bridges"].append(
            _edge(
                protein_center,
                ligand_center,
                residue=_residue(interaction),
                metadata={
                    "distance": interaction.distance,
                    "protein_is_positive": interaction.protispos,
                },
            )
        )

    for interaction in plcomplex.pistacking:
        kind = (
            "pi_stacking_parallel"
            if str(interaction.type).upper() == "P"
            else "pi_stacking_t"
        )
        result[kind].append(
            _edge(
                interaction.proteinring.center,
                interaction.ligandring.center,
                residue=_residue(interaction),
                metadata={
                    "distance": interaction.distance,
                    "angle": interaction.angle,
                    "offset": interaction.offset,
                },
            )
        )

    for interaction in plcomplex.pication_laro + plcomplex.pication_paro:
        if interaction.protcharged:
            protein_center = interaction.charge.center
            ligand_center = interaction.ring.center
        else:
            protein_center = interaction.ring.center
            ligand_center = interaction.charge.center
        result["pi_cation"].append(
            _edge(
                protein_center,
                ligand_center,
                residue=_residue(interaction),
                metadata={
                    "distance": interaction.distance,
                    "offset": interaction.offset,
                    "protein_is_charged": interaction.protcharged,
                },
            )
        )

    for interaction in plcomplex.metal_complexes:
        result["metal_coordination"].append(
            _edge(
                interaction.metal,
                interaction.target.atom,
                residue=(
                    _residue(interaction)
                    if str(interaction.location).startswith("protein")
                    else None
                ),
                metadata={
                    "distance": interaction.distance,
                    "location": interaction.location,
                    "geometry": interaction.geometry,
                    "metal_type": interaction.metal_type,
                },
            )
        )

    all_edges = [edge for kind in INTERACTION_TYPES for edge in result[kind]]
    return result, _unique_residues(all_edges)


def analyze_job(job: dict[str, Any], engine: dict[str, str]) -> dict[str, Any]:
    from plip.basic import config
    from plip.structure.preparation import PDBComplex

    config.NOFIXFILE = True
    config.NOHYDRO = job["hydrogen_policy"] == "use_input"
    config.MODEL = 1

    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    logged_warnings: list[str] = []

    class WarningCollector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno >= logging.WARNING:
                logged_warnings.append(self.format(record))

    warning_collector = WarningCollector()
    root_logger = logging.getLogger()
    root_logger.addHandler(warning_collector)
    try:
        with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(
            captured_stderr
        ):
            molecule = PDBComplex()
            molecule.load_pdb(job["complex_path"])
            molecule.analyze()
    finally:
        root_logger.removeHandler(warning_collector)

    target = job["target"]
    if target not in molecule.interaction_sets:
        available = ", ".join(sorted(molecule.interaction_sets))
        raise RuntimeError(
            f"Synthetic target {target} was not found in PLIP output. "
            f"Available sites: {available or 'none'}"
        )
    interactions, residues = normalize_interactions(molecule.interaction_sets[target])
    diagnostics = captured_stdout.getvalue() + captured_stderr.getvalue()
    warnings = (
        logged_warnings
        + [line.strip() for line in diagnostics.splitlines() if line.strip()]
    )[-20:]
    profile = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "title": job["title"],
        "receptor_hash": job["receptor_hash"],
        "pose_hash": job["pose_hash"],
        "hydrogen_policy": job["hydrogen_policy"],
        "engine": engine,
        "interactions": interactions,
        "residues": residues,
        "warnings": warnings,
    }
    validate_profile(profile)
    return profile


def profile_for_job(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """Apply pose-local display metadata after a chemistry cache hit."""

    result = dict(profile)
    result["title"] = job["title"]
    return result


def run_manifest(path: Path) -> int:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported worker manifest schema")

    engine = engine_versions()
    validate_engine(engine)
    emit({"event": "hello", "engine": engine})
    cache = ProfileCache(manifest.get("cache_dir"))
    jobs = manifest.get("jobs", [])
    total = len(jobs)
    completed = 0
    hits = 0

    for job in jobs:
        state = int(job["state"])
        key = make_cache_key(job, engine)
        profile = cache.load(key)
        cache_hit = profile is not None
        if cache_hit:
            hits += 1
            profile = profile_for_job(profile, job)
        else:
            try:
                profile = analyze_job(job, engine)
                cache.store(key, profile)
            except Exception as exc:
                completed += 1
                emit(
                    {
                        "event": "state_error",
                        "state": state,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                        "completed": completed,
                        "total": total,
                        "cache_hits": hits,
                    }
                )
                continue
        completed += 1
        emit(
            {
                "event": "profile",
                "state": state,
                "cache_key": key,
                "cache_hit": cache_hit,
                "profile": profile,
                "completed": completed,
                "total": total,
                "cache_hits": hits,
            }
        )

    emit(
        {
            "event": "complete",
            "completed": completed,
            "total": total,
            "cache_hits": hits,
        }
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args(argv)
    try:
        engine = engine_versions()
        validate_engine(engine)
        if args.health:
            emit({"event": "health", "ok": True, "engine": engine})
            return 0
        if args.manifest is None:
            parser.error("--manifest is required unless --health is used")
        return run_manifest(args.manifest)
    except Exception as exc:
        emit(
            {
                "event": "fatal",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

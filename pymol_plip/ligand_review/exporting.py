"""Read immutable ligand states from PyMOL for the external worker."""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import MANIFEST_SCHEMA_VERSION
from ..workspace import (
    WorkspaceError,
    clean_state_title,
    ordered_states,
    resolve_single_object as _resolve_single_object,
)


class ExportError(ValueError):
    pass


@dataclass
class ExportBundle:
    temporary_directory: tempfile.TemporaryDirectory[str]
    manifest_path: Path
    ligand_selection: str
    ligand_object: str
    total_states: int

    def cleanup(self) -> None:
        self.temporary_directory.cleanup()


def resolve_single_object(cmd: Any, selection: str) -> str:
    try:
        return _resolve_single_object(cmd, selection)
    except WorkspaceError as exc:
        raise ExportError(str(exc)) from exc


def export_bundle(cmd: Any, ligand_selection: str) -> ExportBundle:
    ligand_object = resolve_single_object(cmd, ligand_selection)
    total_states = int(cmd.count_states(ligand_object))
    if total_states < 1:
        raise ExportError("Ligand object has no states")
    current = max(1, min(int(cmd.get_state()), total_states))
    temporary_directory = tempfile.TemporaryDirectory(prefix="pymol-ligand-review-")
    root = Path(temporary_directory.name)
    jobs: list[dict[str, Any]] = []
    try:
        for state in ordered_states(current, total_states):
            title = clean_state_title(cmd.get_title(ligand_object, state), state=state)
            atom_count = int(cmd.count_atoms(ligand_selection, state=state))
            if atom_count < 1:
                jobs.append(
                    {
                        "state": state,
                        "title": title,
                        "ligand_object": ligand_object,
                        "error": "Ligand selection is empty in this state",
                    }
                )
                continue
            try:
                sdf = str(cmd.get_str("sdf", ligand_selection, state=state))
            except Exception as exc:
                jobs.append(
                    {
                        "state": state,
                        "title": title,
                        "ligand_object": ligand_object,
                        "error": f"PyMOL could not export SDF: {exc}",
                    }
                )
                continue
            if "M  END" not in sdf:
                jobs.append(
                    {
                        "state": state,
                        "title": title,
                        "ligand_object": ligand_object,
                        "error": "PyMOL produced an invalid SDF record",
                    }
                )
                continue
            sdf_path = root / f"state-{state:06d}.sdf"
            sdf_path.write_text(sdf, encoding="utf-8")
            jobs.append(
                {
                    "state": state,
                    "title": title,
                    "ligand_object": ligand_object,
                    "sdf_path": str(sdf_path),
                    "input_hash": hashlib.sha256(sdf.encode("utf-8")).hexdigest(),
                }
            )
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "ligand_object": ligand_object,
            "total_states": total_states,
            "jobs": jobs,
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
    except Exception:
        temporary_directory.cleanup()
        raise
    return ExportBundle(
        temporary_directory=temporary_directory,
        manifest_path=manifest_path,
        ligand_selection=ligand_selection,
        ligand_object=ligand_object,
        total_states=total_states,
    )

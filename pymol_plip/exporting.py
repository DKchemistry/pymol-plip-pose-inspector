"""Export PyMOL selections into deterministic PLIP analysis jobs."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .cache import default_cache_dir
from .constants import (
    EXPORT_SCHEMA_VERSION,
    PROFILE_SCHEMA_VERSION,
    TARGET_CHAIN_CANDIDATES,
    TARGET_RESNAME,
    TARGET_RESNUM,
)


class ExportError(ValueError):
    pass


@dataclass
class ExportBundle:
    temporary_directory: tempfile.TemporaryDirectory[str]
    manifest_path: Path
    receptor_selection: str
    receptor_state: int
    ligand_selection: str
    ligand_object: str
    total_states: int
    requested_states: list[int]
    target: str

    def cleanup(self) -> None:
        self.temporary_directory.cleanup()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_state_title(value: Any, *, state: int) -> str:
    """Normalize titles produced by PyMOL's multi-record SDF reader.

    PyMOL 2.5 and 3.1 append the literal token ``none`` to titles for SDF
    records without an explicit state annotation.  It is an implementation
    detail, not part of the compound name.
    """

    title = str(value or "").strip()
    title = re.sub(r"(?:\s+|^)none$", "", title, flags=re.IGNORECASE).strip()
    return title or f"State {state}"


def parse_states(spec: Any, *, current: int, total: int) -> list[int]:
    if spec is None or str(spec).strip().lower() == "all":
        return list(range(1, total + 1))
    if str(spec).strip().lower() == "current":
        return [current]
    values: list[int] = []
    if isinstance(spec, int):
        values = [spec]
    else:
        for part in re.split(r"[,+\s]+", str(spec).strip()):
            if not part:
                continue
            if "-" in part:
                start_text, end_text = part.split("-", 1)
                start, end = int(start_text), int(end_text)
                values.extend(range(start, end + 1))
            else:
                values.append(int(part))
    values = sorted(set(values))
    if not values or values[0] < 1 or values[-1] > total:
        raise ExportError(f"State selection must be between 1 and {total}")
    return values


def resolve_single_object(cmd: Any, selection: str) -> str:
    try:
        objects = cmd.get_object_list(f"({selection})")
    except Exception as exc:
        raise ExportError(f"Invalid ligand selection: {selection}") from exc
    if len(objects) != 1:
        raise ExportError(
            "Ligand selection must resolve to exactly one molecular object; "
            f"found {len(objects)}"
        )
    return objects[0]


def _pdb_atom_lines(pdb_text: str) -> list[str]:
    return [
        line.rstrip("\r\n")
        for line in pdb_text.splitlines()
        if line.startswith(("ATOM  ", "HETATM"))
    ]


def _pdb_conect_lines(pdb_text: str) -> list[str]:
    return [
        line.rstrip("\r\n")
        for line in pdb_text.splitlines()
        if line.startswith("CONECT")
    ]


def _existing_residue_keys(atom_lines: Iterable[str]) -> set[tuple[str, int, str]]:
    result: set[tuple[str, int, str]] = set()
    for line in atom_lines:
        try:
            result.add((line[21:22], int(line[22:26]), line[17:20].strip()))
        except ValueError:
            continue
    return result


def choose_target(atom_lines: Iterable[str]) -> tuple[str, int, str]:
    existing = _existing_residue_keys(atom_lines)
    for resnum in range(TARGET_RESNUM, 8999, -1):
        for chain in TARGET_CHAIN_CANDIDATES:
            candidate = (chain, resnum, TARGET_RESNAME)
            if candidate not in existing:
                return candidate
    raise ExportError("Could not allocate a collision-free synthetic ligand residue")


def _atom_name_field(name: str) -> str:
    name = name[:4]
    if len(name) < 4:
        return " " + name.ljust(3)
    return name


def _formal_charge_field(value: Any) -> str:
    try:
        charge = int(value)
    except (TypeError, ValueError):
        return "  "
    if charge == 0 or abs(charge) > 9:
        return "  "
    return f"{abs(charge)}{'+' if charge > 0 else '-'}"


def _bond_multiplicity(order: Any) -> int:
    try:
        numeric = float(order)
    except (TypeError, ValueError):
        return 1
    rounded = int(round(numeric))
    return rounded if rounded in (1, 2, 3) else 1


def build_ligand_pdb(
    model: Any,
    *,
    serial_offset: int,
    chain: str,
    resnum: int,
    resname: str = TARGET_RESNAME,
) -> str:
    atoms = list(model.atom)
    if not atoms:
        raise ExportError("Ligand state contains no atoms")
    if serial_offset + len(atoms) > 99999:
        raise ExportError("Combined structure exceeds the PDB 99,999 atom limit")

    element_counts: Counter[str] = Counter()
    atom_lines: list[str] = []
    for index, atom in enumerate(atoms):
        element = str(getattr(atom, "symbol", "") or "X").strip().upper()
        element_counts[element] += 1
        atom_name = f"{element}{element_counts[element]}"[:4]
        x, y, z = (float(value) for value in atom.coord)
        serial = serial_offset + index + 1
        charge = _formal_charge_field(getattr(atom, "formal_charge", 0))
        atom_lines.append(
            f"HETATM{serial:5d} {_atom_name_field(atom_name)} "
            f"{resname:>3} {chain:1}{resnum:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{0.0:6.2f}"
            f"          {element:>2}{charge:>2}"
        )

    adjacency: dict[int, list[int]] = defaultdict(list)
    for bond in model.bond:
        left, right = (int(value) for value in bond.index)
        copies = _bond_multiplicity(getattr(bond, "order", 1))
        adjacency[left].extend([right] * copies)
        adjacency[right].extend([left] * copies)

    conect_lines: list[str] = []
    for index in range(len(atoms)):
        neighbors = adjacency.get(index, [])
        if not neighbors:
            continue
        serial = serial_offset + index + 1
        conect_lines.append(
            "CONECT"
            + f"{serial:5d}"
            + "".join(f"{serial_offset + neighbor + 1:5d}" for neighbor in neighbors)
        )
    return "\n".join(atom_lines + conect_lines) + "\n"


def combine_complex(receptor_pdb: str, ligand_pdb: str) -> str:
    receptor_atoms = _pdb_atom_lines(receptor_pdb)
    ligand_atoms = _pdb_atom_lines(ligand_pdb)
    if not receptor_atoms:
        raise ExportError("Receptor selection contains no PDB-compatible atoms")
    if not ligand_atoms:
        raise ExportError("Ligand export contains no PDB-compatible atoms")
    lines = (
        receptor_atoms
        + ligand_atoms
        + _pdb_conect_lines(receptor_pdb)
        + _pdb_conect_lines(ligand_pdb)
        + ["END"]
    )
    return "\n".join(lines) + "\n"


def export_bundle(
    cmd: Any,
    *,
    receptor_selection: str,
    ligand_selection: str,
    receptor_state: int,
    states: Any = "all",
    cache_dir: str | None = None,
) -> ExportBundle:
    if cmd.count_atoms(receptor_selection, state=receptor_state) == 0:
        raise ExportError("Receptor selection is empty in the requested state")

    ligand_object = resolve_single_object(cmd, ligand_selection)
    total_states = int(cmd.count_states(ligand_object))
    if total_states < 1:
        raise ExportError("Ligand object has no states")
    requested_states = parse_states(
        states, current=int(cmd.get_state()), total=total_states
    )

    receptor_pdb = cmd.get_pdbstr(receptor_selection, state=receptor_state)
    receptor_atoms = _pdb_atom_lines(receptor_pdb)
    if not receptor_atoms:
        raise ExportError("Receptor selection could not be serialized as PDB")
    try:
        serial_offset = max(int(line[6:11]) for line in receptor_atoms)
    except ValueError as exc:
        raise ExportError("Receptor PDB atom serials are invalid") from exc

    target_chain, target_resnum, target_resname = choose_target(receptor_atoms)
    target = f"{target_resname}:{target_chain}:{target_resnum}"
    receptor_hash = sha256_text(
        "\n".join(receptor_atoms + _pdb_conect_lines(receptor_pdb)) + "\n"
    )
    receptor_has_h = cmd.count_atoms(
        f"({receptor_selection}) and elem H", state=receptor_state
    ) > 0

    temporary_directory = tempfile.TemporaryDirectory(prefix="pymol-plip-")
    root = Path(temporary_directory.name)
    jobs: list[dict[str, Any]] = []
    try:
        for state in requested_states:
            model = cmd.get_model(ligand_selection, state)
            ligand_pdb = build_ligand_pdb(
                model,
                serial_offset=serial_offset,
                chain=target_chain,
                resnum=target_resnum,
                resname=target_resname,
            )
            complex_pdb = combine_complex(receptor_pdb, ligand_pdb)
            complex_path = root / f"state-{state:06d}.pdb"
            complex_path.write_text(complex_pdb, encoding="ascii")
            ligand_has_h = any(
                str(getattr(atom, "symbol", "")).upper() == "H"
                for atom in model.atom
            )
            hydrogen_policy = (
                "use_input" if receptor_has_h and ligand_has_h else "add_missing"
            )
            title = clean_state_title(cmd.get_title(ligand_object, state), state=state)
            jobs.append(
                {
                    "state": state,
                    "title": title,
                    "complex_path": str(complex_path),
                    "target": target,
                    "receptor_hash": receptor_hash,
                    "pose_hash": sha256_text(ligand_pdb),
                    "hydrogen_policy": hydrogen_policy,
                    "analysis_options": {
                        "export_schema": EXPORT_SCHEMA_VERSION,
                        "receptor_selection": receptor_selection,
                        "receptor_state": receptor_state,
                        "profile_schema": PROFILE_SCHEMA_VERSION,
                    },
                }
            )

        manifest = {
            "schema_version": 1,
            "cache_dir": str(cache_dir or default_cache_dir()),
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
        receptor_selection=receptor_selection,
        receptor_state=receptor_state,
        ligand_selection=ligand_selection,
        ligand_object=ligand_object,
        total_states=total_states,
        requested_states=requested_states,
        target=target,
    )

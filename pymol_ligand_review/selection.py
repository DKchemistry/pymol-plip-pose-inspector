"""Session-only compound selections and CSV export."""

from __future__ import annotations

import csv
import hashlib
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import CSV_FIELDS


def identity_key(title: str, smiles: str) -> str:
    normalized = " ".join(str(title).split()).casefold()
    return hashlib.sha256(f"{normalized}\n{smiles}".encode("utf-8")).hexdigest()


@dataclass
class SelectedCompound:
    key: str
    name: str
    identifier: str
    smiles: str
    ligand_object: str
    selected_state: int
    selected_at_utc: str


class SelectionStore:
    def __init__(self) -> None:
        self.selected: dict[str, SelectedCompound] = {}
        self.sources: dict[str, set[tuple[str, int]]] = {}

    def register(self, record: dict[str, Any]) -> None:
        key = str(record["identity_key"])
        self.sources.setdefault(key, set()).add(
            (str(record["ligand_object"]), int(record["state"]))
        )

    def is_selected(self, key: str) -> bool:
        return key in self.selected

    def mark(
        self,
        record: dict[str, Any],
        *,
        name: str = "",
        identifier: str = "",
    ) -> SelectedCompound:
        self.register(record)
        key = str(record["identity_key"])
        if key in self.selected:
            compound = self.selected[key]
            if name:
                compound.name = str(name)
            if identifier:
                compound.identifier = str(identifier)
            return compound
        title = str(record["title"])
        compound = SelectedCompound(
            key=key,
            name=str(name).strip() or title,
            identifier=str(identifier).strip() or title,
            smiles=str(record["smiles"]),
            ligand_object=str(record["ligand_object"]),
            selected_state=int(record["state"]),
            selected_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self.selected[key] = compound
        return compound

    def unmark(self, key: str) -> None:
        self.selected.pop(str(key), None)

    def update(self, key: str, *, name: str | None = None, identifier: str | None = None) -> None:
        compound = self.selected[str(key)]
        if name is not None:
            compound.name = str(name).strip() or compound.name
        if identifier is not None:
            compound.identifier = str(identifier).strip() or compound.identifier

    def clear(self) -> None:
        self.selected.clear()

    def records(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key, compound in self.selected.items():
            row = asdict(compound)
            row["matching_sources"] = ";".join(
                f"{object_name}:{state}"
                for object_name, state in sorted(self.sources.get(key, set()))
            )
            rows.append(row)
        return rows

    def export_csv(self, filename: str | Path) -> int:
        path = Path(filename).expanduser()
        if not self.selected:
            raise ValueError("No compounds are marked")
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in self.records():
                writer.writerow(row)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        return len(self.selected)


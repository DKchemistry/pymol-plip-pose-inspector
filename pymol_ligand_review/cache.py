"""Persistent depiction cache used by the external worker."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
from pathlib import Path
from typing import Any

from .constants import CACHE_SCHEMA_VERSION, DEPICTION_SCHEMA_VERSION, DRAW_HEIGHT, DRAW_WIDTH


def default_cache_dir() -> Path:
    override = os.environ.get("PYMOL_LIGAND_REVIEW_CACHE", "").strip()
    if override:
        return Path(override).expanduser()
    system = platform.system()
    if system == "Darwin":
        root = Path.home() / "Library" / "Caches"
    elif system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "PyMOLLigandReview"


def depiction_key(smiles: str, rdkit_version: str) -> str:
    payload = {
        "cache_schema": CACHE_SCHEMA_VERSION,
        "depiction_schema": DEPICTION_SCHEMA_VERSION,
        "height": DRAW_HEIGHT,
        "rdkit": rdkit_version,
        "smiles": smiles,
        "width": DRAW_WIDTH,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class DepictionCache:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else default_cache_dir()

    def path_for(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.png"

    def load(self, key: str) -> Path | None:
        path = self.path_for(key)
        return path if path.is_file() and path.stat().st_size > 8 else None

    def store(self, key: str, png: bytes) -> Path:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{key}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(png)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        return path

    def stats(self) -> tuple[int, int]:
        if not self.root.exists():
            return 0, 0
        paths = list(self.root.glob("*/*.png"))
        return len(paths), sum(path.stat().st_size for path in paths if path.is_file())

    def clear(self) -> None:
        if not self.root.exists():
            return
        for path in self.root.glob("*/*.png"):
            path.unlink(missing_ok=True)
        for directory in self.root.glob("*"):
            if directory.is_dir():
                try:
                    directory.rmdir()
                except OSError:
                    pass

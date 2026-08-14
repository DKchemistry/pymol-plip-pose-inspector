"""Content-addressed, gzip-compressed profile cache."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .constants import CACHE_SCHEMA_VERSION, PROFILE_SCHEMA_VERSION
from .profiles import Profile, validate_profile


def default_cache_dir() -> Path:
    override = os.environ.get("PYMOL_PLIP_CACHE")
    if override:
        return Path(override).expanduser()
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Caches" / "PLIPPoseInspector"
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "pymol-plip-pose-inspector"


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def make_cache_key(job: dict[str, Any], engine: dict[str, str]) -> str:
    material = {
        "cache_schema": CACHE_SCHEMA_VERSION,
        "profile_schema": PROFILE_SCHEMA_VERSION,
        "engine": engine,
        "receptor_hash": job["receptor_hash"],
        "pose_hash": job["pose_hash"],
        "hydrogen_policy": job["hydrogen_policy"],
        "target": job["target"],
        "analysis_options": job.get("analysis_options", {}),
    }
    return hashlib.sha256(canonical_json(material)).hexdigest()


class ProfileCache:
    def __init__(self, root: str | os.PathLike[str] | None = None):
        self.root = Path(root) if root else default_cache_dir()

    def path_for(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json.gz"

    def load(self, key: str) -> Profile | None:
        path = self.path_for(key)
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                envelope = json.load(handle)
            if envelope.get("cache_schema") != CACHE_SCHEMA_VERSION:
                return None
            if envelope.get("key") != key:
                return None
            profile = envelope["profile"]
            validate_profile(profile)
            return profile
        except (FileNotFoundError, OSError, ValueError, KeyError, TypeError):
            return None

    def store(self, key: str, profile: Profile) -> Path:
        validate_profile(profile)
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "cache_schema": CACHE_SCHEMA_VERSION,
            "key": key,
            "profile": profile,
        }
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{key}.", suffix=".tmp", dir=path.parent
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            with gzip.open(tmp_path, "wt", encoding="utf-8") as handle:
                json.dump(envelope, handle, sort_keys=True, separators=(",", ":"))
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)
        return path

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)

    def stats(self) -> tuple[int, int]:
        if not self.root.exists():
            return 0, 0
        files = list(self.root.glob("*/*.json.gz"))
        return len(files), sum(path.stat().st_size for path in files)


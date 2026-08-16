"""Shared external interpreter discovery, settings migration, and health checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from pymol.Qt import QtCore

from .constants import WORKER_ENV_NAME


NEW_SETTINGS = ("PyMOL Pose Inspector", "PyMOL Pose Inspector")
LEGACY_SETTINGS = (
    ("PLIP Pose Inspector", "PLIP Pose Inspector"),
    ("PyMOL Ligand Review", "Ligand Review Panel"),
)


def unified_settings() -> Any:
    settings = QtCore.QSettings(*NEW_SETTINGS)
    if not bool(settings.value("legacy_settings_migrated_v1", False, type=bool)):
        plip = QtCore.QSettings(*LEGACY_SETTINGS[0])
        for key in ("interaction_appearance_v1", "citation_dialog_shown"):
            if not settings.contains(key) and plip.contains(key):
                settings.setValue(key, plip.value(key))
        settings.setValue("legacy_settings_migrated_v1", True)
    return settings


class WorkerRuntime:
    """One validated Python interpreter used by the PLIP and RDKit workers."""

    def __init__(self, settings: Any | None = None):
        self.settings = settings or unified_settings()
        self._health_cache: dict[str, tuple[bool, str, dict[str, str]]] = {}

    @property
    def health_script(self) -> Path:
        return Path(__file__).with_name("runtime_check.py")

    def worker_python_candidates(self) -> list[Path]:
        configured = str(self.settings.value("worker_python", "") or "").strip()
        values = [
            configured,
            os.environ.get("PYMOL_POSE_INSPECTOR_PYTHON", "").strip(),
        ]
        home = Path.home()
        candidates = [Path(value).expanduser() for value in values if value]
        candidates.extend(
            root / "envs" / WORKER_ENV_NAME / "bin" / "python"
            for root in (
                home / "miniconda3",
                home / "miniforge3",
                home / "mambaforge",
                home / "anaconda3",
            )
        )
        for organization, application in LEGACY_SETTINGS:
            old = QtCore.QSettings(organization, application)
            value = str(old.value("worker_python", "") or "").strip()
            if value:
                candidates.append(Path(value).expanduser())
        for name in ("PYMOL_PLIP_PYTHON", "PYMOL_LIGAND_REVIEW_PYTHON"):
            value = os.environ.get(name, "").strip()
            if value:
                candidates.append(Path(value).expanduser())
        candidates.append(Path(sys.executable))
        unique: list[Path] = []
        for path in candidates:
            if path not in unique:
                unique.append(path)
        return unique

    def set_worker_python(self, value: str) -> None:
        self.settings.setValue(
            "worker_python", str(Path(value).expanduser()) if value else ""
        )
        self._health_cache.clear()

    def health_check(
        self, python_path: str | Path | None = None
    ) -> tuple[bool, str, dict[str, str]]:
        path = Path(python_path).expanduser() if python_path else self.worker_python(validate=False)
        key = str(path)
        if key in self._health_cache:
            return self._health_cache[key]
        if not path.is_file():
            result = (False, f"Python executable does not exist: {path}", {})
            self._health_cache[key] = result
            return result
        try:
            completed = subprocess.run(
                [str(path), str(self.health_script)],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            event: dict[str, Any] = {}
            for line in completed.stdout.splitlines():
                try:
                    candidate = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if candidate.get("event") in {"health", "fatal"}:
                    event = candidate
            if completed.returncode == 0 and event.get("ok"):
                engine = dict(event.get("engine", {}))
                result = (
                    True,
                    "Ready: "
                    f"PLIP {engine.get('plip', '?')}, "
                    f"OpenBabel {engine.get('openbabel', '?')}, "
                    f"RDKit {engine.get('rdkit', '?')}, "
                    f"Python {engine.get('python', '?')}",
                    engine,
                )
            else:
                detail = event.get("error") or completed.stderr.strip() or completed.stdout.strip()
                result = (
                    False,
                    detail or f"Worker health check exited with status {completed.returncode}",
                    {},
                )
        except Exception as exc:
            result = (False, str(exc), {})
        self._health_cache[key] = result
        return result

    def worker_python(self, *, validate: bool = True) -> Path:
        candidates = self.worker_python_candidates()
        configured = str(self.settings.value("worker_python", "") or "").strip()
        for candidate in candidates:
            if not candidate.is_file() or not os.access(candidate, os.X_OK):
                continue
            if not validate:
                return candidate
            ok, _message, _engine = self.health_check(candidate)
            if ok:
                return candidate
            if configured and candidate == Path(configured).expanduser():
                break
        if configured:
            ok, message, _engine = self.health_check(Path(configured).expanduser())
            raise FileNotFoundError(f"Configured worker is unavailable: {message}")
        searched = "\n".join(f"  {path}" for path in candidates)
        raise FileNotFoundError(
            f"Could not find the {WORKER_ENV_NAME!r} environment containing "
            f"PLIP, OpenBabel, and RDKit. Searched:\n{searched}\n"
            "Create it from environment.yml or configure its Python in Settings."
        )

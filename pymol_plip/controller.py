"""Main-thread orchestration between PyMOL, the Qt UI, and the PLIP worker."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from pymol.Qt import QtCore

from .cache import ProfileCache, default_cache_dir
from .constants import (
    DEFAULT_RECEPTOR_FILTER,
    INTERACTION_LABELS,
    INTERACTION_TYPES,
    WORKER_ENV_NAME,
)
from .exporting import ExportBundle, ExportError, clean_state_title, export_bundle
from .profiles import interaction_counts
from .rendering import (
    OverlayRun,
    delete_run,
    interaction_enabled,
    normalize_pocket_mode,
    render_pocket,
    render_profiles,
)

Signal = getattr(QtCore, "Signal", QtCore.pyqtSignal)


TYPE_ALIASES = {
    "hbond": "hydrogen_bonds",
    "hbonds": "hydrogen_bonds",
    "hydrogen": "hydrogen_bonds",
    "hydrogen_bond": "hydrogen_bonds",
    "hydrophobic": "hydrophobic_contacts",
    "halogen": "halogen_bonds",
    "water": "water_bridges",
    "salt": "salt_bridges",
    "saltbridge": "salt_bridges",
    "pi_parallel": "pi_stacking_parallel",
    "pistacking": "pi_stacking_parallel",
    "pi_t": "pi_stacking_t",
    "pication": "pi_cation",
    "metal": "metal_coordination",
}


class PoseInspectorController(QtCore.QObject):
    """Own the long-lived analysis state independently of the dialog."""

    status_changed = Signal(str)
    progress_changed = Signal(int, int, int, int)
    running_changed = Signal(bool)
    profiles_changed = Signal()
    state_changed = Signal(int, str, bool)
    objects_changed = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, cmd: Any):
        super().__init__()
        self.cmd = cmd
        self.settings = QtCore.QSettings("PLIP Pose Inspector", "PLIP Pose Inspector")
        self.process: QtCore.QProcess | None = None
        self.bundle: ExportBundle | None = None
        self.run: OverlayRun | None = None
        self.profiles: dict[int, dict[str, Any]] = {}
        self.failures: dict[int, str] = {}
        self.engine: dict[str, str] = {}
        self.active_receptor_selection = ""
        self.active_receptor_state = 1
        self.active_ligand_object = ""
        self.total_states = 0
        self.pocket_mode = "current"
        self.type_preferences = {
            name: name != "hydrophobic_contacts" for name in INTERACTION_TYPES
        }

        self._pending_profiles: dict[int, dict[str, Any]] = {}
        self._pending_failures: dict[int, str] = {}
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._complete_event: dict[str, Any] | None = None
        self._cancelled = False
        self._requested_pocket_mode = "current"
        self._last_state: int | None = None
        self._last_title = ""

        self.state_timer = QtCore.QTimer(self)
        self.state_timer.setInterval(175)
        self.state_timer.timeout.connect(self._poll_state)
        self.state_timer.start()

    @property
    def is_running(self) -> bool:
        return self.process is not None

    @property
    def worker_script(self) -> Path:
        return Path(__file__).with_name("worker.py")

    def worker_python_candidates(self) -> list[Path]:
        configured = str(self.settings.value("worker_python", "") or "").strip()
        environment = os.environ.get("PYMOL_PLIP_PYTHON", "").strip()
        home = Path.home()
        candidates = [Path(value).expanduser() for value in (configured, environment) if value]
        candidates.extend(
            root / "envs" / WORKER_ENV_NAME / "bin" / "python"
            for root in (
                home / "miniconda3",
                home / "miniforge3",
                home / "mambaforge",
                home / "anaconda3",
            )
        )
        unique: list[Path] = []
        for candidate in candidates:
            if candidate not in unique:
                unique.append(candidate)
        return unique

    def worker_python(self) -> Path:
        candidates = self.worker_python_candidates()
        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
        configured = str(self.settings.value("worker_python", "") or "").strip()
        if configured:
            raise FileNotFoundError(f"Configured worker Python does not exist: {configured}")
        searched = "\n".join(f"  {path}" for path in candidates)
        raise FileNotFoundError(
            f"Could not find the {WORKER_ENV_NAME!r} worker environment. "
            f"Searched:\n{searched}\nConfigure its Python executable in Settings."
        )

    def set_worker_python(self, value: str) -> None:
        self.settings.setValue("worker_python", str(Path(value).expanduser()) if value else "")

    def health_check(self, python_path: str | None = None) -> tuple[bool, str, dict[str, str]]:
        try:
            executable = Path(python_path).expanduser() if python_path else self.worker_python()
            completed = subprocess.run(
                [str(executable), str(self.worker_script), "--health"],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            events = []
            for line in completed.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            event = next((item for item in reversed(events) if item.get("event") in {"health", "fatal"}), {})
            if completed.returncode == 0 and event.get("ok"):
                engine = dict(event.get("engine", {}))
                summary = (
                    f"Ready: PLIP {engine.get('plip', '?')}, "
                    f"OpenBabel {engine.get('openbabel', '?')}, Python {engine.get('python', '?')}"
                )
                return True, summary, engine
            message = event.get("error") or completed.stderr.strip() or completed.stdout.strip()
            return False, message or f"Worker exited with status {completed.returncode}", {}
        except Exception as exc:
            return False, str(exc), {}

    def molecular_objects(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for name in self.cmd.get_names("objects"):
            try:
                if self.cmd.get_type(name) != "object:molecule":
                    continue
                result.append(
                    {
                        "name": name,
                        "states": int(self.cmd.count_states(name)),
                        "atoms": int(self.cmd.count_atoms(name)),
                        "protein_atoms": int(self.cmd.count_atoms(f"({name}) and polymer.protein")),
                    }
                )
            except Exception:
                continue
        self.objects_changed.emit(result)
        return result

    def ligand_info(self, selection: str) -> tuple[str, int, int, str]:
        try:
            objects = self.cmd.get_object_list(f"({selection})")
            if len(objects) != 1:
                return "", 0, int(self.cmd.get_state()), ""
            name = objects[0]
            total = int(self.cmd.count_states(name))
            current = max(1, min(int(self.cmd.get_state()), total))
            title = clean_state_title(self.cmd.get_title(name, current), state=current)
            return name, total, current, title
        except Exception:
            return "", 0, int(self.cmd.get_state()), ""

    def analyze(
        self,
        *,
        receptor: str,
        ligand: str,
        states: Any = "all",
        receptor_state: int = 0,
        filtered: bool = True,
        pocket: Any = "current",
    ) -> None:
        if self.is_running:
            raise RuntimeError("An analysis is already running")
        receptor = receptor.strip()
        ligand = ligand.strip()
        if not receptor or not ligand:
            raise ExportError("Both receptor and ligand selections are required")
        final_receptor = (
            f"({receptor}) and ({DEFAULT_RECEPTOR_FILTER})" if filtered else f"({receptor})"
        )
        receptor_objects = self.cmd.get_object_list(final_receptor)
        if not receptor_objects:
            raise ExportError("Receptor selection does not contain a molecular object")
        state_count = max(int(self.cmd.count_states(name)) for name in receptor_objects)
        if receptor_state <= 0:
            receptor_state = max(1, min(int(self.cmd.get_state()), state_count))
        elif receptor_state > state_count:
            raise ExportError(
                f"Receptor state {receptor_state} is unavailable; selection has {state_count} state(s)"
            )

        worker = self.worker_python()
        bundle = export_bundle(
            self.cmd,
            receptor_selection=final_receptor,
            ligand_selection=ligand,
            receptor_state=receptor_state,
            states=states,
        )
        self.bundle = bundle
        self._pending_profiles = {}
        self._pending_failures = {}
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._complete_event = None
        self._cancelled = False
        self._requested_pocket_mode = normalize_pocket_mode(pocket)

        process = QtCore.QProcess(self)
        self.process = process
        process.setProgram(str(worker))
        process.setArguments([str(self.worker_script), "--manifest", str(bundle.manifest_path)])
        environment = QtCore.QProcessEnvironment.systemEnvironment()
        project_root = str(self.worker_script.parent.parent)
        old_pythonpath = environment.value("PYTHONPATH")
        environment.insert("PYTHONPATH", project_root + (os.pathsep + old_pythonpath if old_pythonpath else ""))
        environment.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(environment)
        process.setProcessChannelMode(QtCore.QProcess.SeparateChannels)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.errorOccurred.connect(self._process_error)
        process.finished.connect(self._process_finished)

        self.running_changed.emit(True)
        self.progress_changed.emit(0, len(bundle.requested_states), 0, 0)
        self.status_changed.emit(
            f"Analyzing {len(bundle.requested_states)} pose(s) in the external PLIP worker…"
        )
        process.start()

    def cancel(self) -> None:
        if self.process is None:
            return
        self._cancelled = True
        self.status_changed.emit("Cancelling analysis…")
        self.process.kill()

    def _read_stdout(self) -> None:
        if self.process is None:
            return
        self._stdout_buffer += bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            if not line.strip():
                continue
            try:
                self._handle_event(json.loads(line))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                self._stderr_buffer += f"Invalid worker output ({exc}): {line}\n"
                self._stderr_buffer = self._stderr_buffer[-131_072:]

    def _read_stderr(self) -> None:
        if self.process is not None:
            self._stderr_buffer += bytes(self.process.readAllStandardError()).decode("utf-8", "replace")
            self._stderr_buffer = self._stderr_buffer[-131_072:]

    def _handle_event(self, event: dict[str, Any]) -> None:
        kind = event.get("event")
        if kind == "hello":
            self.engine = dict(event.get("engine", {}))
            self.status_changed.emit(
                f"PLIP {self.engine.get('plip', '?')} / OpenBabel {self.engine.get('openbabel', '?')}"
            )
        elif kind == "profile":
            state = int(event["state"])
            self._pending_profiles[state] = event["profile"]
            self.progress_changed.emit(
                int(event.get("completed", 0)),
                int(event.get("total", 0)),
                int(event.get("cache_hits", 0)),
                len(self._pending_failures),
            )
        elif kind == "state_error":
            state = int(event["state"])
            self._pending_failures[state] = str(event.get("error", "Unknown worker error"))
            self.progress_changed.emit(
                int(event.get("completed", 0)),
                int(event.get("total", 0)),
                int(event.get("cache_hits", 0)),
                len(self._pending_failures),
            )
        elif kind == "complete":
            self._complete_event = event
        elif kind == "fatal":
            self._pending_failures[0] = str(event.get("error", "PLIP worker failed"))

    def _process_error(self, error: Any) -> None:
        if self._cancelled:
            return
        detail = self.process.errorString() if self.process is not None else str(error)
        message = f"Worker process error: {detail}"
        self.status_changed.emit(message)
        if error == QtCore.QProcess.FailedToStart:
            process = self.process
            bundle = self.bundle
            self.process = None
            self.bundle = None
            if bundle is not None:
                bundle.cleanup()
            if process is not None:
                process.deleteLater()
            self.running_changed.emit(False)
            self.error_occurred.emit(message)

    def _process_finished(self, exit_code: int, exit_status: Any) -> None:
        process = self.process
        if process is not None:
            self._read_stdout()
            self._read_stderr()
        bundle = self.bundle
        self.process = None
        self.bundle = None

        try:
            if self._cancelled:
                self.status_changed.emit("Analysis cancelled; existing overlays were left unchanged.")
                return
            if bundle is None:
                return
            successful = bool(self._pending_profiles)
            normal = int(exit_code) == 0 and self._complete_event is not None
            if not normal and not successful:
                detail = self._pending_failures.get(0) or self._stderr_buffer.strip()
                message = detail or f"PLIP worker exited with status {exit_code}"
                self.status_changed.emit(message)
                self.error_occurred.emit(message)
                return

            same_source = (
                self.active_ligand_object == bundle.ligand_object
                and self.active_receptor_selection == bundle.receptor_selection
                and self.active_receptor_state == bundle.receptor_state
                and self.total_states == bundle.total_states
            )
            profiles = dict(self.profiles) if same_source else {}
            failures = dict(self.failures) if same_source else {}
            profiles.update(self._pending_profiles)
            for state in self._pending_profiles:
                failures.pop(state, None)
            failures.update(self._pending_failures)

            enabled_types = {
                name for name in INTERACTION_TYPES if self.type_preferences[name]
            }
            self.run = render_profiles(
                self.cmd,
                ligand_object=bundle.ligand_object,
                profiles=profiles,
                total_states=bundle.total_states,
                previous_run=self.run,
                enabled_types=enabled_types,
            )
            self.profiles = profiles
            self.failures = failures
            self.active_receptor_selection = bundle.receptor_selection
            self.active_receptor_state = bundle.receptor_state
            self.active_ligand_object = bundle.ligand_object
            self.total_states = bundle.total_states
            self.pocket_mode = self._requested_pocket_mode
            self._last_state = None
            self._render_pocket()
            self.profiles_changed.emit()
            completed = int((self._complete_event or {}).get("completed", len(self._pending_profiles) + len(self._pending_failures)))
            hits = int((self._complete_event or {}).get("cache_hits", 0))
            misses = max(0, completed - hits)
            summary = f"Ready: {len(self.profiles)}/{self.total_states} pose(s) analyzed; {hits} cache hit(s), {misses} miss(es)"
            if self.failures:
                summary += f"; {len(self.failures)} failure(s)"
            self.status_changed.emit(summary)
        except Exception as exc:
            message = f"Could not render PLIP overlays: {exc}"
            self.status_changed.emit(message)
            self.error_occurred.emit(message)
        finally:
            if bundle is not None:
                bundle.cleanup()
            if process is not None:
                process.deleteLater()
            self._pending_profiles = {}
            self._pending_failures = {}
            self.running_changed.emit(False)

    def _resolve_types(self, types: str) -> list[str]:
        value = types.strip().lower()
        if value == "all":
            return list(INTERACTION_TYPES)
        resolved: list[str] = []
        for token in value.replace(";", ",").split(","):
            token = token.strip().lower().replace("-", "_").replace(" ", "_")
            if not token:
                continue
            token = TYPE_ALIASES.get(token, token)
            if token not in INTERACTION_TYPES:
                allowed = ", ".join(INTERACTION_TYPES)
                raise ValueError(f"Unknown interaction type {token!r}; choose from {allowed}")
            if token not in resolved:
                resolved.append(token)
        if not resolved:
            raise ValueError("No interaction types were specified")
        return resolved

    def toggle(self, *, types: str = "all", enabled: str = "toggle") -> None:
        targets = self._resolve_types(types)
        mode = enabled.strip().lower()
        if mode not in {"toggle", "on", "off", "1", "0", "true", "false", "yes", "no"}:
            raise ValueError("enabled must be toggle, on, or off")
        for name in targets:
            if mode == "toggle":
                desired = not self.type_preferences[name]
            else:
                desired = mode in {"on", "1", "true", "yes"}
            self.type_preferences[name] = desired
            if self.run is not None:
                object_name = self.run.object_names[name]
                if object_name in self.cmd.get_names("all"):
                    (self.cmd.enable if desired else self.cmd.disable)(object_name)
        self.profiles_changed.emit()

    def type_enabled(self, name: str) -> bool:
        if self.run is not None and self.run.object_names[name] in self.cmd.get_names("all"):
            try:
                return interaction_enabled(self.cmd, self.run, name)
            except Exception:
                pass
        return self.type_preferences[name]

    def set_pocket_mode(self, mode: Any) -> None:
        self.pocket_mode = normalize_pocket_mode(mode)
        self._render_pocket()
        self.profiles_changed.emit()

    def set_pocket_enabled(self, enabled: bool) -> None:
        """Beta 0.1 API compatibility wrapper."""
        self.set_pocket_mode("current" if enabled else "off")

    def clear(self) -> None:
        delete_run(self.cmd, self.run)
        self.run = None
        self.profiles = {}
        self.failures = {}
        self.active_receptor_selection = ""
        self.active_ligand_object = ""
        self.total_states = 0
        self._last_state = None
        self.status_changed.emit("Plugin-owned overlays cleared.")
        self.profiles_changed.emit()

    def cache_stats(self) -> tuple[int, int, Path]:
        cache = ProfileCache()
        count, size = cache.stats()
        return count, size, cache.root

    def clear_cache(self) -> None:
        ProfileCache().clear()

    def current_counts(self) -> tuple[dict[str, int], dict[str, int]]:
        current = max(1, int(self.cmd.get_state()))
        if self.total_states:
            current = min(current, self.total_states)
        current_profile = self.profiles.get(current)
        current_counts = (
            interaction_counts(current_profile)
            if current_profile is not None
            else {name: 0 for name in INTERACTION_TYPES}
        )
        totals = {
            name: sum(len(profile["interactions"].get(name, ())) for profile in self.profiles.values())
            for name in INTERACTION_TYPES
        }
        return current_counts, totals

    def current_status(self) -> tuple[int, str, bool]:
        state = max(1, int(self.cmd.get_state()))
        if self.active_ligand_object and self.active_ligand_object in self.cmd.get_names("objects"):
            state = min(state, max(1, int(self.cmd.count_states(self.active_ligand_object))))
            title = clean_state_title(self.cmd.get_title(self.active_ligand_object, state), state=state)
        else:
            title = self._last_title or f"State {state}"
        return state, title, state in self.profiles

    def _poll_state(self) -> None:
        state, title, analyzed = self.current_status()
        source_exists = (
            not self.active_ligand_object
            or self.active_ligand_object in self.cmd.get_names("objects")
        )
        if not source_exists and self.run is not None:
            title = "Source ligand object was deleted"
            analyzed = False
        if state != self._last_state or title != self._last_title:
            self._last_state = state
            self._last_title = title
            self.state_changed.emit(state, title, analyzed)

    def _render_pocket(self) -> None:
        if self.run is None:
            return
        try:
            render_pocket(
                self.cmd,
                run=self.run,
                receptor_selection=self.active_receptor_selection,
                receptor_state=self.active_receptor_state,
                profiles=self.profiles,
                total_states=self.total_states,
                mode=self.pocket_mode,
            )
        except Exception as exc:
            self.status_changed.emit(f"Interaction overlays are ready, but pocket display failed: {exc}")

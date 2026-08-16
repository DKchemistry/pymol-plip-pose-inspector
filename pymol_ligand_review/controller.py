"""Main-thread orchestration for PyMOL, Qt, and the external RDKit worker."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from pymol.Qt import QtCore

from .cache import DepictionCache
from .constants import WORKER_ENV_NAME
from .exporting import ExportBundle, clean_state_title, export_bundle, resolve_single_object
from .selection import SelectionStore

Signal = getattr(QtCore, "Signal", QtCore.pyqtSignal)


class LigandReviewController(QtCore.QObject):
    status_changed = Signal(str)
    objects_changed = Signal(object)
    running_changed = Signal(bool)
    progress_changed = Signal(int, int, int, int)
    records_changed = Signal()
    state_changed = Signal(int, str, object)
    selection_changed = Signal()
    error_occurred = Signal(str)

    def __init__(self, cmd: Any):
        super().__init__()
        self.cmd = cmd
        self.settings = QtCore.QSettings("PyMOL Ligand Review", "Ligand Review Panel")
        self.process: QtCore.QProcess | None = None
        self.bundle: ExportBundle | None = None
        self.active_selection = ""
        self.active_ligand_object = ""
        self.total_states = 0
        self.records: dict[int, dict[str, Any]] = {}
        self.failures: dict[int, str] = {}
        self.engine: dict[str, str] = {}
        self.selections = SelectionStore()

        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._complete_event: dict[str, Any] | None = None
        self._cancelled = False
        self._last_state_key: tuple[Any, ...] | None = None
        self._health_cache: dict[str, tuple[bool, str, dict[str, str]]] = {}

        self.state_timer = QtCore.QTimer(self)
        self.state_timer.setInterval(125)
        self.state_timer.timeout.connect(self._poll_state)
        self.state_timer.start()

    @property
    def worker_script(self) -> Path:
        return Path(__file__).with_name("worker.py")

    @property
    def is_running(self) -> bool:
        return self.process is not None

    def molecular_objects(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for name in self.cmd.get_names("objects"):
            try:
                if name.startswith("PLIP_Pose_Inspector_"):
                    continue
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

    def worker_python_candidates(self) -> list[Path]:
        configured = str(self.settings.value("worker_python", "") or "").strip()
        environment = os.environ.get("PYMOL_LIGAND_REVIEW_PYTHON", "").strip()
        home = Path.home()
        values = [Path(value).expanduser() for value in (configured, environment) if value]
        values.extend(
            root / "envs" / WORKER_ENV_NAME / "bin" / "python"
            for root in (
                home / "miniconda3",
                home / "miniforge3",
                home / "mambaforge",
                home / "anaconda3",
            )
        )
        values.append(Path(sys.executable))
        unique: list[Path] = []
        for path in values:
            if path not in unique:
                unique.append(path)
        return unique

    def set_worker_python(self, value: str) -> None:
        self.settings.setValue("worker_python", str(Path(value).expanduser()) if value else "")
        self._health_cache.clear()

    def health_check(self, python_path: str | Path | None = None) -> tuple[bool, str, dict[str, str]]:
        path = Path(python_path).expanduser() if python_path else self.worker_python(resolve=False)
        cache_key = str(path)
        if cache_key in self._health_cache:
            return self._health_cache[cache_key]
        if not path.is_file():
            result = (False, f"Python executable does not exist: {path}", {})
            self._health_cache[cache_key] = result
            return result
        try:
            completed = subprocess.run(
                [str(path), str(self.worker_script), "--health"],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
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
                    f"Ready: RDKit {engine.get('rdkit', '?')}, Python {engine.get('python', '?')}",
                    engine,
                )
            else:
                detail = event.get("error") or completed.stderr.strip() or completed.stdout.strip()
                result = (False, detail or f"Worker exited with status {completed.returncode}", {})
        except Exception as exc:
            result = (False, str(exc), {})
        self._health_cache[cache_key] = result
        return result

    def worker_python(self, *, resolve: bool = True) -> Path:
        candidates = self.worker_python_candidates()
        if not resolve:
            return candidates[0]
        configured = str(self.settings.value("worker_python", "") or "").strip()
        if configured:
            path = Path(configured).expanduser()
            ok, message, _engine = self.health_check(path)
            if not ok:
                raise FileNotFoundError(f"Configured worker is unavailable: {message}")
            return path
        for candidate in candidates:
            if not candidate.is_file():
                continue
            ok, _message, _engine = self.health_check(candidate)
            if ok:
                return candidate
        searched = "\n".join(f"  {path}" for path in candidates)
        raise FileNotFoundError(
            f"Could not find a Python environment containing RDKit. Searched:\n{searched}\n"
            "Create the pymol-ligand-review environment or configure its Python in Settings."
        )

    def attach(self, ligand: str, *, force: bool = False) -> None:
        ligand = str(ligand).strip()
        if self.is_running:
            raise RuntimeError("Depictions are already being generated; cancel before changing ligand")
        ligand_object = resolve_single_object(self.cmd, ligand)
        total = int(self.cmd.count_states(ligand_object))
        if (
            not force
            and ligand == self.active_selection
            and ligand_object == self.active_ligand_object
            and total == self.total_states
            and len(self.records) + len(self.failures) == total
        ):
            self._last_state_key = None
            self._poll_state()
            return
        worker = self.worker_python()
        bundle = export_bundle(self.cmd, ligand)
        self.active_selection = ligand
        self.active_ligand_object = bundle.ligand_object
        self.total_states = bundle.total_states
        self.records = {}
        self.failures = {}
        self.bundle = bundle
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._complete_event = None
        self._cancelled = False
        self._last_state_key = None

        process = QtCore.QProcess(self)
        self.process = process
        process.setProgram(str(worker))
        process.setArguments([str(self.worker_script), str(bundle.manifest_path)])
        environment = QtCore.QProcessEnvironment.systemEnvironment()
        root = str(self.worker_script.parent.parent)
        previous = environment.value("PYTHONPATH")
        environment.insert("PYTHONPATH", root + (os.pathsep + previous if previous else ""))
        environment.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(environment)
        process.setProcessChannelMode(QtCore.QProcess.SeparateChannels)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.errorOccurred.connect(self._process_error)
        process.finished.connect(self._process_finished)
        self.running_changed.emit(True)
        self.progress_changed.emit(0, bundle.total_states, 0, 0)
        self.records_changed.emit()
        self.status_changed.emit(f"Generating {bundle.total_states} RDKit depiction(s)…")
        process.start()

    def cancel(self) -> None:
        if self.process is None:
            return
        self._cancelled = True
        self.status_changed.emit("Cancelling depiction generation…")
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
            self._stderr_buffer += bytes(self.process.readAllStandardError()).decode(
                "utf-8", "replace"
            )
            self._stderr_buffer = self._stderr_buffer[-131_072:]

    def _handle_event(self, event: dict[str, Any]) -> None:
        kind = event.get("event")
        if kind == "started":
            self.engine = dict(event.get("engine", {}))
            self.records_changed.emit()
        elif kind == "depiction":
            state = int(event["state"])
            self.records[state] = event
            self.failures.pop(state, None)
            self.selections.register(event)
            self.records_changed.emit()
            self._last_state_key = None
        elif kind == "failure":
            self.failures[int(event["state"])] = str(event.get("error", "Unknown error"))
            self.records_changed.emit()
            self._last_state_key = None
        elif kind == "progress":
            self.progress_changed.emit(
                int(event.get("completed", 0)),
                int(event.get("total", self.total_states)),
                int(event.get("cache_hits", 0)),
                int(event.get("failures", len(self.failures))),
            )
        elif kind == "complete":
            self._complete_event = event
        elif kind == "fatal":
            self.failures[0] = str(event.get("error", "RDKit worker failed"))

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

    def _process_finished(self, exit_code: int, _exit_status: Any) -> None:
        process = self.process
        if process is not None:
            self._read_stdout()
            self._read_stderr()
        bundle = self.bundle
        self.process = None
        self.bundle = None
        try:
            if self._cancelled:
                self.status_changed.emit(
                    f"Generation cancelled; {len(self.records)} completed depiction(s) remain available."
                )
            elif int(exit_code) != 0 and not self.records:
                detail = self.failures.get(0) or self._stderr_buffer.strip()
                message = detail or f"RDKit worker exited with status {exit_code}"
                self.status_changed.emit(message)
                self.error_occurred.emit(message)
            else:
                hits = int((self._complete_event or {}).get("cache_hits", 0))
                misses = max(0, len(self.records) - hits)
                summary = (
                    f"Ready: {len(self.records)}/{self.total_states} depiction(s); "
                    f"{hits} cache hit(s), {misses} new"
                )
                if self.failures:
                    summary += f"; {len([s for s in self.failures if s > 0])} failure(s)"
                self.status_changed.emit(summary)
        finally:
            if bundle is not None:
                bundle.cleanup()
            if process is not None:
                process.deleteLater()
            self.running_changed.emit(False)
            self.records_changed.emit()
            self._last_state_key = None
            self._poll_state()

    def current_state(self) -> int:
        state = max(1, int(self.cmd.get_state()))
        if self.total_states:
            state = min(state, self.total_states)
        return state

    def current_record(self) -> dict[str, Any] | None:
        return self.records.get(self.current_state())

    def current_title(self) -> str:
        state = self.current_state()
        if self.active_ligand_object in self.cmd.get_names("objects"):
            return clean_state_title(self.cmd.get_title(self.active_ligand_object, state), state=state)
        return "Source ligand object was deleted"

    def _poll_state(self) -> None:
        state = self.current_state()
        title = self.current_title() if self.active_ligand_object else f"State {state}"
        record = self.records.get(state)
        key = (
            state,
            title,
            record.get("image_path") if record else None,
            self.selections.is_selected(record["identity_key"]) if record else False,
        )
        if key != self._last_state_key:
            self._last_state_key = key
            self.state_changed.emit(state, title, record)

    def previous_state(self) -> None:
        self.cmd.frame(max(1, self.current_state() - 1))
        self._last_state_key = None
        self._poll_state()

    def next_state(self) -> None:
        self.cmd.frame(min(max(1, self.total_states), self.current_state() + 1))
        self._last_state_key = None
        self._poll_state()

    def mark_current(self, *, enabled: str = "toggle", name: str = "", identifier: str = "") -> bool:
        record = self.current_record()
        if record is None:
            raise ValueError("The current state has no valid RDKit depiction")
        key = str(record["identity_key"])
        mode = str(enabled).strip().lower()
        if mode not in {"toggle", "on", "off", "1", "0", "true", "false", "yes", "no"}:
            raise ValueError("enabled must be toggle, on, or off")
        desired = not self.selections.is_selected(key) if mode == "toggle" else mode in {
            "on",
            "1",
            "true",
            "yes",
        }
        if desired:
            self.selections.mark(record, name=name, identifier=identifier)
        else:
            self.selections.unmark(key)
        self.selection_changed.emit()
        self._last_state_key = None
        self._poll_state()
        return desired

    def update_selection(self, key: str, *, name: str | None = None, identifier: str | None = None) -> None:
        self.selections.update(key, name=name, identifier=identifier)
        self.selection_changed.emit()

    def remove_selection(self, key: str) -> None:
        self.selections.unmark(key)
        self.selection_changed.emit()
        self._last_state_key = None
        self._poll_state()

    def clear_selections(self) -> None:
        self.selections.clear()
        self.selection_changed.emit()
        self._last_state_key = None
        self._poll_state()

    def export_csv(self, filename: str) -> int:
        count = self.selections.export_csv(filename)
        self.status_changed.emit(f"Exported {count} selected compound(s) to {filename}")
        return count

    def jump_to(self, ligand_object: str, state: int) -> None:
        self.cmd.frame(max(1, int(state)))
        if ligand_object != self.active_ligand_object:
            self.attach(ligand_object)
        self._last_state_key = None
        self._poll_state()

    def cache_stats(self) -> tuple[int, int, Path]:
        cache = DepictionCache()
        count, size = cache.stats()
        return count, size, cache.root

    def clear_cache(self) -> None:
        if self.is_running:
            raise RuntimeError("Cancel depiction generation before clearing the cache")
        DepictionCache().clear()

"""Shared PyMOL object discovery, ligand selection, and state observation."""

from __future__ import annotations

import re
from typing import Any

from pymol.Qt import QtCore

Signal = getattr(QtCore, "Signal", QtCore.pyqtSignal)


class WorkspaceError(ValueError):
    """Raised when a PyMOL selection cannot be used as a ligand."""


def clean_state_title(value: Any, *, state: int) -> str:
    title = str(value or "").strip()
    title = re.sub(r"(?:\s+|^)none$", "", title, flags=re.IGNORECASE).strip()
    return title or f"State {state}"


def resolve_single_object(cmd: Any, selection: str) -> str:
    selection = str(selection).strip()
    if not selection:
        raise WorkspaceError("Choose a ligand object or selection")
    try:
        objects = cmd.get_object_list(f"({selection})")
    except Exception as exc:
        raise WorkspaceError(f"Invalid ligand selection: {selection}") from exc
    if len(objects) != 1:
        raise WorkspaceError(
            "Ligand selection must resolve to exactly one molecular object; "
            f"found {len(objects)}"
        )
    return objects[0]


def ordered_states(current: int, total: int) -> list[int]:
    current = max(1, min(int(current), int(total)))
    return [current] + [state for state in range(1, total + 1) if state != current]


def molecular_objects(cmd: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name in cmd.get_names("objects"):
        try:
            if name.startswith("PLIP_Pose_Inspector_"):
                continue
            if cmd.get_type(name) != "object:molecule":
                continue
            result.append(
                {
                    "name": name,
                    "states": int(cmd.count_states(name)),
                    "atoms": int(cmd.count_atoms(name)),
                    "protein_atoms": int(
                        cmd.count_atoms(f"({name}) and polymer.protein")
                    ),
                }
            )
        except Exception:
            continue
    return result


class WorkspaceSession(QtCore.QObject):
    """One state watcher and one active ligand shared by every plugin window."""

    state_changed = Signal(int, str)
    ligand_changed = Signal(str, str, int)
    objects_changed = Signal(object)

    def __init__(self, cmd: Any, *, interval: int = 125):
        super().__init__()
        self.cmd = cmd
        self.active_selection = ""
        self.active_ligand_object = ""
        self.total_states = 0
        self._last_state_key: tuple[Any, ...] | None = None
        self.state_timer = QtCore.QTimer(self)
        self.state_timer.setInterval(int(interval))
        self.state_timer.timeout.connect(self._poll_state)
        self.state_timer.start()

    def objects(self) -> list[dict[str, Any]]:
        objects = molecular_objects(self.cmd)
        self.objects_changed.emit(objects)
        return objects

    def set_ligand(self, selection: str) -> tuple[str, int]:
        selection = str(selection).strip()
        ligand_object = resolve_single_object(self.cmd, selection)
        total = int(self.cmd.count_states(ligand_object))
        if total < 1:
            raise WorkspaceError("Ligand object has no states")
        changed = (
            selection != self.active_selection
            or ligand_object != self.active_ligand_object
            or total != self.total_states
        )
        self.active_selection = selection
        self.active_ligand_object = ligand_object
        self.total_states = total
        self._last_state_key = None
        if changed:
            self.ligand_changed.emit(selection, ligand_object, total)
        self._poll_state()
        return ligand_object, total

    def ligand_info(self, selection: str = "") -> tuple[str, int, int, str]:
        selection = str(selection).strip() or self.active_selection
        try:
            name = resolve_single_object(self.cmd, selection)
            total = int(self.cmd.count_states(name))
            state = max(1, min(int(self.cmd.get_state()), total))
            title = clean_state_title(self.cmd.get_title(name, state), state=state)
            return name, total, state, title
        except Exception:
            return "", 0, max(1, int(self.cmd.get_state())), ""

    def current_state(self) -> int:
        state = max(1, int(self.cmd.get_state()))
        if self.total_states:
            state = min(state, self.total_states)
        return state

    def current_title(self) -> str:
        state = self.current_state()
        if self.active_ligand_object in self.cmd.get_names("objects"):
            return clean_state_title(
                self.cmd.get_title(self.active_ligand_object, state), state=state
            )
        return "Source ligand object was deleted" if self.active_ligand_object else f"State {state}"

    def _poll_state(self) -> None:
        state = self.current_state()
        title = self.current_title()
        key = (state, title, self.active_ligand_object, self.total_states)
        if key != self._last_state_key:
            self._last_state_key = key
            self.state_changed.emit(state, title)


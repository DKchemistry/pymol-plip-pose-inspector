# Name: PLIP Pose Inspector
# Version: 0.1.0
# Citation-Required: Yes
"""PyMOL entry point for PLIP Pose Inspector.

Imports are intentionally lazy so the external PLIP worker can import shared
modules without having PyMOL installed in its environment.
"""

from __future__ import annotations

from .constants import PLUGIN_VERSION as __version__

_controller = None
_dialog = None
_initialized = False


def _as_bool(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "on", "true", "yes"}:
            return True
        if normalized in {"0", "off", "false", "no"}:
            return False
    return bool(int(value))


def get_controller():
    global _controller
    if _controller is None:
        from pymol import cmd

        from .controller import PoseInspectorController

        _controller = PoseInspectorController(cmd)
    return _controller


def plip_gui():
    global _dialog
    from .dialog import PoseInspectorDialog

    controller = get_controller()
    if _dialog is None:
        _dialog = PoseInspectorDialog(controller)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
    return _dialog


def plip_analyze(
    receptor,
    ligand,
    states="all",
    receptor_state=0,
    filtered=1,
    pocket=1,
):
    controller = get_controller()
    return controller.analyze(
        receptor=str(receptor),
        ligand=str(ligand),
        states=states,
        receptor_state=int(receptor_state),
        filtered=_as_bool(filtered),
        pocket=_as_bool(pocket),
    )


def plip_toggle(types="all", enabled="toggle"):
    return get_controller().toggle(types=str(types), enabled=str(enabled))


def plip_clear():
    return get_controller().clear()


def __init_plugin__(app=None):
    global _initialized
    if _initialized:
        return
    from pymol import cmd
    from pymol.plugins import addmenuitemqt

    cmd.extend("plip_gui", plip_gui)
    cmd.extend("plip_analyze", plip_analyze)
    cmd.extend("plip_toggle", plip_toggle)
    cmd.extend("plip_clear", plip_clear)
    addmenuitemqt("PLIP Pose Inspector", plip_gui)
    _initialized = True

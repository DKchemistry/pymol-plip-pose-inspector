# Name: PLIP Pose Inspector
# Version: 0.4.0
# Citation: Adasme et al. (2021), doi:10.1093/nar/gkab294; Salentin et al. (2015), doi:10.1093/nar/gkv315
"""PyMOL entry point for PLIP Pose Inspector.

Imports are intentionally lazy so the external PLIP worker can import shared
modules without having PyMOL installed in its environment.

Interaction perception is provided by PLIP. Please cite: Salentin et al.,
PLIP: fully automated protein-ligand interaction profiler, Nucleic Acids
Research 43(W1), W443-W447 (2015), doi:10.1093/nar/gkv315.
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
    from pymol.Qt import QtCore

    QtCore.QTimer.singleShot(0, _dialog.show_citation_once)
    return _dialog


def plip_analyze(
    receptor,
    ligand,
    states="all",
    receptor_state=0,
    filtered=1,
    pocket="current",
):
    controller = get_controller()
    return controller.analyze(
        receptor=str(receptor),
        ligand=str(ligand),
        states=states,
        receptor_state=int(receptor_state),
        filtered=_as_bool(filtered),
        pocket=pocket,
    )


def plip_toggle(types="all", enabled="toggle"):
    return get_controller().toggle(types=str(types), enabled=str(enabled))


def plip_clear():
    return get_controller().clear()


def plip_pocket(mode="current", ligand=""):
    return get_controller().set_pocket_mode(mode, str(ligand))


def plip_2d(ligand=""):
    """Open the optional Ligand Review Panel on this run's ligand."""
    ligand = str(ligand).strip()
    controller = get_controller()
    if not ligand:
        ligand = controller.active_ligand_object
    if not ligand and _dialog is not None:
        ligand = _dialog.ligand.currentText().strip()
    if not ligand:
        raise ValueError("Choose a ligand object before opening the 2D reviewer")
    try:
        import pymol_ligand_review
    except ImportError as exc:
        raise RuntimeError(
            "Ligand Review Panel is not installed. Install its PyMOL Plugin Manager ZIP, "
            "then reopen this action."
        ) from exc
    return pymol_ligand_review.ligand_review_gui(ligand)


def __init_plugin__(app=None):
    global _initialized
    if _initialized:
        return
    from pymol import cmd
    from pymol.plugins import addmenuitemqt

    cmd.extend("plip_gui", plip_gui)
    cmd.extend("plip_analyze", plip_analyze)
    cmd.extend("plip_toggle", plip_toggle)
    cmd.extend("plip_pocket", plip_pocket)
    cmd.extend("plip_2d", plip_2d)
    cmd.extend("plip_clear", plip_clear)
    addmenuitemqt("PLIP Pose Inspector", plip_gui)
    _initialized = True

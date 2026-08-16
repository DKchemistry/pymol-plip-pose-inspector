# Name: PyMOL Pose Inspector
# Version: 0.5.0
# Citation: Adasme et al. (2021), doi:10.1093/nar/gkab294; Salentin et al. (2015), doi:10.1093/nar/gkv315
"""PyMOL entry point for state-aware interaction and ligand review."""

from __future__ import annotations

from .constants import PLUGIN_VERSION as __version__

_application = None
_initialized = False


def _as_bool(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "on", "true", "yes"}:
            return True
        if normalized in {"0", "off", "false", "no"}:
            return False
    return bool(int(value))


def get_application():
    global _application
    if _application is None:
        from pymol import cmd

        from .application import PoseInspectorApplication

        _application = PoseInspectorApplication(cmd)
    return _application


def get_controller():
    return get_application().plip_controller


def get_review_controller():
    return get_application().review_controller


def pose_inspector_gui():
    return get_application().show_main()


def plip_gui():
    return pose_inspector_gui()


def plip_analyze(
    receptor,
    ligand,
    states="all",
    receptor_state=0,
    filtered=1,
    pocket="current",
):
    return get_controller().analyze(
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


def ligand_review_gui(ligand=""):
    return get_application().show_review(str(ligand))


def plip_2d(ligand=""):
    ligand = str(ligand).strip()
    application = get_application()
    if not ligand:
        ligand = application.session.active_selection or get_controller().active_ligand_object
    if not ligand:
        raise ValueError("Choose a ligand object before opening the 2D reviewer")
    return application.show_review(ligand)


def ligand_review_attach(ligand):
    return get_review_controller().attach(str(ligand), force=True)


def ligand_review_mark(enabled="toggle", name="", identifier=""):
    return get_review_controller().mark_current(
        enabled=str(enabled), name=str(name), identifier=str(identifier)
    )


def ligand_review_export(filename):
    return get_review_controller().export_csv(str(filename))


def ligand_review_clear():
    return get_review_controller().clear_selections()


def __init_plugin__(app=None):
    global _initialized
    if _initialized:
        return
    from pymol import cmd
    from pymol.plugins import addmenuitemqt

    commands = {
        "pose_inspector_gui": pose_inspector_gui,
        "plip_gui": plip_gui,
        "plip_analyze": plip_analyze,
        "plip_toggle": plip_toggle,
        "plip_pocket": plip_pocket,
        "plip_2d": plip_2d,
        "plip_clear": plip_clear,
        "ligand_review_gui": ligand_review_gui,
        "ligand_review_attach": ligand_review_attach,
        "ligand_review_mark": ligand_review_mark,
        "ligand_review_export": ligand_review_export,
        "ligand_review_clear": ligand_review_clear,
    }
    for name, function in commands.items():
        cmd.extend(name, function)
    addmenuitemqt("PyMOL Pose Inspector", pose_inspector_gui)
    _initialized = True

# Name: Ligand Review Panel
# Version: 0.1.0
"""PyMOL entry point for state-synchronized RDKit ligand review."""

from __future__ import annotations

from .constants import PLUGIN_VERSION as __version__

_controller = None
_dialog = None
_initialized = False


def get_controller():
    global _controller
    if _controller is None:
        from pymol import cmd

        from .controller import LigandReviewController

        _controller = LigandReviewController(cmd)
    return _controller


def ligand_review_gui(ligand=""):
    global _dialog
    from .dialog import LigandReviewDialog

    controller = get_controller()
    if _dialog is None:
        _dialog = LigandReviewDialog(controller)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
    if str(ligand).strip():
        _dialog.attach_ligand(str(ligand))
    return _dialog


def ligand_review_attach(ligand):
    return get_controller().attach(str(ligand), force=True)


def ligand_review_mark(enabled="toggle", name="", identifier=""):
    return get_controller().mark_current(
        enabled=str(enabled), name=str(name), identifier=str(identifier)
    )


def ligand_review_export(filename):
    return get_controller().export_csv(str(filename))


def ligand_review_clear():
    return get_controller().clear_selections()


def __init_plugin__(app=None):
    global _initialized
    if _initialized:
        return
    from pymol import cmd
    from pymol.plugins import addmenuitemqt

    cmd.extend("ligand_review_gui", ligand_review_gui)
    cmd.extend("ligand_review_attach", ligand_review_attach)
    cmd.extend("ligand_review_mark", ligand_review_mark)
    cmd.extend("ligand_review_export", ligand_review_export)
    cmd.extend("ligand_review_clear", ligand_review_clear)
    addmenuitemqt("Ligand Review Panel", ligand_review_gui)
    _initialized = True


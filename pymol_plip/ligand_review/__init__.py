"""Integrated Ligand Review Panel compatibility API."""

from __future__ import annotations

from ..constants import PLUGIN_VERSION as __version__


def get_controller():
    from pymol_plip import get_review_controller

    return get_review_controller()


def ligand_review_gui(ligand=""):
    from pymol_plip import ligand_review_gui as launch

    return launch(ligand)


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


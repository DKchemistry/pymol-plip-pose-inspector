#!/usr/bin/env python3
"""Headless PyMOL integration test for real multi-state SDF data."""

from __future__ import annotations

import argparse
import csv
import json
import resource
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pymol import cmd
from pymol.Qt import QtCore, QtGui, QtWidgets

from pymol_plip.ligand_review.controller import LigandReviewController


FIRST_EP4_SMILES = "O=C(NC(=S)Nc1ccc(O)c(C(=O)[O-])c1)c1ccc2ccccc2c1"


def wait_for(controller: LigandReviewController, app: QtWidgets.QApplication, timeout=90.0):
    started = time.perf_counter()
    while controller.is_running and time.perf_counter() - started < timeout:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    if controller.is_running:
        controller.cancel()
        raise TimeoutError("RDKit worker timed out")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ligands", type=Path, required=True)
    parser.add_argument("--worker-python", type=Path, required=True)
    parser.add_argument("--expected-states", type=int, required=True)
    parser.add_argument("--cancel", action="store_true")
    args = parser.parse_args()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    cmd.reinitialize()
    cmd.load(str(args.ligands), "poses")
    atom_count = cmd.count_atoms("poses")
    bond_count = len(cmd.get_model("poses", 1).bond)
    controller = LigandReviewController(cmd)
    controller.set_worker_python(str(args.worker_python))
    statuses: list[str] = []
    states_seen: list[int] = []
    controller.status_changed.connect(statuses.append)
    controller.state_changed.connect(lambda state, _title, _record: states_seen.append(state))

    started = time.perf_counter()
    controller.attach("poses")
    if args.cancel:
        deadline = time.perf_counter() + 5
        while not controller.records and controller.is_running and time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(0.005)
        controller.cancel()
        wait_for(controller, app)
        assert cmd.count_atoms("poses") == atom_count
        print(json.dumps({"cancelled": True, "completed_before_cancel": len(controller.records)}))
        controller.state_timer.stop()
        return
    wait_for(controller, app)
    cold = time.perf_counter() - started
    assert len(controller.records) == args.expected_states, controller.failures
    assert not controller.failures, controller.failures
    assert controller.records[1]["smiles"] == FIRST_EP4_SMILES
    assert controller.records[1]["title"] == "ZINC000020152257"
    assert all(Path(record["image_path"]).is_file() for record in controller.records.values())
    try:
        from rdkit import Chem
    except ImportError:
        Chem = None
    if Chem is not None:
        direct = [mol for mol in Chem.SDMolSupplier(str(args.ligands), removeHs=True) if mol]
        assert len(direct) == args.expected_states
        for state, molecule in enumerate(direct, 1):
            expected = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
            assert controller.records[state]["smiles"] == expected, state
    pixmap = QtGui.QPixmap(controller.records[1]["image_path"])
    assert not pixmap.isNull() and pixmap.size() == QtCore.QSize(600, 400)

    for state in (1, min(2, args.expected_states), args.expected_states):
        cmd.frame(state)
        controller._poll_state()
        assert controller.current_state() == state
        assert controller.current_record()["state"] == state
    assert not controller.is_running

    cmd.frame(1)
    controller.mark_current(enabled="on", name="Chosen, compound", identifier="BUY-001")
    with tempfile.TemporaryDirectory() as directory:
        csv_path = Path(directory) / "chosen.csv"
        assert controller.export_csv(str(csv_path)) == 1
        with csv_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["name"] == "Chosen, compound"
        assert rows[0]["identifier"] == "BUY-001"
        assert rows[0]["smiles"] == FIRST_EP4_SMILES

    started = time.perf_counter()
    controller.attach("poses", force=True)
    wait_for(controller, app)
    warm = time.perf_counter() - started
    assert len(controller.records) == args.expected_states
    assert cmd.count_atoms("poses") == atom_count
    assert len(cmd.get_model("poses", 1).bond) == bond_count
    print(
        json.dumps(
            {
                "states": len(controller.records),
                "cold_seconds": round(cold, 3),
                "warm_seconds": round(warm, 3),
                "selected": len(controller.selections.selected),
                "max_rss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "last_status": statuses[-1],
            },
            sort_keys=True,
        )
    )
    controller.state_timer.stop()


if __name__ == "__main__":
    main()

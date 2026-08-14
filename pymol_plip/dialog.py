"""Nonmodal Qt interface for PLIP Pose Inspector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pymol.Qt import QtCore, QtWidgets

from .constants import INTERACTION_LABELS, INTERACTION_TYPES


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, controller: Any, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("PLIP Pose Inspector Settings")
        self.setModal(False)
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        path_row = QtWidgets.QHBoxLayout()
        self.python_path = QtWidgets.QLineEdit()
        candidates = controller.worker_python_candidates()
        current = str(controller.settings.value("worker_python", "") or "")
        if not current:
            current = next((str(path) for path in candidates if path.is_file()), "")
        self.python_path.setText(current)
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.python_path, 1)
        path_row.addWidget(browse)
        form.addRow("Worker Python", path_row)
        layout.addLayout(form)

        self.health = QtWidgets.QLabel("Not checked")
        self.health.setWordWrap(True)
        layout.addWidget(self.health)
        test_button = QtWidgets.QPushButton("Test Worker")
        test_button.clicked.connect(self._test)
        layout.addWidget(test_button)

        self.cache = QtWidgets.QLabel()
        self.cache.setWordWrap(True)
        layout.addWidget(self.cache)
        clear_cache = QtWidgets.QPushButton("Clear Persistent Cache…")
        clear_cache.clicked.connect(self._clear_cache)
        layout.addWidget(clear_cache)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Close
        )
        buttons.button(QtWidgets.QDialogButtonBox.Save).clicked.connect(self._save)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        self._refresh_cache()

    def _browse(self) -> None:
        value, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select worker Python", self.python_path.text() or str(Path.home())
        )
        if value:
            self.python_path.setText(value)

    def _save(self) -> None:
        self.controller.set_worker_python(self.python_path.text().strip())
        self.health.setText("Worker path saved.")

    def _test(self) -> None:
        path = self.python_path.text().strip() or None
        ok, message, _engine = self.controller.health_check(path)
        self.health.setText(("✓ " if ok else "✗ ") + message)
        if ok and path:
            self.controller.set_worker_python(path)

    def _refresh_cache(self) -> None:
        count, size, root = self.controller.cache_stats()
        self.cache.setText(f"Cache: {count} profile(s), {size / (1024 * 1024):.2f} MiB\n{root}")

    def _clear_cache(self) -> None:
        answer = QtWidgets.QMessageBox.question(
            self,
            "Clear PLIP cache",
            "Delete all cached PLIP pose profiles? Existing PyMOL overlays are unaffected.",
        )
        if answer == QtWidgets.QMessageBox.Yes:
            self.controller.clear_cache()
            self._refresh_cache()


class PoseInspectorDialog(QtWidgets.QDialog):
    def __init__(self, controller: Any):
        super().__init__()
        self.controller = controller
        self._settings_dialog: SettingsDialog | None = None
        self.setWindowTitle("PLIP Pose Inspector")
        self.setModal(False)
        self.resize(590, 660)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

        outer = QtWidgets.QVBoxLayout(self)
        selectors = QtWidgets.QGroupBox("Objects and states")
        form = QtWidgets.QFormLayout(selectors)
        self.receptor = QtWidgets.QComboBox()
        self.receptor.setEditable(True)
        self.ligand = QtWidgets.QComboBox()
        self.ligand.setEditable(True)
        self.receptor_state = QtWidgets.QSpinBox()
        self.receptor_state.setRange(0, 9999)
        self.receptor_state.setSpecialValueText("Current when started")
        self.filtered = QtWidgets.QCheckBox(
            "Restrict receptor to protein, solvent, and inorganic atoms"
        )
        self.filtered.setChecked(True)
        self.filtered.setToolTip(
            "Disable this for an advanced receptor selection that deliberately includes cofactors or other organic atoms."
        )
        self.state_count = QtWidgets.QLabel("—")
        self.current_pose = QtWidgets.QLabel("—")
        self.current_pose.setWordWrap(True)
        self.chemistry_status = QtWidgets.QLabel("Hydrogen policy: —")
        self.chemistry_status.setWordWrap(True)
        form.addRow("Receptor selection", self.receptor)
        form.addRow("Ligand object/selection", self.ligand)
        form.addRow("Fixed receptor state", self.receptor_state)
        form.addRow("", self.filtered)
        form.addRow("Ligand states", self.state_count)
        form.addRow("Current pose", self.current_pose)
        form.addRow("Profile", self.chemistry_status)
        outer.addWidget(selectors)

        actions = QtWidgets.QHBoxLayout()
        self.precompute = QtWidgets.QPushButton("Precompute All")
        self.analyze_current = QtWidgets.QPushButton("Analyze Current")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.refresh_button = QtWidgets.QPushButton("Refresh Objects")
        actions.addWidget(self.precompute)
        actions.addWidget(self.analyze_current)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.refresh_button)
        outer.addLayout(actions)

        interactions_box = QtWidgets.QGroupBox("Interactions")
        interactions = QtWidgets.QGridLayout(interactions_box)
        interactions.addWidget(QtWidgets.QLabel("Visible"), 0, 0)
        interactions.addWidget(QtWidgets.QLabel("Interaction class"), 0, 1)
        interactions.addWidget(QtWidgets.QLabel("Current / total"), 0, 2)
        self.type_checks: dict[str, QtWidgets.QCheckBox] = {}
        self.type_counts: dict[str, QtWidgets.QLabel] = {}
        for row, name in enumerate(INTERACTION_TYPES, 1):
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(controller.type_preferences[name])
            label = QtWidgets.QLabel(INTERACTION_LABELS[name])
            count = QtWidgets.QLabel("0 / 0")
            if name == "hydrophobic_contacts":
                tooltip = (
                    "PLIP hydrophobic contacts; this is not a generic all-atom van der Waals calculation."
                )
                checkbox.setToolTip(tooltip)
                label.setToolTip(tooltip)
            checkbox.toggled.connect(
                lambda checked, interaction_type=name: self._set_interaction(
                    interaction_type, checked
                )
            )
            interactions.addWidget(checkbox, row, 0)
            interactions.addWidget(label, row, 1)
            interactions.addWidget(count, row, 2)
            self.type_checks[name] = checkbox
            self.type_counts[name] = count
        outer.addWidget(interactions_box)

        options = QtWidgets.QHBoxLayout()
        self.all_button = QtWidgets.QPushButton("Show/Hide All")
        self.clear_button = QtWidgets.QPushButton("Clear Overlay")
        self.pocket = QtWidgets.QCheckBox("Show interacting-residue pocket")
        self.pocket.setChecked(True)
        self.settings_button = QtWidgets.QPushButton("Settings…")
        options.addWidget(self.all_button)
        options.addWidget(self.clear_button)
        options.addWidget(self.pocket, 1)
        options.addWidget(self.settings_button)
        outer.addLayout(options)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Idle")
        outer.addWidget(self.progress)
        self.engine_label = QtWidgets.QLabel("Worker not yet checked")
        self.status = QtWidgets.QLabel("Choose a receptor and ligand, then start analysis.")
        self.status.setWordWrap(True)
        outer.addWidget(self.engine_label)
        outer.addWidget(self.status)
        self.failures_box = QtWidgets.QPlainTextEdit()
        self.failures_box.setReadOnly(True)
        self.failures_box.setMaximumHeight(85)
        self.failures_box.setPlaceholderText("Per-state failures will appear here.")
        self.failures_box.hide()
        outer.addWidget(self.failures_box)

        self.precompute.clicked.connect(lambda: self._analyze("all"))
        self.analyze_current.clicked.connect(lambda: self._analyze("current"))
        self.cancel_button.clicked.connect(controller.cancel)
        self.refresh_button.clicked.connect(self.refresh_objects)
        self.ligand.currentTextChanged.connect(self._refresh_ligand_info)
        self.all_button.clicked.connect(self._toggle_all)
        self.clear_button.clicked.connect(controller.clear)
        self.pocket.toggled.connect(controller.set_pocket_enabled)
        self.settings_button.clicked.connect(self._show_settings)

        controller.status_changed.connect(self.status.setText)
        controller.progress_changed.connect(self._progress_changed)
        controller.running_changed.connect(self._running_changed)
        controller.profiles_changed.connect(self._profiles_changed)
        controller.state_changed.connect(self._state_changed)
        controller.error_occurred.connect(self._show_error)

        self.refresh_objects()
        self._profiles_changed()

    def closeEvent(self, event: Any) -> None:
        self.hide()
        event.ignore()

    def refresh_objects(self) -> None:
        receptor_text = self.receptor.currentText().strip()
        ligand_text = self.ligand.currentText().strip()
        objects = self.controller.molecular_objects()
        names = [item["name"] for item in objects]
        if not receptor_text:
            receptor_text = next(
                (item["name"] for item in objects if item["protein_atoms"] > 0),
                names[0] if names else "",
            )
        if not ligand_text:
            ligand_text = next(
                (item["name"] for item in objects if item["states"] > 1),
                next((item["name"] for item in objects if item["protein_atoms"] == 0), ""),
            )
        for combo, value in ((self.receptor, receptor_text), (self.ligand, ligand_text)):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            combo.setEditText(value)
            combo.blockSignals(False)
        self._refresh_ligand_info()

    def _refresh_ligand_info(self) -> None:
        name, total, state, title = self.controller.ligand_info(self.ligand.currentText())
        self.state_count.setText(str(total) if total else "Selection must resolve to one object")
        if total and name == self.controller.active_ligand_object:
            marker = "analyzed" if state in self.controller.profiles else "not analyzed"
            self.current_pose.setText(f"{state}/{total}: {title} ({marker})")
        else:
            self.current_pose.setText(f"{state}/{total}: {title}" if total else "—")

    def _analyze(self, states: str) -> None:
        try:
            self.controller.analyze(
                receptor=self.receptor.currentText(),
                ligand=self.ligand.currentText(),
                states=states,
                receptor_state=self.receptor_state.value(),
                filtered=self.filtered.isChecked(),
                pocket=self.pocket.isChecked(),
            )
        except Exception as exc:
            self._show_error(str(exc))

    def _set_interaction(self, name: str, checked: bool) -> None:
        desired = "on" if checked else "off"
        if self.controller.type_preferences[name] != checked or self.controller.type_enabled(name) != checked:
            self.controller.toggle(types=name, enabled=desired)

    def _toggle_all(self) -> None:
        desired = not any(self.controller.type_enabled(name) for name in INTERACTION_TYPES)
        self.controller.toggle(types="all", enabled="on" if desired else "off")

    def _running_changed(self, running: bool) -> None:
        self.precompute.setEnabled(not running)
        self.analyze_current.setEnabled(not running)
        self.cancel_button.setEnabled(running)

    def _progress_changed(self, completed: int, total: int, hits: int, failures: int) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(completed)
        self.progress.setFormat(
            f"{completed}/{total} poses — {hits} cache hits — {failures} failures"
        )

    def _profiles_changed(self) -> None:
        current, total = self.controller.current_counts()
        for name in INTERACTION_TYPES:
            checkbox = self.type_checks[name]
            checkbox.blockSignals(True)
            checkbox.setChecked(self.controller.type_enabled(name))
            checkbox.blockSignals(False)
            self.type_counts[name].setText(f"{current[name]} / {total[name]}")
        if self.controller.engine:
            self.engine_label.setText(
                f"PLIP {self.controller.engine.get('plip', '?')} / "
                f"OpenBabel {self.controller.engine.get('openbabel', '?')} / "
                f"Python {self.controller.engine.get('python', '?')}"
            )
        state = self.controller.current_status()[0]
        profile = self.controller.profiles.get(state)
        if profile is None:
            self.chemistry_status.setText("Hydrogen policy: — (current pose not analyzed)")
            self.chemistry_status.setToolTip("")
        else:
            policy = (
                "use explicit input hydrogens"
                if profile.get("hydrogen_policy") == "use_input"
                else "PLIP adds missing polar hydrogens"
            )
            warning_count = len(profile.get("warnings", ()))
            suffix = f"; {warning_count} diagnostic message(s)" if warning_count else ""
            self.chemistry_status.setText(f"Hydrogen policy: {policy}{suffix}")
            self.chemistry_status.setToolTip("\n".join(profile.get("warnings", ())))
        if self.controller.failures:
            self.failures_box.setPlainText(
                "\n".join(
                    f"State {state}: {message}"
                    for state, message in sorted(self.controller.failures.items())
                )
            )
            self.failures_box.show()
        else:
            self.failures_box.clear()
            self.failures_box.hide()
        self._refresh_ligand_info()

    def _state_changed(self, state: int, title: str, analyzed: bool) -> None:
        marker = "analyzed" if analyzed else "not analyzed"
        total = self.controller.total_states or self.controller.ligand_info(self.ligand.currentText())[1]
        self.current_pose.setText(f"{state}/{total}: {title} ({marker})")
        self._profiles_changed()

    def _show_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self.controller, self)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _show_error(self, message: str) -> None:
        self.status.setText(message)
        QtWidgets.QMessageBox.warning(self, "PLIP Pose Inspector", message)

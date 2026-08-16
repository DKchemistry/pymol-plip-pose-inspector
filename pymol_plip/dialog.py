"""Nonmodal Qt interface for PLIP Pose Inspector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pymol.Qt import QtCore, QtGui, QtWidgets

from .appearance import PATTERN_LABELS, PATTERNS
from .constants import INTERACTION_LABELS, INTERACTION_TYPES


PLIP_CITATION_TEXT = """If PLIP contributes to published work, please cite one of the references recommended by the PLIP authors:

Adasme, M. F. et al. PLIP 2021: expanding the scope of the protein-ligand interaction profiler to DNA and RNA. Nucleic Acids Research (2021), gkab294. https://doi.org/10.1093/nar/gkab294

Salentin, S. et al. PLIP: fully automated protein-ligand interaction profiler. Nucleic Acids Research 43(W1), W443–W447 (2015). https://doi.org/10.1093/nar/gkv315

PLIP project: https://github.com/pharmai/plip"""


class CitationDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Citing PLIP")
        self.setModal(False)
        self.resize(680, 350)
        layout = QtWidgets.QVBoxLayout(self)
        explanation = QtWidgets.QLabel(
            "Interaction perception in PLIP Pose Inspector is provided by PLIP."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.text = QtWidgets.QPlainTextEdit(PLIP_CITATION_TEXT)
        self.text.setReadOnly(True)
        layout.addWidget(self.text, 1)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        copy_button = buttons.addButton("Copy Citation Text", QtWidgets.QDialogButtonBox.ActionRole)
        copy_button.clicked.connect(
            lambda: QtWidgets.QApplication.clipboard().setText(PLIP_CITATION_TEXT)
        )
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)


class DiagnosticsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("PLIP Pose Diagnostics")
        self.setModal(False)
        self.resize(680, 380)
        layout = QtWidgets.QVBoxLayout(self)
        self.summary = QtWidgets.QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text, 1)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        copy_button = buttons.addButton("Copy Diagnostics", QtWidgets.QDialogButtonBox.ActionRole)
        copy_button.clicked.connect(
            lambda: QtWidgets.QApplication.clipboard().setText(self.text.toPlainText())
        )
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def set_profile(self, state: int, profile: dict[str, Any]) -> None:
        policy = (
            "used explicit input hydrogens because both partners contained them"
            if profile.get("hydrogen_policy") == "use_input"
            else "allowed PLIP to add missing polar hydrogens automatically"
        )
        self.summary.setText(
            f"State {state}: {profile.get('title', f'State {state}')}\n"
            f"Hydrogen policy: {policy}. This policy is selected automatically."
        )
        warnings = profile.get("warnings", ())
        self.text.setPlainText("\n".join(str(value) for value in warnings))


class AppearanceDialog(QtWidgets.QDialog):
    def __init__(self, controller: Any, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("PLIP Interaction Appearance")
        self.setModal(False)
        self.resize(760, 520)
        layout = QtWidgets.QVBoxLayout(self)

        radius_row = QtWidgets.QHBoxLayout()
        radius_row.addWidget(QtWidgets.QLabel("Global dash radius"))
        self.radius = QtWidgets.QDoubleSpinBox()
        self.radius.setRange(0.001, 2.0)
        self.radius.setDecimals(3)
        self.radius.setSingleStep(0.01)
        self.radius.setToolTip(
            "This is PyMOL's global dash_radius and affects plugin and user-created measurements."
        )
        radius_row.addWidget(self.radius)
        radius_note = QtWidgets.QLabel("affects all PyMOL measurements")
        radius_note.setStyleSheet("color: gray")
        radius_row.addWidget(radius_note)
        radius_row.addStretch(1)
        layout.addLayout(radius_row)

        grid = QtWidgets.QGridLayout()
        for column, heading in enumerate(
            ("Interaction class", "Color", "Pattern", "Length", "Gap")
        ):
            grid.addWidget(QtWidgets.QLabel(heading), 0, column)
        self.rows: dict[str, dict[str, Any]] = {}
        for row, interaction_type in enumerate(INTERACTION_TYPES, 1):
            color_button = QtWidgets.QPushButton()
            color_button.setMinimumWidth(92)
            pattern = QtWidgets.QComboBox()
            for value in PATTERNS:
                pattern.addItem(PATTERN_LABELS[value], value)
            length = QtWidgets.QDoubleSpinBox()
            gap = QtWidgets.QDoubleSpinBox()
            for spin in (length, gap):
                spin.setRange(0.0, 5.0)
                spin.setDecimals(2)
                spin.setSingleStep(0.05)
            grid.addWidget(QtWidgets.QLabel(INTERACTION_LABELS[interaction_type]), row, 0)
            grid.addWidget(color_button, row, 1)
            grid.addWidget(pattern, row, 2)
            grid.addWidget(length, row, 3)
            grid.addWidget(gap, row, 4)
            self.rows[interaction_type] = {
                "color_button": color_button,
                "color": [1.0, 1.0, 1.0],
                "pattern": pattern,
                "length": length,
                "gap": gap,
            }
            color_button.clicked.connect(
                lambda _checked=False, name=interaction_type: self._choose_color(name)
            )
            pattern.currentIndexChanged.connect(
                lambda _index, name=interaction_type: self._pattern_changed(name)
            )
        grid.setColumnStretch(0, 1)
        layout.addLayout(grid)

        note = QtWidgets.QLabel(
            "Apply changes only to the selected overlay, or save them as defaults for future analyses. "
            "Saving a PSE preserves the applied object settings."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        self.apply_button = buttons.addButton(
            "Apply to Current Overlay", QtWidgets.QDialogButtonBox.ActionRole
        )
        save_button = buttons.addButton(
            "Apply && Save as My Defaults", QtWidgets.QDialogButtonBox.ActionRole
        )
        restore_button = buttons.addButton(
            "Restore PLIP Defaults", QtWidgets.QDialogButtonBox.ResetRole
        )
        self.apply_button.clicked.connect(lambda: self._apply(False))
        save_button.clicked.connect(lambda: self._apply(True))
        restore_button.clicked.connect(self._restore)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        self._load()

    def showEvent(self, event: Any) -> None:
        self._load()
        super().showEvent(event)

    def _load(self, styles: dict[str, dict[str, Any]] | None = None) -> None:
        styles = styles or self.controller.current_appearance()
        self.radius.setValue(float(self.controller.cmd.get("dash_radius")))
        self.apply_button.setEnabled(self.controller.run is not None)
        for name, style in styles.items():
            row = self.rows[name]
            row["color"] = list(style["color"])
            self._update_color_button(name)
            combo = row["pattern"]
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(style["pattern"])))
            combo.blockSignals(False)
            row["length"].setValue(float(style["dash_length"]))
            row["gap"].setValue(float(style["dash_gap"]))
            self._pattern_changed(name, apply_preset=False)

    def _update_color_button(self, name: str) -> None:
        row = self.rows[name]
        rgb = [round(float(value) * 255) for value in row["color"]]
        hex_color = "#{:02X}{:02X}{:02X}".format(*rgb)
        text_color = "black" if sum(rgb) > 382 else "white"
        row["color_button"].setText(hex_color)
        row["color_button"].setStyleSheet(
            f"background-color: {hex_color}; color: {text_color};"
        )

    def _choose_color(self, name: str) -> None:
        current = self.rows[name]["color"]
        initial = QtGui.QColor.fromRgbF(*current)
        chosen = QtWidgets.QColorDialog.getColor(initial, self, "Choose interaction color")
        if chosen.isValid():
            self.rows[name]["color"] = [chosen.redF(), chosen.greenF(), chosen.blueF()]
            self._update_color_button(name)

    def _pattern_changed(self, name: str, *, apply_preset: bool = True) -> None:
        row = self.rows[name]
        pattern = row["pattern"].currentData()
        presets = {
            "solid": (0.15, 0.0),
            "dashed": (0.15, 0.50),
            "long_dashed": (0.60, 0.30),
        }
        if apply_preset and pattern in presets:
            row["length"].setValue(presets[pattern][0])
            row["gap"].setValue(presets[pattern][1])
        editable = pattern == "custom"
        row["length"].setEnabled(editable)
        row["gap"].setEnabled(editable)

    def _styles(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "color": list(row["color"]),
                "pattern": row["pattern"].currentData(),
                "dash_length": row["length"].value(),
                "dash_gap": row["gap"].value(),
            }
            for name, row in self.rows.items()
        }

    def _apply(self, save_as_defaults: bool) -> None:
        try:
            self.controller.set_global_dash_radius(self.radius.value())
            self.controller.apply_interaction_appearance(
                self._styles(),
                save_as_defaults=save_as_defaults,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "PLIP Pose Inspector", str(exc))

    def _restore(self) -> None:
        styles = self.controller.restore_plip_appearance()
        self._load(styles)


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
        self._appearance_dialog: AppearanceDialog | None = None
        self._diagnostics_dialog: DiagnosticsDialog | None = None
        self._citation_dialog: CitationDialog | None = None
        self.setWindowTitle("PLIP Pose Inspector")
        self.setModal(False)
        self.resize(820, 720)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

        outer = QtWidgets.QVBoxLayout(self)
        selectors = QtWidgets.QGroupBox("Objects and states")
        selectors_layout = QtWidgets.QVBoxLayout(selectors)
        form = QtWidgets.QFormLayout()
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
        form.addRow("Receptor selection", self.receptor)
        form.addRow("Ligand object/selection", self.ligand)
        form.addRow("Fixed receptor state", self.receptor_state)
        form.addRow("", self.filtered)
        form.addRow("Ligand states", self.state_count)
        selectors_layout.addLayout(form)

        status_rows = QtWidgets.QGridLayout()
        self.current_pose = QtWidgets.QLineEdit("—")
        self.current_pose.setReadOnly(True)
        self.current_pose.setToolTip("Current ligand state, title, and analysis status.")
        self.chemistry_status = QtWidgets.QLineEdit("Hydrogen policy: —")
        self.chemistry_status.setReadOnly(True)
        self.chemistry_status.setToolTip("Hydrogen policy for the current analyzed pose.")
        row_height = max(
            self.current_pose.sizeHint().height(),
            self.chemistry_status.sizeHint().height(),
        )
        self.current_pose.setFixedHeight(row_height)
        self.chemistry_status.setFixedHeight(row_height)
        status_rows.addWidget(QtWidgets.QLabel("Current Pose"), 0, 0)
        status_rows.addWidget(self.current_pose, 1, 0)
        profile_header = QtWidgets.QHBoxLayout()
        profile_header.addWidget(QtWidgets.QLabel("Profile"))
        profile_header.addStretch(1)
        self.diagnostics_button = QtWidgets.QPushButton("View Diagnostics…")
        self.diagnostics_button.setEnabled(False)
        self.diagnostics_button.setToolTip(
            "Show captured PLIP warnings for the current analyzed pose."
        )
        profile_header.addWidget(self.diagnostics_button)
        status_rows.addLayout(profile_header, 2, 0)
        status_rows.addWidget(self.chemistry_status, 3, 0)
        status_rows.setColumnStretch(0, 1)
        selectors_layout.addLayout(status_rows)
        outer.addWidget(selectors)

        actions = QtWidgets.QHBoxLayout()
        self.precompute = QtWidgets.QPushButton("Precompute All")
        self.analyze_current = QtWidgets.QPushButton("Analyze Current Only")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.refresh_button = QtWidgets.QPushButton("Refresh Object Lists")
        self.refresh_button.setToolTip(
            "Rescan molecular objects loaded, deleted, or renamed while this dialog is open."
        )
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
        pocket_label = QtWidgets.QLabel("Pocket")
        self.pocket = QtWidgets.QComboBox()
        self.pocket.addItem("Current pose", "current")
        self.pocket.addItem("All analyzed poses", "all")
        self.pocket.addItem("Hidden", "off")
        self.pocket.setToolTip(
            "Show interacting receptor residues for the current pose, their analyzed union, or hide the plugin-owned pocket."
        )
        self.settings_button = QtWidgets.QPushButton("Settings…")
        self.appearance_button = QtWidgets.QPushButton("Appearance…")
        self.review_2d_button = QtWidgets.QPushButton("2D Review…")
        self.review_2d_button.setToolTip(
            "Open the optional Ligand Review Panel on this ligand object."
        )
        self.citation_button = QtWidgets.QPushButton("Citation…")
        options.addWidget(self.all_button)
        options.addWidget(self.clear_button)
        options.addWidget(pocket_label)
        options.addWidget(self.pocket, 1)
        options.addWidget(self.review_2d_button)
        options.addWidget(self.appearance_button)
        options.addWidget(self.settings_button)
        options.addWidget(self.citation_button)
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
        self.ligand.currentTextChanged.connect(self._ligand_changed)
        self.all_button.clicked.connect(self._toggle_all)
        self.clear_button.clicked.connect(controller.clear)
        self.pocket.currentIndexChanged.connect(self._set_pocket_mode)
        self.appearance_button.clicked.connect(self._show_appearance)
        self.review_2d_button.clicked.connect(self._show_2d_review)
        self.settings_button.clicked.connect(self._show_settings)
        self.citation_button.clicked.connect(self._show_citation)
        self.diagnostics_button.clicked.connect(self._show_diagnostics)

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

    def showEvent(self, event: Any) -> None:
        self.refresh_objects()
        super().showEvent(event)

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
        self.controller.attach_existing_run(ligand_text, receptor_text)
        self._refresh_ligand_info()

    def _ligand_changed(self, _text: str) -> None:
        self.controller.attach_existing_run(
            self.ligand.currentText(),
            self.receptor.currentText(),
        )
        self._refresh_ligand_info()

    def _refresh_ligand_info(self) -> None:
        name, total, state, title = self.controller.ligand_info(self.ligand.currentText())
        self.state_count.setText(str(total) if total else "Selection must resolve to one object")
        if total and name == self.controller.active_ligand_object:
            if self.controller.session_attached:
                marker = "saved overlay attached"
            else:
                marker = "analyzed" if state in self.controller.profiles else "not analyzed"
            self.current_pose.setText(f"{state}/{total}: {title} ({marker})")
        else:
            self.current_pose.setText(f"{state}/{total}: {title}" if total else "—")
        self.current_pose.setToolTip(self.current_pose.text())

    def _analyze(self, states: str) -> None:
        try:
            self.controller.analyze(
                receptor=self.receptor.currentText(),
                ligand=self.ligand.currentText(),
                states=states,
                receptor_state=self.receptor_state.value(),
                filtered=self.filtered.isChecked(),
                pocket=self.pocket.currentData(),
            )
        except Exception as exc:
            self._show_error(str(exc))

    def _set_pocket_mode(self, _index: int) -> None:
        self.controller.set_pocket_mode(self.pocket.currentData())

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
        pocket_index = self.pocket.findData(self.controller.pocket_mode)
        if pocket_index >= 0 and pocket_index != self.pocket.currentIndex():
            self.pocket.blockSignals(True)
            self.pocket.setCurrentIndex(pocket_index)
            self.pocket.blockSignals(False)
        current, total = self.controller.current_counts()
        for name in INTERACTION_TYPES:
            checkbox = self.type_checks[name]
            checkbox.blockSignals(True)
            checkbox.setChecked(self.controller.type_enabled(name))
            checkbox.blockSignals(False)
            self.type_counts[name].setText(
                "— / —"
                if self.controller.session_attached
                else f"{current[name]} / {total[name]}"
            )
        if self.controller.engine:
            self.engine_label.setText(
                f"PLIP {self.controller.engine.get('plip', '?')} / "
                f"OpenBabel {self.controller.engine.get('openbabel', '?')} / "
                f"Python {self.controller.engine.get('python', '?')}"
            )
        state = self.controller.current_status()[0]
        profile = self.controller.profiles.get(state)
        self.diagnostics_button.setEnabled(
            bool(profile and profile.get("warnings"))
            and not self.controller.session_attached
        )
        if profile is None and self.controller.session_attached:
            self.chemistry_status.setText(
                "Saved-session overlay attached; normalized profile details unavailable"
            )
            self.chemistry_status.setToolTip(
                "Display, pocket, and appearance controls do not require reanalysis. "
                "Hydrogen policy and diagnostics are available only from a live analysis."
            )
        elif profile is None:
            self.chemistry_status.setText("Hydrogen policy: — (current pose not analyzed)")
            self.chemistry_status.setToolTip(
                "No normalized PLIP profile is loaded for the current ligand state."
            )
        else:
            policy = (
                "use explicit input hydrogens"
                if profile.get("hydrogen_policy") == "use_input"
                else "PLIP adds missing polar hydrogens"
            )
            warning_count = len(profile.get("warnings", ()))
            suffix = f"; {warning_count} diagnostic message(s)" if warning_count else ""
            self.chemistry_status.setText(f"Hydrogen policy: {policy}{suffix}")
            diagnostics = "\n".join(profile.get("warnings", ()))
            self.chemistry_status.setToolTip(
                diagnostics or self.chemistry_status.text()
            )
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
        self.current_pose.setToolTip(self.current_pose.text())
        self._profiles_changed()

    def _show_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self.controller, self)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _show_appearance(self) -> None:
        if self._appearance_dialog is None:
            self._appearance_dialog = AppearanceDialog(self.controller, self)
        self._appearance_dialog.show()
        self._appearance_dialog.raise_()
        self._appearance_dialog.activateWindow()

    def _show_2d_review(self) -> None:
        try:
            import pymol_ligand_review

            pymol_ligand_review.ligand_review_gui(self.ligand.currentText().strip())
        except Exception as exc:
            message = (
                "Ligand Review Panel is not installed. Install its PyMOL Plugin Manager ZIP "
                "to enable synchronized 2D structures and compound selection."
                if isinstance(exc, ImportError)
                else str(exc)
            )
            self.status.setText(message)
            QtWidgets.QMessageBox.information(self, "2D Ligand Review", message)

    def _show_diagnostics(self) -> None:
        state = self.controller.current_status()[0]
        profile = self.controller.profiles.get(state)
        if not profile or not profile.get("warnings"):
            return
        if self._diagnostics_dialog is None:
            self._diagnostics_dialog = DiagnosticsDialog(self)
        self._diagnostics_dialog.set_profile(state, profile)
        self._diagnostics_dialog.show()
        self._diagnostics_dialog.raise_()
        self._diagnostics_dialog.activateWindow()

    def _show_citation(self) -> None:
        if self._citation_dialog is None:
            self._citation_dialog = CitationDialog(self)
        self._citation_dialog.show()
        self._citation_dialog.raise_()
        self._citation_dialog.activateWindow()

    def show_citation_once(self) -> None:
        key = "citation_dialog_shown"
        if bool(self.controller.settings.value(key, False, type=bool)):
            return
        self.controller.settings.setValue(key, True)
        self._show_citation()

    def _show_error(self, message: str) -> None:
        self.status.setText(message)
        QtWidgets.QMessageBox.warning(self, "PLIP Pose Inspector", message)

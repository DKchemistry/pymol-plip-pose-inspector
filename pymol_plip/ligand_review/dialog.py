"""Qt interfaces for depiction, selection review, settings, and export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pymol.Qt import QtCore, QtGui, QtWidgets


class ScaledPixmapLabel(QtWidgets.QLabel):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._source = QtGui.QPixmap()
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMinimumSize(420, 280)
        self.setStyleSheet("background: white; border: 1px solid #b8b8b8;")
        self.setText("Choose a ligand to generate a 2D depiction")

    def set_source(self, pixmap: QtGui.QPixmap | None, placeholder: str = "") -> None:
        self._source = pixmap or QtGui.QPixmap()
        if self._source.isNull():
            self.setPixmap(QtGui.QPixmap())
            self.setText(placeholder)
        else:
            self.setText("")
            self._rescale()

    def resizeEvent(self, event: Any) -> None:
        self._rescale()
        super().resizeEvent(event)

    def _rescale(self) -> None:
        if self._source.isNull():
            return
        size = self.size() - QtCore.QSize(12, 12)
        self.setPixmap(
            self._source.scaled(
                size,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, controller: Any, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("PyMOL Pose Inspector Settings")
        self.setModal(False)
        self.resize(720, 260)
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        worker_row = QtWidgets.QHBoxLayout()
        self.worker = QtWidgets.QLineEdit()
        configured = str(controller.settings.value("worker_python", "") or "")
        if not configured:
            configured = next(
                (str(path) for path in controller.worker_python_candidates() if path.is_file()),
                "",
            )
        self.worker.setText(configured)
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        worker_row.addWidget(self.worker, 1)
        worker_row.addWidget(browse)
        form.addRow("RDKit worker Python", worker_row)
        self.cache_label = QtWidgets.QLabel()
        self.cache_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        form.addRow("Depiction cache", self.cache_label)
        layout.addLayout(form)
        note = QtWidgets.QLabel(
            "RDKit runs in this external interpreter and is never imported into PyMOL. "
            "The recommended unified environment is named pymol-pose-inspector."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.health_status = QtWidgets.QLabel("Not checked")
        self.health_status.setWordWrap(True)
        layout.addWidget(self.health_status)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        save = buttons.addButton("Save", QtWidgets.QDialogButtonBox.ActionRole)
        health = buttons.addButton("Health Check", QtWidgets.QDialogButtonBox.ActionRole)
        clear_cache = buttons.addButton("Clear Cache", QtWidgets.QDialogButtonBox.ResetRole)
        save.clicked.connect(self._save)
        health.clicked.connect(self._health)
        clear_cache.clicked.connect(self._clear_cache)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        self._refresh_cache()

    def showEvent(self, event: Any) -> None:
        self._refresh_cache()
        super().showEvent(event)

    def _browse(self) -> None:
        filename, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose RDKit worker Python", self.worker.text() or str(Path.home())
        )
        if filename:
            self.worker.setText(filename)

    def _save(self) -> None:
        self.controller.set_worker_python(self.worker.text().strip())
        self.health_status.setText("Worker path saved")

    def _health(self) -> None:
        self._save()
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            ok, message, _engine = self.controller.health_check(self.worker.text().strip())
            self.health_status.setText(message)
            self.health_status.setStyleSheet("color: #167b16;" if ok else "color: #a00000;")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _refresh_cache(self) -> None:
        count, size, root = self.controller.cache_stats()
        self.cache_label.setText(f"{count} image(s), {size / 1048576:.2f} MiB — {root}")

    def _clear_cache(self) -> None:
        answer = QtWidgets.QMessageBox.question(
            self,
            "Clear depiction cache",
            "Delete every cached RDKit depiction? Selected compounds are not affected.",
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.controller.clear_cache()
            self._refresh_cache()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Ligand Review Panel", str(exc))


class SelectedCompoundsDialog(QtWidgets.QDialog):
    COLUMNS = ("Name", "Identifier", "SMILES", "Object", "Selected state", "Matching sources")

    def __init__(self, controller: Any, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._refreshing = False
        self.setWindowTitle("Selected Compounds")
        self.setModal(False)
        self.resize(1250, 430)
        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)
        self.table.itemChanged.connect(self._item_changed)
        layout.addWidget(self.table, 1)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        jump = buttons.addButton("Jump to Pose", QtWidgets.QDialogButtonBox.ActionRole)
        copy = buttons.addButton("Copy SMILES", QtWidgets.QDialogButtonBox.ActionRole)
        remove = buttons.addButton("Remove", QtWidgets.QDialogButtonBox.DestructiveRole)
        export = buttons.addButton("Export CSV…", QtWidgets.QDialogButtonBox.ActionRole)
        jump.clicked.connect(self._jump)
        copy.clicked.connect(self._copy)
        remove.clicked.connect(self._remove)
        export.clicked.connect(lambda: self.parent().export_csv_dialog())
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        controller.selection_changed.connect(self.refresh)

    def showEvent(self, event: Any) -> None:
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        self._refreshing = True
        try:
            rows = self.controller.selections.records()
            self.table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                values = (
                    row["name"],
                    row["identifier"],
                    row["smiles"],
                    row["ligand_object"],
                    str(row["selected_state"]),
                    row["matching_sources"],
                )
                for column, value in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(value))
                    item.setData(QtCore.Qt.UserRole, row["key"])
                    if column not in (0, 1):
                        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    self.table.setItem(row_index, column, item)
        finally:
            self._refreshing = False

    def _current(self) -> tuple[str, int] | None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return None
        return str(self.table.item(row, 0).data(QtCore.Qt.UserRole)), row

    def _item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if self._refreshing or item.column() not in (0, 1):
            return
        key = str(item.data(QtCore.Qt.UserRole))
        kwargs = {"name" if item.column() == 0 else "identifier": item.text()}
        self.controller.update_selection(key, **kwargs)

    def _jump(self) -> None:
        current = self._current()
        if current is None:
            return
        key, _row = current
        compound = self.controller.selections.selected[key]
        try:
            self.controller.jump_to(compound.ligand_object, compound.selected_state)
            parent = self.parent()
            parent.ligand.blockSignals(True)
            parent.ligand.setEditText(compound.ligand_object)
            parent.ligand.blockSignals(False)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Ligand Review Panel", str(exc))

    def _copy(self) -> None:
        current = self._current()
        if current is None:
            return
        key, _row = current
        QtWidgets.QApplication.clipboard().setText(self.controller.selections.selected[key].smiles)

    def _remove(self) -> None:
        current = self._current()
        if current is not None:
            self.controller.remove_selection(current[0])


class LigandReviewDialog(QtWidgets.QDialog):
    def __init__(self, controller: Any, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._settings_dialog: SettingsDialog | None = None
        self._selected_dialog: SelectedCompoundsDialog | None = None
        self._displayed_identity = ""
        self._attach_timer = QtCore.QTimer(self)
        self._attach_timer.setSingleShot(True)
        self._attach_timer.setInterval(300)
        self._attach_timer.timeout.connect(lambda: self._attach(False))

        self.setWindowTitle("2D Ligand Review — PyMOL Pose Inspector")
        self.setModal(False)
        self.resize(760, 790)
        outer = QtWidgets.QVBoxLayout(self)

        object_row = QtWidgets.QHBoxLayout()
        object_row.addWidget(QtWidgets.QLabel("Ligand object/selection"))
        self.ligand = QtWidgets.QComboBox()
        self.ligand.setEditable(True)
        object_row.addWidget(self.ligand, 1)
        self.refresh_button = QtWidgets.QPushButton("Refresh Objects")
        self.recompute_button = QtWidgets.QPushButton("Recompute")
        self.settings_button = QtWidgets.QPushButton("Settings…")
        object_row.addWidget(self.refresh_button)
        object_row.addWidget(self.recompute_button)
        object_row.addWidget(self.settings_button)
        outer.addLayout(object_row)

        header = QtWidgets.QHBoxLayout()
        self.state_label = QtWidgets.QLabel("State — / —")
        self.title_label = QtWidgets.QLabel("No ligand selected")
        font = self.title_label.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        self.title_label.setFont(font)
        self.title_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        header.addWidget(self.state_label)
        header.addWidget(self.title_label, 1)
        outer.addLayout(header)

        self.image = ScaledPixmapLabel()
        outer.addWidget(self.image, 1)

        form = QtWidgets.QFormLayout()
        self.name = QtWidgets.QLineEdit()
        self.identifier = QtWidgets.QLineEdit()
        self.smiles = QtWidgets.QPlainTextEdit()
        self.smiles.setReadOnly(True)
        self.smiles.setMaximumHeight(62)
        self.smiles.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        form.addRow("Name", self.name)
        form.addRow("Identifier", self.identifier)
        form.addRow("Canonical isomeric SMILES", self.smiles)
        outer.addLayout(form)

        actions = QtWidgets.QHBoxLayout()
        self.previous_button = QtWidgets.QPushButton("Previous")
        self.next_button = QtWidgets.QPushButton("Next")
        self.mark_button = QtWidgets.QPushButton("Mark Compound")
        self.review_button = QtWidgets.QPushButton("Selected Compounds (0)…")
        self.export_button = QtWidgets.QPushButton("Export CSV…")
        self.clear_button = QtWidgets.QPushButton("Clear Selections")
        self.previous_button.setShortcut("Alt+Left")
        self.next_button.setShortcut("Alt+Right")
        self.mark_button.setShortcut("Ctrl+M")
        actions.addWidget(self.previous_button)
        actions.addWidget(self.next_button)
        actions.addWidget(self.mark_button)
        actions.addWidget(self.review_button)
        actions.addWidget(self.export_button)
        actions.addWidget(self.clear_button)
        outer.addLayout(actions)

        progress_row = QtWidgets.QHBoxLayout()
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Idle")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.cancel_button)
        outer.addLayout(progress_row)
        self.engine_label = QtWidgets.QLabel("RDKit worker not yet checked")
        self.status = QtWidgets.QLabel("Choose a ligand object to begin.")
        self.status.setWordWrap(True)
        self.diagnostics = QtWidgets.QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMaximumHeight(68)
        self.diagnostics.hide()
        outer.addWidget(self.engine_label)
        outer.addWidget(self.status)
        outer.addWidget(self.diagnostics)

        self.refresh_button.clicked.connect(self.refresh_objects)
        self.recompute_button.clicked.connect(lambda: self._attach(True))
        self.settings_button.clicked.connect(self._show_settings)
        self.ligand.currentTextChanged.connect(self._ligand_changed)
        self.previous_button.clicked.connect(controller.previous_state)
        self.next_button.clicked.connect(controller.next_state)
        self.mark_button.clicked.connect(self._mark_current)
        self.review_button.clicked.connect(self._show_selected)
        self.export_button.clicked.connect(self.export_csv_dialog)
        self.clear_button.clicked.connect(self._clear_selections)
        self.cancel_button.clicked.connect(controller.cancel)
        self.name.editingFinished.connect(self._metadata_edited)
        self.identifier.editingFinished.connect(self._metadata_edited)

        controller.status_changed.connect(self.status.setText)
        controller.running_changed.connect(self._running_changed)
        controller.progress_changed.connect(self._progress_changed)
        controller.records_changed.connect(self._records_changed)
        controller.state_changed.connect(self._state_changed)
        controller.selection_changed.connect(self._selection_changed)
        controller.error_occurred.connect(self._show_error)
        if controller.session is not None:
            controller.session.ligand_changed.connect(self._shared_ligand_changed)
        self.refresh_objects(schedule=False)
        self._selection_changed()

    def closeEvent(self, event: Any) -> None:
        self.hide()
        event.ignore()

    def showEvent(self, event: Any) -> None:
        self.refresh_objects(schedule=not bool(self.controller.active_ligand_object))
        super().showEvent(event)

    def refresh_objects(self, _checked: bool = False, *, schedule: bool = True) -> None:
        current = self.ligand.currentText().strip()
        if self.controller.session is not None and self.controller.session.active_selection:
            current = self.controller.session.active_selection
        objects = self.controller.molecular_objects()
        names = [item["name"] for item in objects]
        if not current:
            current = next(
                (item["name"] for item in objects if item["states"] > 1 and item["protein_atoms"] == 0),
                next((item["name"] for item in objects if item["protein_atoms"] == 0), ""),
            )
        self.ligand.blockSignals(True)
        self.ligand.clear()
        self.ligand.addItems(names)
        self.ligand.setEditText(current)
        self.ligand.blockSignals(False)
        if schedule and current and not self.controller.is_running:
            self._attach_timer.start()

    def attach_ligand(self, ligand: str, *, force: bool = False) -> None:
        self.ligand.blockSignals(True)
        self.ligand.setEditText(str(ligand))
        self.ligand.blockSignals(False)
        self._attach(force)

    def _ligand_changed(self, _text: str) -> None:
        if self.isVisible() and not self.controller.is_running:
            self._attach_timer.start()

    def _shared_ligand_changed(
        self, selection: str, _ligand_object: str, _total: int
    ) -> None:
        if self.ligand.currentText().strip() == selection:
            return
        self.ligand.blockSignals(True)
        self.ligand.setEditText(selection)
        self.ligand.blockSignals(False)

    def _attach(self, force: bool) -> None:
        ligand = self.ligand.currentText().strip()
        if not ligand:
            return
        try:
            self.controller.attach(ligand, force=force)
        except Exception as exc:
            self.status.setText(str(exc))
            self.image.set_source(None, "Depiction unavailable — check Settings")

    def _running_changed(self, running: bool) -> None:
        self.cancel_button.setEnabled(running)
        self.recompute_button.setEnabled(not running)
        self.ligand.setEnabled(not running)
        self.refresh_button.setEnabled(not running)

    def _progress_changed(self, completed: int, total: int, hits: int, failures: int) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(completed)
        self.progress.setFormat(
            f"{completed}/{total} — {hits} cache hit(s) — {failures} failure(s)"
        )

    def _records_changed(self) -> None:
        if self.controller.engine:
            self.engine_label.setText(
                f"RDKit {self.controller.engine.get('rdkit', '?')} / "
                f"Python {self.controller.engine.get('python', '?')}"
            )
        self._display_current(force=False)

    def _state_changed(self, _state: int, _title: str, _record: Any) -> None:
        self._display_current(force=True)

    def _display_current(self, *, force: bool) -> None:
        state = self.controller.current_state()
        total = self.controller.total_states
        title = self.controller.current_title() if self.controller.active_ligand_object else "No ligand selected"
        record = self.controller.records.get(state)
        self.state_label.setText(f"State {state} / {total or '—'}")
        self.title_label.setText(title)
        self.previous_button.setEnabled(bool(total and state > 1))
        self.next_button.setEnabled(bool(total and state < total))
        if record is None:
            failure = self.controller.failures.get(state, "Depiction is being generated…")
            self.image.set_source(None, failure)
            self.smiles.clear()
            self.mark_button.setEnabled(False)
            self.mark_button.setText("Mark Compound")
            self.diagnostics.setPlainText(failure if state in self.controller.failures else "")
            self.diagnostics.setVisible(state in self.controller.failures)
            identity = ""
        else:
            pixmap = QtGui.QPixmap(str(record["image_path"]))
            self.image.set_source(pixmap, "Cached depiction could not be loaded")
            self.smiles.setPlainText(str(record["smiles"]))
            identity = str(record["identity_key"])
            selected = self.controller.selections.selected.get(identity)
            self.mark_button.setEnabled(True)
            self.mark_button.setText("Unmark Compound" if selected else "Mark Compound")
            warnings = "\n".join(str(value) for value in record.get("warnings", ()))
            self.diagnostics.setPlainText(warnings)
            self.diagnostics.setVisible(bool(warnings))
            if force or identity != self._displayed_identity:
                self.name.setText(selected.name if selected else title)
                self.identifier.setText(selected.identifier if selected else title)
        if identity != self._displayed_identity:
            self._displayed_identity = identity

    def _mark_current(self) -> None:
        try:
            self.controller.mark_current(
                enabled="toggle",
                name=self.name.text(),
                identifier=self.identifier.text(),
            )
        except Exception as exc:
            self._show_error(str(exc))

    def _metadata_edited(self) -> None:
        record = self.controller.current_record()
        if record and self.controller.selections.is_selected(record["identity_key"]):
            self.controller.update_selection(
                record["identity_key"],
                name=self.name.text(),
                identifier=self.identifier.text(),
            )

    def _selection_changed(self) -> None:
        count = len(self.controller.selections.selected)
        self.review_button.setText(f"Selected Compounds ({count})…")
        self.review_button.setEnabled(count > 0)
        self.export_button.setEnabled(count > 0)
        self.clear_button.setEnabled(count > 0)
        self._display_current(force=True)

    def _show_selected(self) -> None:
        if self._selected_dialog is None:
            self._selected_dialog = SelectedCompoundsDialog(self.controller, self)
        self._selected_dialog.show()
        self._selected_dialog.raise_()
        self._selected_dialog.activateWindow()

    def _show_settings(self) -> None:
        if self.controller.application is not None:
            self.controller.application.show_settings(self)
            return
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self.controller, self)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def export_csv_dialog(self) -> None:
        filename, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export selected compounds",
            "selected_compounds.csv",
            "CSV files (*.csv);;All files (*)",
        )
        if not filename:
            return
        path = Path(filename)
        if path.exists():
            answer = QtWidgets.QMessageBox.question(
                self,
                "Overwrite CSV",
                f"Overwrite {path}?",
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return
        try:
            self.controller.export_csv(str(path))
        except Exception as exc:
            self._show_error(str(exc))

    def _clear_selections(self) -> None:
        answer = QtWidgets.QMessageBox.question(
            self,
            "Clear selected compounds",
            "Remove every compound from this session's worklist?",
        )
        if answer == QtWidgets.QMessageBox.Yes:
            self.controller.clear_selections()

    def _show_error(self, message: str) -> None:
        self.status.setText(message)
        QtWidgets.QMessageBox.warning(self, "PyMOL Pose Inspector", message)

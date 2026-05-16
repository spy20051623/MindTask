"""Desktop dialogs used by the MindTask main window."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import MindTaskDB, normalize_due_date
from .constants import (
    HISTORY_ACTION_TRANSLATION_KEYS,
    HISTORY_ENTITY_TRANSLATION_KEYS,
    PRIORITY_LABELS,
    PRIORITY_TRANSLATION_KEYS,
)
from .dialog_helpers import confirm_question, localize_dialog_buttons, required_label
from .due_date_editor import DueDateEditor
from .i18n import Translator
from .style import THEME_SYSTEM, badge_colors_for_theme, build_app_style, colors_for_theme


class HistoryDialog(QDialog):
    """History viewer with scoped undo actions."""

    history_changed = Signal()

    def __init__(
        self,
        db: MindTaskDB,
        theme: str = THEME_SYSTEM,
        language: str = "system",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.db = db
        self.theme = theme
        self.translator = Translator(language)
        self.setWindowTitle(self.tr("history"))
        self.resize(760, 460)
        self.setStyleSheet(build_app_style(theme, QApplication.instance()))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QLabel(self.tr("operation_history"))
        header.setObjectName("SectionLabel")
        layout.addWidget(header)

        self.history_table = QTableWidget(0, 6)
        self.history_table.setObjectName("TaskTable")
        self.history_table.setHorizontalHeaderLabels(
            ["ID", self.tr("created"), self.tr("action"), self.tr("entity"), self.tr("state"), self.tr("undone")]
        )
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.history_table, 1)

        button_row = QHBoxLayout()
        self.undo_latest_button = QPushButton(self.tr("undo_latest"))
        self.undo_latest_button.setObjectName("SecondaryButton")
        self.undo_latest_button.clicked.connect(self.undo_latest)
        self.undo_to_selected_button = QPushButton(self.tr("undo_to_selected"))
        self.undo_to_selected_button.setObjectName("DangerButton")
        self.undo_to_selected_button.clicked.connect(self.undo_to_selected)
        close_button = QPushButton(self.tr("close"))
        close_button.clicked.connect(self.accept)
        button_row.addWidget(self.undo_latest_button)
        button_row.addWidget(self.undo_to_selected_button)
        button_row.addStretch()
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.refresh()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def refresh(self) -> None:
        rows = self.db.get_history(limit=100, include_undone=True)
        self.history_table.setRowCount(len(rows))
        for row_index, history in enumerate(rows):
            entity_id = f"#{history['entity_id']}" if history.get("entity_id") is not None else ""
            action = history["action"]
            entity_type = history["entity_type"]
            values = [
                history["id"],
                history["created_at"],
                self.tr(HISTORY_ACTION_TRANSLATION_KEYS.get(action, action)),
                f"{self.tr(HISTORY_ENTITY_TRANSLATION_KEYS.get(entity_type, entity_type))}{entity_id}",
                self.tr("undone") if history.get("undone_at") else self.tr("active"),
                history.get("undone_at") or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                colors = colors_for_theme(self.theme, QApplication.instance())
                item.setForeground(QColor(colors["muted_text"] if history.get("undone_at") else colors["text"]))
                item.setBackground(QColor(colors["panel_bg"] if row_index % 2 else colors["input_bg"]))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, history["id"])
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 4:
                    history_colors = badge_colors_for_theme(self.theme, QApplication.instance())["history"]
                    badge = history_colors["undone" if history.get("undone_at") else "active"]
                    item.setForeground(QColor(badge[0]))
                    item.setBackground(QColor(badge[1]))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.history_table.setItem(row_index, column, item)
        self.history_table.resizeRowsToContents()
        self.undo_latest_button.setEnabled(any(not row.get("undone_at") for row in rows))
        self.undo_to_selected_button.setEnabled(bool(rows))

    def undo_latest(self) -> None:
        history = self.db.undo_last_operation()
        if not history:
            QMessageBox.information(self, self.tr("undo"), self.tr("no_operation_to_undo"))
            self.refresh()
            return
        self.history_changed.emit()
        self.refresh()

    def undo_to_selected(self) -> None:
        history_id = self._selected_history_id()
        if history_id is None:
            QMessageBox.information(self, self.tr("history"), self.tr("select_history_first"))
            return

        selected = self._selected_history_row()
        if selected is not None and selected.get("undone_at"):
            QMessageBox.information(self, self.tr("history"), self.tr("selected_history_undone"))
            return

        if not confirm_question(
            self,
            self.tr("undo_to_selected"),
            self.tr("undo_to_selected_confirm"),
            self.translator,
        ):
            return

        undone = self.db.undo_operations_until(history_id)
        if not undone:
            QMessageBox.information(self, self.tr("undo"), self.tr("no_operation_was_undone"))
            self.refresh()
            return

        self.history_changed.emit()
        self.refresh()

    def _selected_history_id(self) -> Optional[int]:
        rows = self.history_table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.history_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole))

    def _selected_history_row(self) -> Optional[Dict[str, Any]]:
        history_id = self._selected_history_id()
        if history_id is None:
            return None
        for row in self.db.get_history(limit=100, include_undone=True):
            if row["id"] == history_id:
                return row
        return None


class ProjectDialog(QDialog):
    """Dialog for creating or renaming a project."""

    def __init__(self, name: str = "", language: str = "system", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.translator = Translator(language)
        self.setWindowTitle(self.tr("new_project"))
        theme = THEME_SYSTEM
        app = QApplication.instance()
        if app is not None:
            theme = app.property("mindtask_theme") or THEME_SYSTEM
        self.setStyleSheet(build_app_style(theme, app))

        self.name_edit = QLineEdit(name)

        form = QFormLayout(self)
        form.addRow(required_label(self.tr("name")), self.name_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        localize_dialog_buttons(buttons, self.translator)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def project_name(self) -> str:
        return self.name_edit.text().strip()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _accept_if_valid(self) -> None:
        if not self.project_name():
            QMessageBox.warning(self, self.tr("invalid_project"), self.tr("name_required"))
            return
        self.accept()


class TaskDialog(QDialog):
    """Dialog for creating a task."""

    def __init__(
        self,
        projects: List[Dict[str, Any]],
        language: str = "system",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.translator = Translator(language)
        self.setWindowTitle(self.tr("new_task"))
        theme = THEME_SYSTEM
        app = QApplication.instance()
        if app is not None:
            theme = app.property("mindtask_theme") or THEME_SYSTEM
        self.setStyleSheet(build_app_style(theme, app))

        self.title_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.priority_combo = QComboBox()
        self.project_combo = QComboBox()
        self.due_editor = DueDateEditor(language=language)

        for priority in PRIORITY_LABELS:
            self.priority_combo.addItem(self.tr(PRIORITY_TRANSLATION_KEYS[priority]), priority)
        self.priority_combo.setCurrentIndex(0)

        self.project_combo.addItem(self.tr("none"), None)
        for project in projects:
            self.project_combo.addItem(project["name"], project["id"])

        form = QFormLayout(self)
        form.addRow(required_label(self.tr("title")), self.title_edit)
        form.addRow(self.tr("description"), self.description_edit)
        form.addRow(self.tr("priority"), self.priority_combo)
        form.addRow(self.tr("project"), self.project_combo)
        form.addRow(self.tr("due"), self.due_editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        localize_dialog_buttons(buttons, self.translator)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def task_data(self) -> Dict[str, Any]:
        due_date = self.due_editor.due_value()
        return {
            "title": self.title_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "priority": self.priority_combo.currentData(),
            "project_id": self.project_combo.currentData(),
            "due_date": due_date,
            "due_mode": self.due_editor.due_mode(),
        }

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _accept_if_valid(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, self.tr("invalid_task"), self.tr("title_required"))
            return
        try:
            normalize_due_date(self.due_editor.due_value())
        except ValueError as exc:
            QMessageBox.warning(self, self.tr("invalid_due_date"), str(exc))
            return
        self.accept()

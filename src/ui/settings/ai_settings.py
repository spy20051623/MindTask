"""AI settings panel for OpenAI-compatible providers."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core import OpenAICompatibleClient, mask_api_key, save_ai_execution_settings, save_ai_settings
from ..shared.alert_message import ALERT_DANGER, ALERT_INFO, AlertMessage
from .toggle_switch import ToggleSwitch


AI_TIMEOUT_OPTIONS = (0, 15, 30, 60, 120, 300)


class AISettingsMixin:
    """Mixin for AI provider configuration UI."""

    def _build_ai_settings_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        panel.setSizePolicy(self.expanding_size_policy())
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        self.ai_settings_title_label = self._section_label("")
        layout.addWidget(self.ai_settings_title_label)
        self.ai_model_settings_title_label = self._section_label("")
        layout.addWidget(self.ai_model_settings_title_label)

        form = QFormLayout()
        self.ai_base_url_edit = QLineEdit(self.ai_base_url)
        self.ai_base_url_label = QLabel()
        self.ai_base_url_hint_label = QLabel()
        self.ai_base_url_hint_label.setObjectName("MutedLabel")
        self.ai_base_url_hint_label.setWordWrap(True)
        form.addRow(self.ai_base_url_label, self._ai_field_with_hint(self.ai_base_url_edit, self.ai_base_url_hint_label))

        self.ai_api_key_edit = QLineEdit()
        self.ai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.ai_api_key_edit.setText("")
        self.ai_api_key_edit.setPlaceholderText(mask_api_key(self.ai_api_key))
        self.ai_api_key_edit.setProperty("storedApiKey", self.ai_api_key)
        self.ai_api_key_edit.setProperty("showingMaskedKey", bool(self.ai_api_key))
        self.ai_api_key_edit.installEventFilter(self)
        self.ai_api_key_edit.textEdited.connect(self._mark_ai_key_edited)
        self.ai_clear_key_button = QPushButton()
        self.ai_clear_key_button.setObjectName("SecondaryButton")
        self.ai_clear_key_button.clicked.connect(self.clear_ai_api_key)
        api_key_row = QWidget()
        api_key_row.setObjectName("TransparentRow")
        api_key_layout = QHBoxLayout(api_key_row)
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        api_key_layout.setSpacing(8)
        api_key_layout.addWidget(self.ai_api_key_edit, 1)
        api_key_layout.addWidget(self.ai_clear_key_button)
        self.ai_api_key_label = QLabel()
        self.ai_api_key_hint_label = QLabel()
        self.ai_api_key_hint_label.setObjectName("MutedLabel")
        self.ai_api_key_hint_label.setWordWrap(True)
        form.addRow(self.ai_api_key_label, self._ai_field_with_hint(api_key_row, self.ai_api_key_hint_label))

        self.ai_default_model_edit = QLineEdit(self.ai_default_model)
        self.ai_default_model_label = QLabel()
        form.addRow(self.ai_default_model_label, self.ai_default_model_edit)

        self.ai_models_list = QListWidget()
        self.ai_models_list.setObjectName("ProjectList")
        self.ai_models_list.setMinimumHeight(108)
        for model in self.ai_models:
            self._add_ai_model_list_item(model)
        self.ai_model_name_edit = QLineEdit()
        self.ai_add_model_button = QPushButton()
        self.ai_add_model_button.setObjectName("SecondaryButton")
        self.ai_add_model_button.clicked.connect(self.add_ai_model_from_input)
        self.ai_filter_models_button = QPushButton()
        self.ai_filter_models_button.setObjectName("SecondaryButton")
        self.ai_filter_models_button.clicked.connect(self.filter_ai_models_from_input)
        self.ai_delete_model_button = QPushButton()
        self.ai_delete_model_button.setObjectName("DangerButton")
        self.ai_delete_model_button.clicked.connect(self.delete_selected_ai_model)
        self.ai_set_default_model_button = QPushButton()
        self.ai_set_default_model_button.setObjectName("SecondaryButton")
        self.ai_set_default_model_button.clicked.connect(self.set_selected_ai_model_as_default)
        self.ai_fetch_models_button = QPushButton()
        self.ai_fetch_models_button.setObjectName("SecondaryButton")
        self.ai_fetch_models_button.clicked.connect(self.fetch_ai_models_from_provider)
        model_action_row = QWidget()
        model_action_row.setObjectName("TransparentRow")
        model_action_layout = QHBoxLayout(model_action_row)
        model_action_layout.setContentsMargins(0, 0, 0, 0)
        model_action_layout.setSpacing(8)
        model_action_layout.addWidget(self.ai_model_name_edit, 1)
        model_action_layout.addWidget(self.ai_add_model_button)
        model_action_layout.addWidget(self.ai_delete_model_button)
        model_action_layout.addWidget(self.ai_filter_models_button)
        model_action_layout.addWidget(self.ai_set_default_model_button)
        model_action_layout.addWidget(self.ai_fetch_models_button)
        models_row = QWidget()
        models_row.setObjectName("TransparentRow")
        models_layout = QVBoxLayout(models_row)
        models_layout.setContentsMargins(0, 0, 0, 0)
        models_layout.setSpacing(6)
        models_layout.addWidget(self.ai_models_list)
        models_layout.addWidget(model_action_row)
        self.ai_models_label = QLabel()
        form.addRow(self.ai_models_label, models_row)

        self.ai_models_endpoint_edit = QLineEdit(self.ai_models_endpoint)
        self.ai_models_endpoint_label = QLabel()
        self.ai_models_endpoint_hint_label = QLabel()
        self.ai_models_endpoint_hint_label.setObjectName("MutedLabel")
        self.ai_models_endpoint_hint_label.setWordWrap(True)
        form.addRow(
            self.ai_models_endpoint_label,
            self._ai_field_with_hint(self.ai_models_endpoint_edit, self.ai_models_endpoint_hint_label),
        )

        self.ai_timeout_combo = QComboBox()
        self.ai_timeout_combo.setObjectName("CompactComboBox")
        self.ai_timeout_combo.setFixedWidth(132)
        self.ai_timeout_combo.setToolTip(self.tr("ai_response_timeout_hint"))
        for seconds in AI_TIMEOUT_OPTIONS:
            self.ai_timeout_combo.addItem("", seconds)
        self._set_ai_timeout_combo(self.ai_request_timeout_seconds)
        self.ai_timeout_label = QLabel()
        form.addRow(self.ai_timeout_label, self.ai_timeout_combo)
        layout.addLayout(form)

        model_button_row = QHBoxLayout()
        model_button_row.setContentsMargins(0, 0, 0, 0)
        model_button_row.setSpacing(8)
        self.ai_save_button = QPushButton()
        self.ai_save_button.setObjectName("SecondaryButton")
        self.ai_save_button.clicked.connect(self.save_ai_settings_from_form)
        self.ai_test_connection_button = QPushButton()
        self.ai_test_connection_button.setObjectName("SecondaryButton")
        self.ai_test_connection_button.clicked.connect(self.test_ai_connection)
        self.ai_settings_message = AlertMessage()
        self.ai_settings_message.hide()
        model_button_row.addWidget(self.ai_save_button)
        model_button_row.addWidget(self.ai_test_connection_button)
        model_button_row.addWidget(self.ai_settings_message)
        model_button_row.addStretch()
        layout.addLayout(model_button_row)

        self.ai_execution_settings_title_label = self._section_label("")
        layout.addWidget(self.ai_execution_settings_title_label)

        self.ai_allow_database_write_switch = ToggleSwitch()
        self.ai_allow_database_write_switch.setChecked(self.ai_allow_database_write)
        self.ai_confirm_delete_actions_switch = ToggleSwitch()
        self.ai_confirm_delete_actions_switch.setChecked(self.ai_confirm_delete_actions)
        self.ai_confirm_bulk_actions_switch = ToggleSwitch()
        self.ai_confirm_bulk_actions_switch.setChecked(self.ai_confirm_bulk_actions)
        for switch in (
            self.ai_allow_database_write_switch,
            self.ai_confirm_delete_actions_switch,
            self.ai_confirm_bulk_actions_switch,
        ):
            switch.toggled.connect(self.apply_ai_execution_settings_from_controls)

        permission_form = QFormLayout()
        self.ai_allow_database_write_label = QLabel()
        self.ai_allow_database_write_hint_label = QLabel()
        self.ai_allow_database_write_hint_label.setObjectName("MutedLabel")
        self.ai_allow_database_write_hint_label.setWordWrap(True)
        permission_form.addRow(
            self.ai_allow_database_write_label,
            self._ai_switch_row(self.ai_allow_database_write_switch, self.ai_allow_database_write_hint_label),
        )
        self.ai_confirm_delete_actions_label = QLabel()
        permission_form.addRow(self.ai_confirm_delete_actions_label, self.ai_confirm_delete_actions_switch)
        self.ai_confirm_bulk_actions_label = QLabel()
        permission_form.addRow(self.ai_confirm_bulk_actions_label, self.ai_confirm_bulk_actions_switch)
        layout.addLayout(permission_form)
        self.ai_execution_message = AlertMessage()
        self.ai_execution_message.hide()
        layout.addWidget(self.ai_execution_message)
        layout.addStretch()
        return panel

    def _ai_switch_row(self, switch: ToggleSwitch, hint_label: QLabel) -> QWidget:
        row = QWidget()
        row.setObjectName("TransparentRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 3, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(switch)
        layout.addWidget(hint_label)
        return row

    def _ai_field_with_hint(self, field: QWidget, hint_label: QLabel) -> QWidget:
        row = QWidget()
        row.setObjectName("TransparentRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(field)
        layout.addWidget(hint_label)
        return row

    def retranslate_ai_settings(self) -> None:
        self.ai_settings_title_label.setText(self.tr("settings_ai"))
        self.ai_model_settings_title_label.setText(self.tr("ai_model_settings"))
        self.ai_base_url_label.setText(self.tr("ai_base_url"))
        self.ai_base_url_hint_label.setText(self.tr("ai_base_url_hint"))
        self.ai_api_key_label.setText(self.tr("ai_api_key"))
        self.ai_api_key_hint_label.setText(self.tr("ai_api_key_hint"))
        self.ai_clear_key_button.setText(self.tr("clear"))
        self.ai_default_model_label.setText(self.tr("ai_default_model"))
        self.ai_models_label.setText(self.tr("ai_models"))
        self.ai_model_name_edit.setPlaceholderText(self.tr("ai_model_name"))
        self.ai_add_model_button.setText(self.tr("add"))
        self.ai_filter_models_button.setText(self.tr("filter"))
        self.ai_delete_model_button.setText(self.tr("delete"))
        self.ai_set_default_model_button.setText(self.tr("set_default"))
        self.ai_fetch_models_button.setText(self.tr("fetch_models"))
        self.ai_models_endpoint_label.setText(self.tr("ai_models_endpoint"))
        self.ai_models_endpoint_hint_label.setText(self.tr("ai_models_endpoint_hint"))
        self.ai_timeout_label.setText(self.tr("ai_response_timeout"))
        self.ai_timeout_combo.setToolTip(self.tr("ai_response_timeout_hint"))
        self._retranslate_ai_timeout_combo()
        self.ai_execution_settings_title_label.setText(self.tr("ai_execution_settings"))
        self.ai_allow_database_write_label.setText(self.tr("ai_allow_database_write"))
        self.ai_allow_database_write_hint_label.setText(self.tr("ai_allow_database_write_hint"))
        self.ai_confirm_delete_actions_label.setText(self.tr("ai_confirm_delete_actions"))
        self.ai_confirm_bulk_actions_label.setText(self.tr("ai_confirm_bulk_actions"))
        self.ai_save_button.setText(self.tr("save"))
        self.ai_test_connection_button.setText(self.tr("test_connection"))
        self._update_ai_switch_texts()

    def _update_ai_switch_texts(self, *_args: object) -> None:
        for switch in (
            self.ai_allow_database_write_switch,
            self.ai_confirm_delete_actions_switch,
            self.ai_confirm_bulk_actions_switch,
        ):
            switch.setText(self.tr("switch_on") if switch.isChecked() else self.tr("switch_off"))

    def _set_ai_timeout_combo(self, seconds: int) -> None:
        value = 0 if int(seconds) <= 0 else int(seconds)
        if value not in AI_TIMEOUT_OPTIONS:
            value = 30
        for index in range(self.ai_timeout_combo.count()):
            if self.ai_timeout_combo.itemData(index) == value:
                self.ai_timeout_combo.setCurrentIndex(index)
                return
        self.ai_timeout_combo.setCurrentIndex(2)

    def _retranslate_ai_timeout_combo(self) -> None:
        current = self.ai_timeout_combo.currentData()
        self.ai_timeout_combo.blockSignals(True)
        for index in range(self.ai_timeout_combo.count()):
            seconds = int(self.ai_timeout_combo.itemData(index))
            text = self.tr("ai_timeout_unlimited") if seconds == 0 else self.tr("ai_timeout_seconds", seconds=seconds)
            self.ai_timeout_combo.setItemText(index, text)
        self.ai_timeout_combo.blockSignals(False)
        if isinstance(current, int):
            self._set_ai_timeout_combo(current)

    def _mark_ai_key_edited(self) -> None:
        self.ai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.ai_api_key_edit.setPlaceholderText("")
        self.ai_api_key_edit.setProperty("showingMaskedKey", False)

    def handle_ai_api_key_event(self, watched: object, event: object) -> bool:
        if not hasattr(self, "ai_api_key_edit"):
            return False
        if watched != self.ai_api_key_edit:
            return False
        try:
            event_type = event.type()
        except AttributeError:
            return False
        from PySide6.QtCore import QEvent

        if event_type == QEvent.Type.KeyPress and self.ai_api_key_edit.property("showingMaskedKey"):
            self.ai_api_key_edit.clear()
            self._mark_ai_key_edited()
        return False

    def clear_ai_api_key(self) -> None:
        self.ai_api_key_edit.clear()
        self.ai_api_key_edit.setPlaceholderText("")
        self.ai_api_key_edit.setProperty("storedApiKey", "")
        self.ai_api_key_edit.setProperty("showingMaskedKey", False)

    def _add_ai_model_list_item(self, model: str) -> None:
        text = model.strip()
        if not text:
            return
        for index in range(self.ai_models_list.count()):
            if self.ai_models_list.item(index).text() == text:
                return
        item = QListWidgetItem(text)
        self.ai_models_list.addItem(item)

    def add_ai_model_from_input(self) -> None:
        self._add_ai_model_list_item(self.ai_model_name_edit.text())
        self.ai_model_name_edit.clear()
        self.clear_ai_model_filter()

    def delete_selected_ai_model(self) -> None:
        for item in self.ai_models_list.selectedItems():
            self.ai_models_list.takeItem(self.ai_models_list.row(item))
        self.clear_ai_model_filter()

    def set_selected_ai_model_as_default(self) -> None:
        items = self.ai_models_list.selectedItems()
        if not items:
            return
        self.ai_default_model_edit.setText(items[0].text())

    def filter_ai_models_from_input(self) -> None:
        keyword = self.ai_model_name_edit.text().strip().casefold()
        for index in range(self.ai_models_list.count()):
            item = self.ai_models_list.item(index)
            item.setHidden(bool(keyword) and keyword not in item.text().casefold())

    def clear_ai_model_filter(self) -> None:
        for index in range(self.ai_models_list.count()):
            self.ai_models_list.item(index).setHidden(False)

    def fetch_ai_models_from_provider(self) -> None:
        try:
            client = OpenAICompatibleClient(
                self.ai_base_url_edit.text(),
                self._ai_api_key_from_form(),
                request_timeout_seconds=int(self.ai_timeout_combo.currentData() or 0),
            )
            models = client.list_models(self.ai_models_endpoint_edit.text())
        except Exception as exc:
            self.show_inline_message(
                self.ai_settings_message,
                self.tr("ai_fetch_models_failed", error=exc),
                ALERT_DANGER,
            )
            return
        sorted_model_ids = []
        for model in sorted(models, key=lambda item: item.id.casefold()):
            if model.id and model.id not in sorted_model_ids:
                sorted_model_ids.append(model.id)
        self.ai_models_list.clear()
        for model_id in sorted_model_ids:
            self._add_ai_model_list_item(model_id)
        self.clear_ai_model_filter()
        self.show_inline_message(
            self.ai_settings_message,
            self.tr("ai_models_imported", count=len(sorted_model_ids)),
            ALERT_INFO,
        )

    def apply_ai_execution_settings_from_controls(self, *_args: object) -> None:
        previous = (
            self.ai_allow_database_write,
            self.ai_confirm_delete_actions,
            self.ai_confirm_bulk_actions,
        )
        self._update_ai_switch_texts()
        try:
            save_ai_execution_settings(
                allow_database_write=self.ai_allow_database_write_switch.isChecked(),
                confirm_delete_actions=self.ai_confirm_delete_actions_switch.isChecked(),
                confirm_bulk_actions=self.ai_confirm_bulk_actions_switch.isChecked(),
                config_path=self.config_path,
            )
        except Exception as exc:
            self.ai_allow_database_write, self.ai_confirm_delete_actions, self.ai_confirm_bulk_actions = previous
            for switch, value in (
                (self.ai_allow_database_write_switch, previous[0]),
                (self.ai_confirm_delete_actions_switch, previous[1]),
                (self.ai_confirm_bulk_actions_switch, previous[2]),
            ):
                switch.blockSignals(True)
                switch.setChecked(value)
                switch.blockSignals(False)
            self._update_ai_switch_texts()
            self.show_inline_message(
                self.ai_execution_message,
                self.tr("could_not_save_ai_execution_settings", error=exc),
                ALERT_DANGER,
            )
            return

        self.ai_allow_database_write = self.ai_allow_database_write_switch.isChecked()
        self.ai_confirm_delete_actions = self.ai_confirm_delete_actions_switch.isChecked()
        self.ai_confirm_bulk_actions = self.ai_confirm_bulk_actions_switch.isChecked()
        self.show_inline_message(self.ai_execution_message, self.tr("ai_execution_settings_saved"), ALERT_INFO)

    def _ai_models_from_text(self) -> list[str]:
        models: list[str] = []
        for index in range(self.ai_models_list.count()):
            text = self.ai_models_list.item(index).text().strip()
            if text and text not in models:
                models.append(text)
        return models

    def _ai_api_key_from_form(self) -> str:
        if self.ai_api_key_edit.property("showingMaskedKey"):
            return str(self.ai_api_key_edit.property("storedApiKey") or "")
        return self.ai_api_key_edit.text().strip()

    def test_ai_connection(self) -> None:
        try:
            client = OpenAICompatibleClient(
                self.ai_base_url_edit.text(),
                self._ai_api_key_from_form(),
                request_timeout_seconds=int(self.ai_timeout_combo.currentData() or 0),
            )
            client.chat_completion(
                model=self.ai_default_model_edit.text(),
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with OK.",
                    }
                ],
            )
        except Exception as exc:
            self.show_inline_message(
                self.ai_settings_message,
                self.tr("ai_connection_test_failed", error=exc),
                ALERT_DANGER,
            )
            return
        self.show_inline_message(self.ai_settings_message, self.tr("ai_connection_test_succeeded"), ALERT_INFO)

    def save_ai_settings_from_form(self) -> None:
        try:
            save_ai_settings(
                base_url=self.ai_base_url_edit.text(),
                api_key=self._ai_api_key_from_form(),
                default_model=self.ai_default_model_edit.text(),
                models=self._ai_models_from_text(),
                models_endpoint=self.ai_models_endpoint_edit.text(),
                request_timeout_seconds=int(self.ai_timeout_combo.currentData() or 0),
                allow_database_write=self.ai_allow_database_write_switch.isChecked(),
                confirm_delete_actions=self.ai_confirm_delete_actions_switch.isChecked(),
                confirm_bulk_actions=self.ai_confirm_bulk_actions_switch.isChecked(),
                config_path=self.config_path,
            )
        except Exception as exc:
            self.show_inline_message(
                self.ai_settings_message,
                self.tr("could_not_save_ai_settings", error=exc),
                ALERT_DANGER,
            )
            return

        self.ai_base_url = self.ai_base_url_edit.text().strip()
        self.ai_api_key = self._ai_api_key_from_form()
        self.ai_default_model = self.ai_default_model_edit.text().strip()
        self.ai_models = self._ai_models_from_text()
        self.ai_models_endpoint = self.ai_models_endpoint_edit.text().strip()
        self.ai_request_timeout_seconds = int(self.ai_timeout_combo.currentData() or 0)
        self.ai_allow_database_write = self.ai_allow_database_write_switch.isChecked()
        self.ai_confirm_delete_actions = self.ai_confirm_delete_actions_switch.isChecked()
        self.ai_confirm_bulk_actions = self.ai_confirm_bulk_actions_switch.isChecked()
        self.ai_api_key_edit.setText("")
        self.ai_api_key_edit.setPlaceholderText(mask_api_key(self.ai_api_key))
        self.ai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.ai_api_key_edit.setProperty("storedApiKey", self.ai_api_key)
        self.ai_api_key_edit.setProperty("showingMaskedKey", bool(self.ai_api_key))
        self.show_inline_message(self.ai_settings_message, self.tr("ai_settings_saved"), ALERT_INFO)

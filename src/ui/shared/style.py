"""Application-wide Qt themes for MindTask."""

from __future__ import annotations

from typing import Dict


THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_OPTIONS = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)


LIGHT_COLORS = {
    "app_bg": "#eef2f7",
    "panel_bg": "#f8fafc",
    "input_bg": "#ffffff",
    "text": "#1f2937",
    "strong_text": "#111827",
    "muted_text": "#667085",
    "placeholder": "#94a3b8",
    "border": "#cfd8e3",
    "header_bg": "#e5eaf1",
    "grid": "#e5eaf1",
    "selection_bg": "#dbeafe",
    "selection_text": "#111827",
    "focus_border": "#2563eb",
    "empty_border": "#cfd8e3",
    "primary": "#2563eb",
    "primary_hover": "#1d4ed8",
    "secondary": "#475569",
    "secondary_hover": "#334155",
    "danger": "#b91c1c",
    "danger_hover": "#991b1b",
    "disabled_bg": "#cbd5e1",
    "disabled_text": "#64748b",
}

DARK_COLORS = {
    "app_bg": "#0b0b0c",
    "panel_bg": "#141414",
    "input_bg": "#1c1c1f",
    "text": "#e7e7e7",
    "strong_text": "#f5f5f5",
    "muted_text": "#a3a3a3",
    "placeholder": "#737373",
    "border": "#333333",
    "header_bg": "#242424",
    "grid": "#303030",
    "selection_bg": "#3a3a3d",
    "selection_text": "#ffffff",
    "focus_border": "#60a5fa",
    "empty_border": "#3f3f46",
    "primary": "#3f3f46",
    "primary_hover": "#52525b",
    "secondary": "#2f2f33",
    "secondary_hover": "#444448",
    "danger": "#dc2626",
    "danger_hover": "#b91c1c",
    "disabled_bg": "#27272a",
    "disabled_text": "#71717a",
}

LIGHT_BADGE_COLORS = {
    "status": {
        "not_started": ("#64748b", "#f1f5f9"),
        "in_progress": ("#2563eb", "#eff6ff"),
        "suspended": ("#b7791f", "#fffbeb"),
        "completed": ("#2f855a", "#f0fff4"),
    },
    "priority": {
        "None": ("#64748b", "#f8fafc"),
        "Low": ("#2f855a", "#f0fff4"),
        "Medium": ("#b7791f", "#fffbeb"),
        "High": ("#c2410c", "#fff7ed"),
    },
    "history": {
        "active": ("#2f855a", "#f0fff4"),
        "undone": ("#64748b", "#f1f5f9"),
    },
}

DARK_BADGE_COLORS = {
    "status": {
        "not_started": ("#d4d4d4", "#262626"),
        "in_progress": ("#f5f5f5", "#3f3f46"),
        "suspended": ("#f5f5f5", "#57534e"),
        "completed": ("#f5f5f5", "#3f4a3f"),
    },
    "priority": {
        "None": ("#d4d4d4", "#262626"),
        "Low": ("#f5f5f5", "#3f4a3f"),
        "Medium": ("#f5f5f5", "#57534e"),
        "High": ("#f5f5f5", "#5a3a32"),
    },
    "history": {
        "active": ("#f5f5f5", "#3f4a3f"),
        "undone": ("#d4d4d4", "#262626"),
    },
}


def is_dark_system_theme(app) -> bool:
    try:
        from PySide6.QtCore import Qt

        color_scheme = app.styleHints().colorScheme()
        if color_scheme == Qt.ColorScheme.Dark:
            return True
        if color_scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass

    color = app.palette().color(app.palette().ColorRole.Window)
    return color.lightness() < 128


def resolve_theme(theme: str, app=None) -> str:
    if theme == THEME_SYSTEM:
        return THEME_DARK if app is not None and is_dark_system_theme(app) else THEME_LIGHT
    return theme if theme in {THEME_LIGHT, THEME_DARK} else THEME_LIGHT


def colors_for_theme(theme: str, app=None) -> Dict[str, str]:
    return DARK_COLORS if resolve_theme(theme, app) == THEME_DARK else LIGHT_COLORS


def badge_colors_for_theme(theme: str, app=None):
    return DARK_BADGE_COLORS if resolve_theme(theme, app) == THEME_DARK else LIGHT_BADGE_COLORS


def _base_style(colors: Dict[str, str]) -> str:
    return f"""
QWidget {{
    background: {colors["app_bg"]};
    color: {colors["text"]};
    font-size: 13px;
}}
QMainWindow, QDialog, QMessageBox {{
    background: {colors["app_bg"]};
    color: {colors["text"]};
}}
QMessageBox QLabel {{
    background: transparent;
    color: {colors["text"]};
}}
QFrame#Sidebar, QFrame#DetailPanel {{
    background: {colors["panel_bg"]};
    border: 1px solid {colors["border"]};
    color: {colors["text"]};
}}
QFrame#BottomNav {{
    background: {colors["input_bg"]};
    border-top: 1px solid {colors["border"]};
    color: {colors["text"]};
}}
QWidget#TransparentRow,
QStackedWidget#PaginationPageStack,
QStackedWidget#PaginationPageStack QWidget {{
    background: transparent;
    border: none;
}}
QLineEdit, QTextEdit, QTextBrowser, QComboBox, QDateEdit, QSpinBox, QListWidget, QTableWidget, QTreeWidget {{
    background: {colors["input_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
    padding: 6px;
    selection-background-color: {colors["selection_bg"]};
    selection-color: {colors["selection_text"]};
}}
QWidget#AIMessageContainer {{
    background: transparent;
    border: none;
}}
QScrollArea#AIChatMessagesScroll,
QScrollArea#AIChatMessagesScroll > QWidget,
QScrollArea#AIChatMessagesScroll > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QFrame#AIEmptyChatState {{
    background: transparent;
    border: none;
}}
QLabel#AIEmptyChatText {{
    color: {colors["muted_text"]};
    font-size: 18px;
    font-weight: 500;
}}
QFrame#DetailPanel QPushButton {{
    border: 1px solid transparent;
    padding: 6px 11px;
}}
QLineEdit#SearchInput {{
    min-width: 220px;
}}
QLineEdit#SearchInput:focus {{
    border: 1px solid {colors["focus_border"]};
}}
QLineEdit#PaginationPageEdit {{
    min-width: 56px;
    max-width: 56px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
}}
QLineEdit#PaginationPageEdit:focus {{
    border: 1px solid {colors["focus_border"]};
}}
QComboBox#CompactComboBox {{
    min-width: 108px;
    max-width: 132px;
}}
QSpinBox#CompactSpinBox {{
    min-width: 80px;
    max-width: 96px;
}}
QLineEdit::placeholder {{
    color: {colors["placeholder"]};
}}
QComboBox QAbstractItemView, QDateEdit QAbstractItemView {{
    background: {colors["input_bg"]};
    color: {colors["text"]};
    selection-background-color: {colors["selection_bg"]};
    selection-color: {colors["selection_text"]};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: {colors["panel_bg"]};
    border-left: 1px solid {colors["border"]};
    width: 16px;
}}
QLabel {{
    background: transparent;
    color: {colors["text"]};
}}
QWidget#TransparentRow, QCheckBox {{
    background: transparent;
}}
QScrollArea#DetailScrollArea, QScrollArea#DetailScrollArea > QWidget, QScrollArea#DetailScrollArea > QWidget > QWidget {{
    background: transparent;
    border: 0;
}}
QWidget#DetailActionBar {{
    background: transparent;
    border-top: 1px solid {colors["border"]};
}}
QLabel#SectionLabel {{
    color: {colors["strong_text"]};
    font-weight: 600;
    font-size: 14px;
}}
QLabel#MutedLabel {{
    color: {colors["muted_text"]};
}}
QFrame#AIUserMessage, QFrame#AIAssistantMessage {{
    border: 1px solid {colors["border"]};
    border-left: 3px solid {colors["focus_border"]};
    border-radius: 6px;
}}
QFrame#AIUserMessage {{
    background: {"#eef6ff" if colors["app_bg"] == "#eef2f7" else "#1d2430"};
}}
QFrame#AIAssistantMessage {{
    background: {colors["input_bg"]};
    border-left: 3px solid {colors["secondary"]};
}}
QLabel#AIMessageRole {{
    color: {colors["strong_text"]};
    font-weight: 600;
    font-size: 12px;
    padding: 0;
    margin: 0;
}}
QLabel#AIMessageHeaderStatus {{
    color: {colors["muted_text"]};
    font-size: 12px;
    padding: 0;
    margin: 0;
}}
QLabel#AIMessageMeta {{
    color: {colors["muted_text"]};
    font-size: 12px;
    padding: 0;
    margin: 0;
}}
QTextBrowser#AIMessageBody {{
    background: transparent;
    border: none;
    border-radius: 0;
    color: {colors["text"]};
    font-size: 13px;
    padding: 0;
    selection-background-color: {colors["selection_bg"]};
    selection-color: {colors["selection_text"]};
}}
QFrame#AIActionSeparator {{
    color: {colors["border"]};
    background: {colors["border"]};
    max-height: 1px;
}}
QLabel#AIActionTitle {{
    color: {colors["muted_text"]};
    font-weight: 600;
    font-size: 12px;
}}
QToolButton#AIActionToggle {{
    background: transparent;
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
    padding: 4px 6px;
    text-align: left;
}}
QToolButton#AIActionToggle:hover {{
    background: {colors["selection_bg"]};
}}
QLabel#AIActionDetail {{
    color: {colors["muted_text"]};
    background: {colors["panel_bg"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
    padding: 6px;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
}}
QLabel#EmptyState {{
    color: {colors["muted_text"]};
    background: {colors["input_bg"]};
    border: 1px dashed {colors["empty_border"]};
    border-radius: 6px;
    padding: 24px;
}}
QMenu {{
    background: {colors["input_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 10px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {colors["selection_bg"]};
    color: {colors["selection_text"]};
}}
"""


def _detail_field_style(colors: Dict[str, str], resolved: str) -> str:
    return f"""
QFrame#DetailPanel QLineEdit[detailModified="true"],
QFrame#DetailPanel QTextEdit[detailModified="true"],
QFrame#DetailPanel QTextBrowser[detailModified="true"],
QFrame#DetailPanel QComboBox[detailModified="true"],
QFrame#DetailPanel QDateEdit[detailModified="true"] {{
    border: 1px solid {"#d97706" if resolved == THEME_LIGHT else "#b7791f"};
}}
QFrame#DetailPanel QLineEdit[detailInvalid="true"],
QFrame#DetailPanel QComboBox[detailInvalid="true"],
QFrame#DetailPanel QDateEdit[detailInvalid="true"],
QFrame#DetailPanel QSpinBox[detailInvalid="true"],
QDialog QLineEdit[detailInvalid="true"],
QDialog QComboBox[detailInvalid="true"],
QDialog QDateEdit[detailInvalid="true"] {{
    border: 1px solid {colors["danger"]};
}}
QFrame#DetailPanel QLineEdit:focus,
QFrame#DetailPanel QLineEdit#ChecklistInlineEditor,
QFrame#DetailPanel QLineEdit#ChecklistInlineEditor:focus,
QFrame#DetailPanel QTextEdit:focus,
QFrame#DetailPanel QTextBrowser:focus,
QFrame#DetailPanel QComboBox:focus,
QFrame#DetailPanel QDateEdit:focus,
QFrame#DetailPanel QSpinBox:focus,
QFrame#DetailPanel QTreeWidget:focus,
QDialog QLineEdit:focus,
QDialog QTextEdit:focus,
QDialog QTextBrowser:focus,
QDialog QComboBox:focus,
QDialog QDateEdit:focus {{
    border: 1px solid {colors["focus_border"]};
}}
"""


def _checklist_style(colors: Dict[str, str], resolved: str) -> str:
    return f"""
QFrame#DetailPanel QPushButton#ChecklistDoneButton {{
    background: {colors["input_bg"]};
    color: {colors["muted_text"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
    padding: 0;
    font-weight: 800;
}}
QFrame#DetailPanel QPushButton#ChecklistDoneButton:hover {{
    background: {colors["selection_bg"]};
    border: 1px solid {colors["focus_border"]};
}}
QFrame#DetailPanel QPushButton#ChecklistDoneButton:checked {{
    background: {"#eff6ff" if resolved == THEME_LIGHT else colors["primary"]};
    border: 1px solid {colors["focus_border"] if resolved == THEME_LIGHT else colors["primary"]};
    color: {colors["focus_border"] if resolved == THEME_LIGHT else "#ffffff"};
}}
QFrame#DetailPanel QPushButton#ChecklistDoneButton:checked:hover {{
    background: {"#dbeafe" if resolved == THEME_LIGHT else colors["primary"]};
    border: 1px solid {colors["focus_border"]};
}}
QLabel#ChecklistItemLabel {{
    color: {colors["text"]};
    padding: 4px 2px;
}}
"""


def _alert_style(resolved: str) -> str:
    return f"""
QWidget#AlertMessage {{
    background: transparent;
    min-width: 0;
}}
QLabel#AlertIcon {{
    background: transparent;
    border-radius: 9px;
    font-weight: 800;
    padding: 0;
}}
QLabel#AlertText {{
    background: transparent;
    font-weight: 600;
}}
QLabel#AlertIcon[alertSeverity="0"] {{
    color: {"#2563eb" if resolved == THEME_LIGHT else "#60a5fa"};
    border: 1px solid {"#2563eb" if resolved == THEME_LIGHT else "#60a5fa"};
}}
QLabel#AlertText[alertSeverity="0"] {{
    color: {"#2563eb" if resolved == THEME_LIGHT else "#60a5fa"};
}}
QLabel#AlertIcon[alertSeverity="1"] {{
    color: {"#d97706" if resolved == THEME_LIGHT else "#fbbf24"};
    border: 1px solid {"#d97706" if resolved == THEME_LIGHT else "#fbbf24"};
}}
QLabel#AlertText[alertSeverity="1"] {{
    color: {"#d97706" if resolved == THEME_LIGHT else "#fbbf24"};
}}
QLabel#AlertIcon[alertSeverity="2"] {{
    color: {"#dc2626" if resolved == THEME_LIGHT else "#f87171"};
    border: 1px solid {"#dc2626" if resolved == THEME_LIGHT else "#f87171"};
}}
QLabel#AlertText[alertSeverity="2"] {{
    color: {"#dc2626" if resolved == THEME_LIGHT else "#f87171"};
}}
"""


def _shortcut_style(colors: Dict[str, str], resolved: str) -> str:
    return f"""
QFrame#ShortcutRow {{
    border: 1px solid transparent;
    border-radius: 6px;
}}
QFrame#ShortcutRow[shortcutActive="true"] {{
    background: {colors["selection_bg"]};
    border: 1px solid {colors["primary"]};
}}
QFrame#ShortcutRow[shortcutModified="true"] {{
    background: {"#fffbeb" if resolved == THEME_LIGHT else "#3f3420"};
    border: 1px solid {"#d97706" if resolved == THEME_LIGHT else "#b7791f"};
}}
QFrame#ShortcutRow[shortcutDuplicate="true"] {{
    background: {"#fee2e2" if resolved == THEME_LIGHT else "#4a2424"};
    border: 1px solid {colors["danger"]};
}}
QFrame#ShortcutRow[shortcutInvalid="true"] {{
    background: {"#fee2e2" if resolved == THEME_LIGHT else "#4a2424"};
    border: 1px solid {colors["danger"]};
}}
"""


def _button_style(colors: Dict[str, str]) -> str:
    return f"""
QPushButton {{
    background: {colors["primary"]};
    color: #ffffff;
    border: 0;
    border-radius: 4px;
    padding: 7px 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {colors["primary_hover"]};
}}
QPushButton:disabled {{
    background: {colors["disabled_bg"]};
    color: {colors["disabled_text"]};
}}
QPushButton#SecondaryButton {{
    background: {colors["secondary"]};
}}
QPushButton#SecondaryButton:hover {{
    background: {colors["secondary_hover"]};
}}
QPushButton#DangerButton {{
    background: {colors["danger"]};
}}
QPushButton#DangerButton:hover {{
    background: {colors["danger_hover"]};
}}
QPushButton#IconButton {{
    background: {colors["panel_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    padding: 0;
}}
QPushButton#IconButton:hover {{
    background: {colors["selection_bg"]};
}}
QPushButton#DangerIconButton {{
    background: {colors["danger"]};
    color: #ffffff;
    border: 1px solid transparent;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    padding: 0;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
}}
QPushButton#DangerIconButton:hover {{
    background: {colors["danger_hover"]};
}}
QPushButton#NavButton {{
    background: transparent;
    color: {colors["muted_text"]};
    border: 1px solid transparent;
    border-radius: 4px;
    min-width: 96px;
    padding: 7px 14px;
}}
QPushButton#NavButton:hover {{
    background: {colors["panel_bg"]};
    color: {colors["text"]};
}}
QPushButton#NavButtonActive {{
    background: {colors["selection_bg"]};
    color: {colors["selection_text"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
    min-width: 96px;
    padding: 7px 14px;
}}
QDialogButtonBox QPushButton {{
    min-width: 76px;
}}
QFrame#DetailPanel QPushButton#PrimaryButton,
QFrame#DetailPanel QPushButton#SecondaryButton,
QFrame#DetailPanel QPushButton#DangerButton,
QDialog QDialogButtonBox QPushButton {{
    border: 1px solid transparent;
    padding: 6px 11px;
}}
QFrame#DetailPanel QPushButton:focus,
QDialog QPushButton:focus {{
    border: 1px solid {colors["focus_border"]};
}}
QFrame#DetailPanel QPushButton#AIChatSendButton {{
    min-width: 64px;
    max-width: 64px;
    min-height: 96px;
    max-height: 96px;
    padding: 0;
}}
"""


def _table_and_list_style(colors: Dict[str, str]) -> str:
    return f"""
QFrame#TaskActions {{
    background: transparent;
    border: 0;
}}
QHeaderView::section {{
    background: {colors["header_bg"]};
    color: {colors["text"]};
    border: 0;
    border-right: 1px solid {colors["border"]};
    padding: 7px 8px;
    font-weight: 600;
}}
QTableWidget#TaskTable {{
    background: {colors["input_bg"]};
    color: {colors["text"]};
    gridline-color: {colors["grid"]};
    alternate-background-color: {colors["panel_bg"]};
}}
QTableWidget#TaskTable::item {{
    padding: 4px;
}}
QTableWidget#TaskTable::item:selected {{
    background: {colors["selection_bg"]};
    color: {colors["selection_text"]};
}}
QListWidget#ProjectList {{
    background: {colors["input_bg"]};
    color: {colors["text"]};
}}
QListWidget#ProjectList::item {{
    background: {colors["input_bg"]};
    color: {colors["text"]};
    padding: 7px 6px;
    border-radius: 4px;
}}
QListWidget#ProjectList::item:selected {{
    background: {colors["selection_bg"]};
    color: {colors["selection_text"]};
}}
QListWidget#AIChatSessionList {{
    background: transparent;
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
}}
QListWidget#AIChatSessionList::item {{
    background: transparent;
    color: {colors["text"]};
    padding: 7px 6px;
    border-radius: 4px;
}}
QListWidget#AIChatSessionList::item:hover {{
    background: {colors["input_bg"]};
}}
QListWidget#AIChatSessionList::item:selected {{
    background: {colors["selection_bg"]};
    color: {colors["selection_text"]};
}}
QListWidget#DueFilterList {{
    background: {colors["input_bg"]};
    color: {colors["text"]};
}}
QListWidget#DueFilterList::item {{
    background: {colors["input_bg"]};
    color: {colors["text"]};
    padding: 4px 6px;
    border-radius: 4px;
}}
QListWidget#DueFilterList::item:selected {{
    background: {colors["selection_bg"]};
    color: {colors["selection_text"]};
}}
"""


def build_app_style(theme: str = THEME_SYSTEM, app=None) -> str:
    resolved = resolve_theme(theme, app)
    colors = colors_for_theme(theme, app)
    return "".join(
        (
            _base_style(colors),
            _detail_field_style(colors, resolved),
            _checklist_style(colors, resolved),
            _alert_style(resolved),
            _shortcut_style(colors, resolved),
            _button_style(colors),
            _table_and_list_style(colors),
        )
    )

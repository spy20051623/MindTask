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


def build_app_style(theme: str = THEME_SYSTEM, app=None) -> str:
    resolved = resolve_theme(theme, app)
    colors = colors_for_theme(theme, app)
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
QLineEdit, QTextEdit, QComboBox, QDateEdit, QListWidget, QTableWidget {{
    background: {colors["input_bg"]};
    color: {colors["text"]};
    border: 1px solid {colors["border"]};
    border-radius: 4px;
    padding: 6px;
    selection-background-color: {colors["selection_bg"]};
    selection-color: {colors["selection_text"]};
}}
QLineEdit#SearchInput {{
    min-width: 220px;
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
QLabel {{
    background: transparent;
    color: {colors["text"]};
}}
QWidget#TransparentRow {{
    background: transparent;
}}
QLabel#SectionLabel {{
    color: {colors["strong_text"]};
    font-weight: 600;
    font-size: 14px;
}}
QLabel#MutedLabel {{
    color: {colors["muted_text"]};
}}
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
QLabel#EmptyState {{
    color: {colors["muted_text"]};
    background: {colors["input_bg"]};
    border: 1px dashed {colors["empty_border"]};
    border-radius: 6px;
    padding: 24px;
}}
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

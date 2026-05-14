"""Shared UI constants for MindTask."""

THEME_TRANSLATION_KEYS = {
    "system": "theme_system",
    "dark": "theme_dark",
    "light": "theme_light",
}

STATUS_LABELS = {
    0: "not_started",
    1: "in_progress",
    2: "suspended",
    3: "completed",
}
STATUS_VALUES = {value: key for key, value in STATUS_LABELS.items()}
STATUS_TRANSLATION_KEYS = {
    0: "status_not_started",
    1: "status_in_progress",
    2: "status_suspended",
    3: "status_completed",
}

PRIORITY_LABELS = {
    0: "None",
    1: "Low",
    2: "Medium",
    3: "High",
}
PRIORITY_TRANSLATION_KEYS = {
    0: "priority_none",
    1: "priority_low",
    2: "priority_medium",
    3: "priority_high",
}

HISTORY_ACTION_TRANSLATION_KEYS = {
    "create": "action_create",
    "delete": "action_delete",
    "update": "action_update",
}
HISTORY_ENTITY_TRANSLATION_KEYS = {
    "project": "entity_project",
    "tag": "entity_tag",
    "task": "entity_task",
    "task_tag": "entity_task_tag",
}

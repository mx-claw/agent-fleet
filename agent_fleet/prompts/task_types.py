from __future__ import annotations

from enum import StrEnum


class TaskType(StrEnum):
    FEATURE_IMPLEMENTATION = "feature_implementation"


def normalize_task_type(task_type: str) -> TaskType:
    value = task_type.strip().lower()
    try:
        return TaskType(value)
    except ValueError as error:
        available = ", ".join(t.value for t in TaskType)
        raise ValueError(f"unknown task_type: {task_type!r}. available: {available}") from error


def task_type_choices() -> list[str]:
    return [t.value for t in TaskType]

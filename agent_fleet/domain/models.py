from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    kind: str
    payload: str
    status: TaskStatus
    created_at: str
    updated_at: str
    queued_at: str
    started_at: str | None = None
    finished_at: str | None = None


@dataclass(frozen=True, slots=True)
class Execution:
    id: str
    task_id: str
    agent_name: str
    status: TaskStatus
    created_at: str
    process_id: int | None = None
    exit_code: int | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    id: int
    execution_id: str
    sequence_number: int
    source: str
    event_type: str
    payload: str
    created_at: str

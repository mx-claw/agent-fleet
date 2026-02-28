from __future__ import annotations

from enum import StrEnum
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, Relationship, SQLModel


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    kind: str
    payload: str
    status: TaskStatus = Field(default=TaskStatus.QUEUED, index=True)
    created_at: str
    updated_at: str
    queued_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    executions: list["Execution"] = Relationship(back_populates="task")


class Execution(SQLModel, table=True):
    __tablename__ = "executions"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    task_id: str = Field(foreign_key="tasks.id", index=True)
    agent_name: str
    status: TaskStatus = Field(default=TaskStatus.QUEUED)
    created_at: str
    process_id: Optional[int] = None
    exit_code: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    task: Optional[Task] = Relationship(back_populates="executions")
    events: list["ExecutionEvent"] = Relationship(back_populates="execution")


class ExecutionEvent(SQLModel, table=True):
    __tablename__ = "execution_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    execution_id: str = Field(foreign_key="executions.id", index=True)
    sequence_number: int
    source: str
    event_type: str
    payload: str
    created_at: str

    execution: Optional[Execution] = Relationship(back_populates="events")

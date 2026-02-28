from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from agent_fleet.domain.models import Execution, ExecutionEvent, Task, TaskStatus
from agent_fleet.persistence.schema import initialize_schema


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="microseconds")


class SQLiteRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            initialize_schema(connection)

    @contextmanager
    def connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def enqueue_task(self, *, kind: str, payload: str) -> Task:
        task_id = str(uuid4())
        timestamp = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    id, kind, payload, status, created_at, updated_at, queued_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    task_id,
                    kind,
                    payload,
                    TaskStatus.QUEUED.value,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row)

    def dequeue_next_task(self) -> Task | None:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT *
                FROM tasks
                WHERE status = ?
                ORDER BY queued_at ASC, id ASC
                LIMIT 1
                """,
                (TaskStatus.QUEUED.value,),
            ).fetchone()
            if row is None:
                return None

            started_at = utc_now()
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?, started_at = ?
                WHERE id = ?
                """,
                (TaskStatus.RUNNING.value, started_at, started_at, row["id"]),
            )
            updated_row = connection.execute("SELECT * FROM tasks WHERE id = ?", (row["id"],)).fetchone()
        return self._row_to_task(updated_row)

    def mark_task_succeeded(self, task_id: str) -> Task:
        return self._update_task_status(task_id, TaskStatus.SUCCEEDED)

    def mark_task_failed(self, task_id: str) -> Task:
        return self._update_task_status(task_id, TaskStatus.FAILED)

    def mark_task_canceled(self, task_id: str) -> Task:
        return self._update_task_status(task_id, TaskStatus.CANCELED)

    def get_task(self, task_id: str) -> Task | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def list_tasks(self, *, limit: int = 20) -> list[Task]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM tasks
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def create_execution(self, *, task_id: str, agent_name: str) -> Execution:
        execution_id = str(uuid4())
        timestamp = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO executions (
                    id, task_id, agent_name, status, process_id, exit_code, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, NULL, NULL, ?, NULL, NULL)
                """,
                (
                    execution_id,
                    task_id,
                    agent_name,
                    TaskStatus.QUEUED.value,
                    timestamp,
                ),
            )
            row = connection.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
        return self._row_to_execution(row)

    def mark_execution_running(self, *, execution_id: str, process_id: int | None) -> Execution:
        timestamp = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE executions
                SET status = ?, process_id = ?, started_at = ?, finished_at = NULL
                WHERE id = ?
                """,
                (TaskStatus.RUNNING.value, process_id, timestamp, execution_id),
            )
            row = connection.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
        return self._row_to_execution(row)

    def mark_execution_succeeded(self, *, execution_id: str, exit_code: int) -> Execution:
        return self._finish_execution(
            execution_id=execution_id,
            status=TaskStatus.SUCCEEDED,
            exit_code=exit_code,
        )

    def mark_execution_failed(self, *, execution_id: str, exit_code: int | None) -> Execution:
        return self._finish_execution(
            execution_id=execution_id,
            status=TaskStatus.FAILED,
            exit_code=exit_code,
        )

    def get_execution(self, execution_id: str) -> Execution | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
        return self._row_to_execution(row) if row else None

    def list_executions_for_task(self, task_id: str) -> list[Execution]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM executions
                WHERE task_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (task_id,),
            ).fetchall()
        return [self._row_to_execution(row) for row in rows]

    def append_execution_event(
        self,
        *,
        execution_id: str,
        sequence_number: int,
        source: str,
        event_type: str,
        payload: str,
    ) -> ExecutionEvent:
        timestamp = utc_now()
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO execution_events (
                    execution_id, sequence_number, source, event_type, payload, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (execution_id, sequence_number, source, event_type, payload, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM execution_events WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._row_to_execution_event(row)

    def list_execution_events(self, execution_id: str) -> list[ExecutionEvent]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM execution_events
                WHERE execution_id = ?
                ORDER BY sequence_number ASC, id ASC
                """,
                (execution_id,),
            ).fetchall()
        return [self._row_to_execution_event(row) for row in rows]

    def get_task_history(self, task_id: str) -> dict[str, object] | None:
        task = self.get_task(task_id)
        if task is None:
            return None

        executions = self.list_executions_for_task(task_id)
        history = []
        for execution in executions:
            history.append(
                {
                    "execution": execution,
                    "events": self.list_execution_events(execution.id),
                }
            )
        return {"task": task, "executions": history}

    def _update_task_status(self, task_id: str, status: TaskStatus) -> Task:
        timestamp = utc_now()
        finished_at = timestamp if status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELED} else None
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?, finished_at = COALESCE(?, finished_at)
                WHERE id = ?
                """,
                (status.value, timestamp, finished_at, task_id),
            )
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row)

    def _finish_execution(
        self,
        *,
        execution_id: str,
        status: TaskStatus,
        exit_code: int | None,
    ) -> Execution:
        timestamp = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE executions
                SET status = ?, exit_code = ?, finished_at = ?
                WHERE id = ?
                """,
                (status.value, exit_code, timestamp, execution_id),
            )
            row = connection.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
        return self._row_to_execution(row)

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            kind=row["kind"],
            payload=row["payload"],
            status=TaskStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            queued_at=row["queued_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    @staticmethod
    def _row_to_execution(row: sqlite3.Row) -> Execution:
        return Execution(
            id=row["id"],
            task_id=row["task_id"],
            agent_name=row["agent_name"],
            status=TaskStatus(row["status"]),
            created_at=row["created_at"],
            process_id=row["process_id"],
            exit_code=row["exit_code"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    @staticmethod
    def _row_to_execution_event(row: sqlite3.Row) -> ExecutionEvent:
        return ExecutionEvent(
            id=row["id"],
            execution_id=row["execution_id"],
            sequence_number=row["sequence_number"],
            source=row["source"],
            event_type=row["event_type"],
            payload=row["payload"],
            created_at=row["created_at"],
        )

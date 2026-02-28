from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from agent_fleet.domain.models import Execution, ExecutionEvent, Task, TaskStatus
from agent_fleet.persistence.schema import create_sqlite_engine, initialize_schema


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="microseconds")


class SQLiteRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.engine = create_sqlite_engine(self.database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        initialize_schema(self.engine)

    def enqueue_task(self, *, kind: str, payload: str) -> Task:
        timestamp = utc_now()
        task = Task(
            kind=kind,
            payload=payload,
            status=TaskStatus.QUEUED,
            created_at=timestamp,
            updated_at=timestamp,
            queued_at=timestamp,
        )
        with Session(self.engine) as session:
            session.add(task)
            session.commit()
            session.refresh(task)
        return task

    def dequeue_next_task(self) -> Task | None:
        with Session(self.engine) as session:
            task = session.exec(
                select(Task)
                .where(Task.status == TaskStatus.QUEUED)
                .order_by(Task.queued_at.asc(), Task.id.asc())
                .limit(1)
            ).first()
            if task is None:
                return None

            started_at = utc_now()
            task.status = TaskStatus.RUNNING
            task.updated_at = started_at
            task.started_at = started_at
            session.add(task)
            session.commit()
            session.refresh(task)
            return task

    def mark_task_succeeded(self, task_id: str) -> Task:
        return self._update_task_status(task_id, TaskStatus.SUCCEEDED)

    def mark_task_failed(self, task_id: str) -> Task:
        return self._update_task_status(task_id, TaskStatus.FAILED)

    def mark_task_canceled(self, task_id: str) -> Task:
        return self._update_task_status(task_id, TaskStatus.CANCELED)

    def get_task(self, task_id: str) -> Task | None:
        with Session(self.engine) as session:
            return session.get(Task, task_id)

    def list_tasks(self, *, limit: int = 20) -> list[Task]:
        with Session(self.engine) as session:
            return list(
                session.exec(
                    select(Task).order_by(Task.created_at.desc(), Task.id.desc()).limit(limit)
                )
            )

    def create_execution(self, *, task_id: str, agent_name: str) -> Execution:
        execution = Execution(
            task_id=task_id,
            agent_name=agent_name,
            status=TaskStatus.QUEUED,
            created_at=utc_now(),
        )
        with Session(self.engine) as session:
            session.add(execution)
            session.commit()
            session.refresh(execution)
        return execution

    def mark_execution_running(self, *, execution_id: str, process_id: int | None) -> Execution:
        with Session(self.engine) as session:
            execution = self._require_execution(session, execution_id)
            execution.status = TaskStatus.RUNNING
            execution.process_id = process_id
            execution.started_at = utc_now()
            execution.finished_at = None
            session.add(execution)
            session.commit()
            session.refresh(execution)
            return execution

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
        with Session(self.engine) as session:
            return session.get(Execution, execution_id)

    def list_executions_for_task(self, task_id: str) -> list[Execution]:
        with Session(self.engine) as session:
            return list(
                session.exec(
                    select(Execution)
                    .where(Execution.task_id == task_id)
                    .order_by(Execution.created_at.asc(), Execution.id.asc())
                )
            )

    def append_execution_event(
        self,
        *,
        execution_id: str,
        sequence_number: int,
        source: str,
        event_type: str,
        payload: str,
    ) -> ExecutionEvent:
        event = ExecutionEvent(
            execution_id=execution_id,
            sequence_number=sequence_number,
            source=source,
            event_type=event_type,
            payload=payload,
            created_at=utc_now(),
        )
        with Session(self.engine) as session:
            session.add(event)
            session.commit()
            session.refresh(event)
        return event

    def list_execution_events(self, execution_id: str) -> list[ExecutionEvent]:
        with Session(self.engine) as session:
            return list(
                session.exec(
                    select(ExecutionEvent)
                    .where(ExecutionEvent.execution_id == execution_id)
                    .order_by(ExecutionEvent.sequence_number.asc(), ExecutionEvent.id.asc())
                )
            )

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
        with Session(self.engine) as session:
            task = self._require_task(session, task_id)
            timestamp = utc_now()
            task.status = status
            task.updated_at = timestamp
            if status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELED}:
                task.finished_at = timestamp
            session.add(task)
            session.commit()
            session.refresh(task)
            return task

    def _finish_execution(
        self,
        *,
        execution_id: str,
        status: TaskStatus,
        exit_code: int | None,
    ) -> Execution:
        with Session(self.engine) as session:
            execution = self._require_execution(session, execution_id)
            execution.status = status
            execution.exit_code = exit_code
            execution.finished_at = utc_now()
            session.add(execution)
            session.commit()
            session.refresh(execution)
            return execution

    @staticmethod
    def _require_task(session: Session, task_id: str) -> Task:
        task = session.get(Task, task_id)
        if task is None:
            raise ValueError(f"task not found: {task_id}")
        return task

    @staticmethod
    def _require_execution(session: Session, execution_id: str) -> Execution:
        execution = session.get(Execution, execution_id)
        if execution is None:
            raise ValueError(f"execution not found: {execution_id}")
        return execution

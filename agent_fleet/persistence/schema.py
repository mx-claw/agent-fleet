from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine
from sqlalchemy.engine import Engine

from agent_fleet.domain import models as _models  # noqa: F401  # ensure model metadata is loaded


def create_sqlite_engine(database_path: str | Path) -> Engine:
    path = Path(database_path)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def initialize_schema(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_columns(engine)
    _create_indexes(engine)
    _backfill_execution_events(engine)


def _ensure_columns(engine: Engine) -> None:
    migration_columns = {
        "executions": (
            ("process_id", "INTEGER"),
            ("exit_code", "INTEGER"),
        ),
        "execution_events": (
            ("sequence_number", "INTEGER"),
            ("source", "TEXT"),
        ),
    }

    with engine.begin() as connection:
        for table_name, columns in migration_columns.items():
            existing_columns = {
                row[1]
                for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
            }
            for column_name, column_type in columns:
                if column_name not in existing_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )


def _create_indexes(engine: Engine) -> None:
    statements = (
        "CREATE INDEX IF NOT EXISTS idx_tasks_status_queued_at ON tasks(status, queued_at, id)",
        "CREATE INDEX IF NOT EXISTS idx_executions_task_id ON executions(task_id)",
        "CREATE INDEX IF NOT EXISTS idx_execution_events_execution_id ON execution_events(execution_id, id)",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _backfill_execution_events(engine: Engine) -> None:
    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(execution_events)").fetchall()
        }

        if "sequence_number" in columns:
            connection.execute(
                text(
                    """
                    WITH numbered AS (
                        SELECT id, ROW_NUMBER() OVER (PARTITION BY execution_id ORDER BY id ASC) AS seq
                        FROM execution_events
                    )
                    UPDATE execution_events
                    SET sequence_number = (
                        SELECT seq
                        FROM numbered
                        WHERE numbered.id = execution_events.id
                    )
                    WHERE sequence_number IS NULL
                    """
                )
            )

        if "source" in columns:
            connection.execute(
                text(
                    """
                    UPDATE execution_events
                    SET source = 'json'
                    WHERE source IS NULL
                    """
                )
            )

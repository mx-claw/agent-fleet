from __future__ import annotations

import sqlite3

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'canceled')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        queued_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS executions (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        agent_name TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'canceled')),
        process_id INTEGER,
        exit_code INTEGER,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS execution_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        execution_id TEXT NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
        sequence_number INTEGER NOT NULL,
        source TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tasks_status_queued_at ON tasks(status, queued_at, id)",
    "CREATE INDEX IF NOT EXISTS idx_executions_task_id ON executions(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_execution_events_execution_id ON execution_events(execution_id, id)",
)

MIGRATION_COLUMNS = {
    "executions": (
        ("process_id", "INTEGER"),
        ("exit_code", "INTEGER"),
    ),
    "execution_events": (
        ("sequence_number", "INTEGER"),
        ("source", "TEXT"),
    ),
}


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    _ensure_columns(connection)
    _backfill_execution_events(connection)
    connection.commit()


def _ensure_columns(connection: sqlite3.Connection) -> None:
    for table_name, columns in MIGRATION_COLUMNS.items():
        existing_columns = {
            row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, column_type in columns:
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )


def _backfill_execution_events(connection: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(execution_events)").fetchall()
    }
    if "sequence_number" in columns:
        connection.execute(
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
    if "source" in columns:
        connection.execute(
            """
            UPDATE execution_events
            SET source = 'json'
            WHERE source IS NULL
            """
        )

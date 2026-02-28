import sqlite3

from agent_fleet.persistence.schema import initialize_schema


def test_initialize_schema_creates_expected_tables() -> None:
    connection = sqlite3.connect(":memory:")

    initialize_schema(connection)

    table_names = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }

    assert {"tasks", "executions", "execution_events"} <= table_names

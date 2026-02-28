from __future__ import annotations

import os

from agent_fleet.agents.codex_runner import CodexRunner
from agent_fleet.persistence.repository import SQLiteRepository


def test_codex_runner_persists_json_and_raw_events(tmp_path) -> None:
    script_path = tmp_path / "fake-codex"
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' '{\"type\":\"Task.Started\",\"step\":1}'",
                "printf '%s\\n' 'plain stdout line'",
                "printf '%s\\n' 'stderr raw line' >&2",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    os.chmod(script_path, 0o755)

    repository = SQLiteRepository(tmp_path / "runner.db")
    repository.initialize()
    task = repository.enqueue_task(kind="codex", payload="{}")
    execution = repository.create_execution(task_id=task.id, agent_name="codex")
    runner = CodexRunner(repository, command=(str(script_path),))

    result = runner.run(execution_id=execution.id, prompt="ignored", working_dir=tmp_path)

    stored_execution = repository.get_execution(execution.id)
    events = repository.list_execution_events(execution.id)

    assert result.exit_code == 0
    assert result.summary == {"json_events": 1, "stdout_lines": 1, "stderr_lines": 1}
    assert stored_execution is not None
    assert stored_execution.exit_code == 0
    assert [event.sequence_number for event in events] == [1, 2, 3]
    assert any(event.source == "json" and event.event_type == "task_started" for event in events)
    assert any(
        event.source == "stdout" and event.event_type == "raw_text" and event.payload == "plain stdout line"
        for event in events
    )
    assert any(
        event.source == "stderr" and event.event_type == "raw_text" and event.payload == "stderr raw line"
        for event in events
    )


def test_codex_runner_adds_skip_git_repo_check_outside_git(tmp_path) -> None:
    codex_path = tmp_path / "codex"
    codex_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "printf '%s\\n' \"$*\"",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    os.chmod(codex_path, 0o755)

    repository = SQLiteRepository(tmp_path / "runner2.db")
    repository.initialize()
    task = repository.enqueue_task(kind="codex", payload="{}")
    execution = repository.create_execution(task_id=task.id, agent_name="codex")

    runner = CodexRunner(repository, command=(str(codex_path), "exec", "--json"))
    runner.run(execution_id=execution.id, prompt="do work", working_dir=tmp_path)

    events = repository.list_execution_events(execution.id)
    assert any("--skip-git-repo-check" in event.payload for event in events)

from __future__ import annotations

import os

import pytest

from agent_fleet.orchestrator.runtime import RuntimeStateError, acquire_pid_file, read_pid_file


def test_acquire_pid_file_rejects_active_process(tmp_path) -> None:
    pid_file = tmp_path / "orchestrator.pid"
    pid_file.write_text(f"{os.getpid()}\n", encoding="ascii")

    with pytest.raises(RuntimeStateError):
        acquire_pid_file(pid_file)


def test_acquire_pid_file_replaces_stale_pid_file(tmp_path) -> None:
    pid_file = tmp_path / "orchestrator.pid"
    pid_file.write_text("999999\n", encoding="ascii")

    acquire_pid_file(pid_file, pid=12345)

    assert read_pid_file(pid_file) == 12345

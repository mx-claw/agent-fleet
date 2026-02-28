from __future__ import annotations

import json
from pathlib import Path
import signal
import subprocess
import sys
import time

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agents.codex_runner import CodexRunner
from .config import AppConfig
from .orchestrator.runtime import (
    RuntimeStateError,
    acquire_pid_file,
    is_process_running,
    read_pid_file,
    release_pid_file,
    stop_process,
)
from .orchestrator.service import OrchestratorService
from .persistence.repository import SQLiteRepository
from .prompts.task_types import task_type_choices
from .queue.fifo import FIFOQueue


@click.group()
@click.option("--database", "database_path", default="agent_fleet.db", show_default=True)
@click.option("--runtime-dir", default="runtime", show_default=True)
@click.pass_context
def main(ctx: click.Context, database_path: str, runtime_dir: str) -> None:
    """Manage the agent-fleet queue and orchestrator lifecycle."""
    ctx.obj = {"config": AppConfig.from_paths(database_path=database_path, runtime_dir=runtime_dir)}


@main.command()
@click.option("--working-dir", required=True, type=click.Path(path_type=Path))
@click.option("--instruction", required=False, type=str)
@click.option("--github-issue-url", required=False, type=str)
@click.option("--github-issue-title", required=False, type=str)
@click.option("--github-issue-body", required=False, type=str)
@click.option("--github-issue-number", required=False, type=int)
@click.option(
    "--task-type",
    default="feature_implementation",
    type=click.Choice(task_type_choices(), case_sensitive=False),
    show_default=True,
)
@click.pass_context
def enqueue(
    ctx: click.Context,
    working_dir: Path,
    instruction: str | None,
    github_issue_url: str | None,
    github_issue_title: str | None,
    github_issue_body: str | None,
    github_issue_number: int | None,
    task_type: str,
) -> None:
    payload = _build_enqueue_payload(
        working_dir=working_dir,
        instruction=instruction,
        github_issue_url=github_issue_url,
        github_issue_title=github_issue_title,
        github_issue_body=github_issue_body,
        github_issue_number=github_issue_number,
        task_type=task_type,
    )

    repository = _repository(ctx)
    queue = FIFOQueue(repository)
    task = queue.enqueue(kind="codex", payload=json.dumps(payload))
    Console().print(f"queued task {task.id}")


@main.command()
@click.option("--poll-interval", default=1.0, show_default=True, type=float)
@click.option("--pid-file", default=None, type=click.Path(path_type=Path))
@click.pass_context
def run(ctx: click.Context, poll_interval: float, pid_file: Path | None) -> None:
    config = _config(ctx)
    repository = _repository(ctx)
    queue = FIFOQueue(repository)
    service = OrchestratorService(
        repository,
        queue,
        CodexRunner(repository),
        poll_interval_seconds=poll_interval,
    )

    pid_path = pid_file or config.pid_file_path
    pid_written = False
    if pid_file is not None:
        acquire_pid_file(pid_path)
        pid_written = True

    def _handle_signal(_signum: int, _frame: object) -> None:
        service.stop()

    previous_sigint = signal.signal(signal.SIGINT, _handle_signal)
    previous_sigterm = signal.signal(signal.SIGTERM, _handle_signal)
    try:
        service.run()
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        if pid_written:
            release_pid_file(pid_path)


@main.command()
@click.option("--poll-interval", default=1.0, show_default=True, type=float)
@click.pass_context
def start(ctx: click.Context, poll_interval: float) -> None:
    config = _config(ctx)
    console = Console()
    try:
        existing_pid = read_pid_file(config.pid_file_path)
        if existing_pid is not None and is_process_running(existing_pid):
            raise RuntimeStateError(f"Process already running with pid {existing_pid}")
        if existing_pid is not None:
            release_pid_file(config.pid_file_path)

        config.runtime_dir.mkdir(parents=True, exist_ok=True)
        log_handle = config.log_file_path.open("a", encoding="utf-8")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "agent_fleet",
                "--database",
                str(config.database_path),
                "--runtime-dir",
                str(config.runtime_dir),
                "run",
                "--poll-interval",
                str(poll_interval),
                "--pid-file",
                str(config.pid_file_path),
            ],
            cwd=Path.cwd(),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        log_handle.close()
        _wait_for_pid_file(config.pid_file_path, expected_pid=process.pid)
    except RuntimeStateError as error:
        raise click.ClickException(str(error)) from error

    console.print(f"started orchestrator pid {process.pid}")
    console.print(f"log file: {config.log_file_path}")


@main.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    config = _config(ctx)
    pid = read_pid_file(config.pid_file_path)
    if pid is None:
        raise click.ClickException("orchestrator is not running")

    if not is_process_running(pid):
        release_pid_file(config.pid_file_path)
        raise click.ClickException("orchestrator pid file was stale and has been removed")

    stop_process(pid)
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if not is_process_running(pid):
            release_pid_file(config.pid_file_path)
            Console().print(f"stopped orchestrator pid {pid}")
            return
        time.sleep(0.1)
    raise click.ClickException(f"timed out waiting for pid {pid} to stop")


@main.command()
@click.option("--limit", default=10, show_default=True, type=int)
@click.pass_context
def status(ctx: click.Context, limit: int) -> None:
    config = _config(ctx)
    repository = _repository(ctx)
    console = Console()
    pid = read_pid_file(config.pid_file_path)

    lifecycle = Table(title="orchestrator")
    lifecycle.add_column("Field")
    lifecycle.add_column("Value")
    lifecycle.add_row("Database", str(config.database_path))
    lifecycle.add_row("Runtime Dir", str(config.runtime_dir))
    lifecycle.add_row("PID File", str(config.pid_file_path))
    lifecycle.add_row("Log File", str(config.log_file_path))
    lifecycle.add_row("Running", "yes" if pid is not None and is_process_running(pid) else "no")
    lifecycle.add_row("PID", str(pid) if pid is not None else "-")
    console.print(lifecycle)

    tasks = repository.list_tasks(limit=limit)
    task_table = Table(title="recent tasks")
    task_table.add_column("Task")
    task_table.add_column("Status")
    task_table.add_column("Queued")
    task_table.add_column("Kind")
    for task in tasks:
        task_table.add_row(task.id, task.status.value, task.queued_at, task.kind)
    console.print(task_table)


@main.command()
@click.option("--task-id", required=True)
@click.option("--tail", default=50, show_default=True, type=int)
@click.pass_context
def events(ctx: click.Context, task_id: str, tail: int) -> None:
    repository = _repository(ctx)
    console = Console()

    history_data = repository.get_task_history(task_id)
    if history_data is None:
        raise click.ClickException(f"task {task_id} not found")

    task = history_data["task"]
    assert not isinstance(task, dict)
    console.print(Panel.fit(f"{task.id}\nstatus={task.status.value}\nkind={task.kind}", title="task"))

    all_rows: list[tuple[str, int, str, str, str]] = []
    for item in history_data["executions"]:
        execution = item["execution"]
        for event in item["events"]:
            all_rows.append((execution.id, event.sequence_number, event.source, event.event_type, event.payload))

    if tail > 0:
        all_rows = all_rows[-tail:]

    event_table = Table(title="events")
    event_table.add_column("Execution")
    event_table.add_column("Seq")
    event_table.add_column("Source")
    event_table.add_column("Type")
    event_table.add_column("Payload")

    for execution_id, seq, source, event_type, payload in all_rows:
        event_table.add_row(execution_id, str(seq), source, event_type, payload)

    console.print(event_table)


@main.command(hidden=True)
@click.argument("task_id")
@click.option("--tail", default=50, show_default=True, type=int)
@click.pass_context
def history(ctx: click.Context, task_id: str, tail: int) -> None:
    """Deprecated alias for `events --task-id`"""
    ctx.invoke(events, task_id=task_id, tail=tail)


def _build_enqueue_payload(
    *,
    working_dir: Path,
    instruction: str | None,
    github_issue_url: str | None,
    github_issue_title: str | None,
    github_issue_body: str | None,
    github_issue_number: int | None,
    task_type: str,
) -> dict[str, object]:
    plain_instruction = (instruction or "").strip()
    issue_url = (github_issue_url or "").strip()
    issue_title = (github_issue_title or "").strip()
    issue_body = (github_issue_body or "").strip()
    issue_mode = any([issue_url, issue_title, issue_body, github_issue_number is not None])

    if plain_instruction and issue_mode:
        raise click.ClickException(
            "Provide either a plain --instruction OR github issue fields, not both."
        )

    if not plain_instruction and not issue_mode:
        raise click.ClickException(
            "Provide either --instruction OR github issue fields (--github-issue-url/--github-issue-title/--github-issue-body)."
        )

    if issue_mode:
        if not issue_url:
            raise click.ClickException("--github-issue-url is required for github issue mode")
        if not issue_title and not issue_body:
            raise click.ClickException(
                "Provide at least one of --github-issue-title or --github-issue-body in github issue mode"
            )
        return {
            "working_dir": str(working_dir),
            "task_type": task_type.lower(),
            "input_mode": "github_issue",
            "instruction": "",
            "github_issue": {
                "url": issue_url,
                "title": issue_title,
                "body": issue_body,
                "number": github_issue_number,
            },
        }

    return {
        "working_dir": str(working_dir),
        "task_type": task_type.lower(),
        "input_mode": "plain_task",
        "instruction": plain_instruction,
        "github_issue": None,
    }


def _config(ctx: click.Context) -> AppConfig:
    return ctx.obj["config"]


def _repository(ctx: click.Context) -> SQLiteRepository:
    config = _config(ctx)
    repository = SQLiteRepository(config.database_path)
    repository.initialize()
    return repository


def _wait_for_pid_file(pid_file: Path, *, expected_pid: int, timeout_seconds: float = 5.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        pid = read_pid_file(pid_file)
        if pid == expected_pid:
            return
        time.sleep(0.05)
    raise RuntimeStateError(f"Timed out waiting for pid file {pid_file}")


if __name__ == "__main__":
    main()

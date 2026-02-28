from __future__ import annotations

from dataclasses import dataclass
import json
from queue import Queue
import subprocess
import threading
from pathlib import Path
from typing import IO, Sequence

from agent_fleet.persistence.repository import SQLiteRepository


@dataclass(frozen=True, slots=True)
class CodexRunResult:
    exit_code: int
    summary: dict[str, int]


class CodexRunner:
    """Adapter that runs Codex and persists streamed execution events."""

    def __init__(
        self,
        repository: SQLiteRepository,
        *,
        command: Sequence[str] = ("codex", "exec", "--json"),
    ) -> None:
        self.repository = repository
        self.command = tuple(command)

    def run(
        self,
        *,
        execution_id: str,
        prompt: str,
        working_dir: str | Path,
    ) -> CodexRunResult:
        working_dir_path = Path(working_dir)
        command = [*self.command]

        # Allow execution outside git when needed; policy prompt still enforces
        # commit/push/PR behavior when inside git repositories.
        if not _is_git_repo(working_dir_path) and _looks_like_codex_command(command):
            command.append("--skip-git-repo-check")

        command.append(prompt)

        process = subprocess.Popen(
            command,
            cwd=working_dir_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self.repository.mark_execution_running(execution_id=execution_id, process_id=process.pid)

        output_queue: Queue[tuple[str, str] | None] = Queue()
        readers = [
            threading.Thread(
                target=_enqueue_lines,
                args=(process.stdout, "stdout", output_queue),
                daemon=True,
            ),
            threading.Thread(
                target=_enqueue_lines,
                args=(process.stderr, "stderr", output_queue),
                daemon=True,
            ),
        ]
        for reader in readers:
            reader.start()

        sequence_number = 0
        summary = {"json_events": 0, "stdout_lines": 0, "stderr_lines": 0}
        completed_readers = 0
        while completed_readers < len(readers):
            item = output_queue.get()
            if item is None:
                completed_readers += 1
                continue

            source, line = item
            sequence_number += 1
            event_source, event_type, payload = self._parse_event_line(source=source, line=line)
            if event_source == "json":
                summary["json_events"] += 1
            elif event_source == "stderr":
                summary["stderr_lines"] += 1
            else:
                summary["stdout_lines"] += 1

            self.repository.append_execution_event(
                execution_id=execution_id,
                sequence_number=sequence_number,
                source=event_source,
                event_type=event_type,
                payload=payload,
            )

        exit_code = process.wait()
        if exit_code == 0:
            self.repository.mark_execution_succeeded(execution_id=execution_id, exit_code=exit_code)
        else:
            self.repository.mark_execution_failed(execution_id=execution_id, exit_code=exit_code)
        return CodexRunResult(exit_code=exit_code, summary=summary)

    @staticmethod
    def _parse_event_line(*, source: str, line: str) -> tuple[str, str, str]:
        stripped = line.rstrip("\n")
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return source, "raw_text", stripped

        if isinstance(payload, dict):
            event_type = payload.get("type") or payload.get("event_type") or "json_event"
        else:
            event_type = "json_event"
        return "json", _normalize_event_type(str(event_type)), json.dumps(payload, sort_keys=True)


def _enqueue_lines(
    stream: IO[str] | None,
    source: str,
    output_queue: Queue[tuple[str, str] | None],
) -> None:
    if stream is None:
        output_queue.put(None)
        return

    try:
        for line in iter(stream.readline, ""):
            output_queue.put((source, line))
    finally:
        stream.close()
        output_queue.put(None)


def _normalize_event_type(value: str) -> str:
    normalized = []
    for character in value.lower():
        if character.isalnum():
            normalized.append(character)
        else:
            normalized.append("_")
    return "".join(normalized).strip("_") or "json_event"


def _is_git_repo(path: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _looks_like_codex_command(command: Sequence[str]) -> bool:
    if not command:
        return False
    binary = Path(command[0]).name
    return binary == "codex"

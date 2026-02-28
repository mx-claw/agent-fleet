from __future__ import annotations

import json
from pathlib import Path
import threading

from agent_fleet.agents.codex_runner import CodexRunner
from agent_fleet.persistence.repository import SQLiteRepository
from agent_fleet.prompts.policy import build_prompt
from agent_fleet.queue.fifo import FIFOQueue


class OrchestratorService:
    def __init__(
        self,
        repository: SQLiteRepository,
        queue: FIFOQueue,
        codex_runner: CodexRunner,
        *,
        poll_interval_seconds: float = 1.0,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.repository = repository
        self.queue = queue
        self.codex_runner = codex_runner
        self.poll_interval_seconds = poll_interval_seconds
        self.stop_event = stop_event or threading.Event()

    def run(self) -> None:
        while not self.stop_event.is_set():
            task = self.queue.dequeue()
            if task is None:
                self.stop_event.wait(self.poll_interval_seconds)
                continue
            self._run_task(task.id, task.kind, task.payload)

    def stop(self) -> None:
        self.stop_event.set()

    def _run_task(self, task_id: str, task_kind: str, task_payload: str) -> None:
        execution = self.repository.create_execution(task_id=task_id, agent_name=task_kind)
        try:
            payload = json.loads(task_payload)
            working_dir = Path(payload["working_dir"])
            instruction = str(payload.get("instruction", ""))
            task_type = str(payload.get("task_type", "feature_implementation"))
            input_mode = str(payload.get("input_mode", "plain_task"))
            github_issue = payload.get("github_issue")
            if not working_dir.exists() or not working_dir.is_dir():
                raise ValueError(f"working_dir does not exist: {working_dir}")

            prompt = build_prompt(
                task_type=task_type,
                working_dir=working_dir,
                instruction=instruction,
                input_mode=input_mode,
                github_issue=github_issue if isinstance(github_issue, dict) else None,
            )
            result = self.codex_runner.run(
                execution_id=execution.id,
                prompt=prompt,
                working_dir=working_dir,
            )
        except Exception as error:  # noqa: BLE001
            self.repository.append_execution_event(
                execution_id=execution.id,
                sequence_number=1,
                source="system",
                event_type="orchestrator_error",
                payload=str(error),
            )
            self.repository.mark_execution_failed(execution_id=execution.id, exit_code=None)
            self.repository.mark_task_failed(task_id)
            return

        if result.exit_code == 0:
            self.repository.mark_task_succeeded(task_id)
        else:
            self.repository.mark_task_failed(task_id)

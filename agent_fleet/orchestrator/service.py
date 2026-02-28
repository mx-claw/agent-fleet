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
            instruction = payload["instruction"]
            prompt = build_prompt(instruction, working_dir=working_dir)
            result = self.codex_runner.run(
                execution_id=execution.id,
                prompt=prompt,
                working_dir=working_dir,
            )
        except Exception as error:
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

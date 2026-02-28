from __future__ import annotations

from agent_fleet.domain.models import Task
from agent_fleet.persistence.repository import SQLiteRepository


class FIFOQueue:
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository

    def enqueue(self, *, kind: str, payload: str) -> Task:
        return self.repository.enqueue_task(kind=kind, payload=payload)

    def dequeue(self) -> Task | None:
        return self.repository.dequeue_next_task()

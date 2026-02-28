from agent_fleet.domain.models import TaskStatus
from agent_fleet.persistence.repository import SQLiteRepository
from agent_fleet.queue.fifo import FIFOQueue


def test_fifo_queue_dequeues_in_enqueue_order(tmp_path) -> None:
    repository = SQLiteRepository(tmp_path / "queue.db")
    repository.initialize()
    queue = FIFOQueue(repository)

    first = queue.enqueue(kind="codex", payload="first task")
    second = queue.enqueue(kind="codex", payload="second task")

    first_dequeued = queue.dequeue()
    second_dequeued = queue.dequeue()

    assert first_dequeued is not None
    assert second_dequeued is not None
    assert first_dequeued.id == first.id
    assert second_dequeued.id == second.id
    assert first_dequeued.status is TaskStatus.RUNNING
    assert second_dequeued.status is TaskStatus.RUNNING
    assert queue.dequeue() is None

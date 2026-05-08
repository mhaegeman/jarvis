"""Tests for the in-memory tasks queue."""

from __future__ import annotations

from server.tasks import TasksQueue


def test_empty_snapshot_is_zeroes() -> None:
    q = TasksQueue()
    assert q.snapshot() == {"queued": 0, "active": 0, "done": 0}


def test_enqueue_returns_unique_ids() -> None:
    q = TasksQueue()
    a = q.enqueue("ingest:foo")
    b = q.enqueue("ingest:bar")
    assert a != b


def test_enqueue_increments_queued() -> None:
    q = TasksQueue()
    q.enqueue("a")
    q.enqueue("b")
    snap = q.snapshot()
    assert snap["queued"] == 2
    assert snap["active"] == 0
    assert snap["done"] == 0


def test_start_moves_queued_to_active() -> None:
    q = TasksQueue()
    a = q.enqueue("a")
    q.enqueue("b")
    q.start(a)
    snap = q.snapshot()
    assert snap["queued"] == 1
    assert snap["active"] == 1
    assert snap["done"] == 0


def test_finish_moves_active_to_done() -> None:
    q = TasksQueue()
    a = q.enqueue("a")
    q.start(a)
    q.finish(a)
    snap = q.snapshot()
    assert snap == {"queued": 0, "active": 0, "done": 1}


def test_finish_unknown_id_is_idempotent() -> None:
    q = TasksQueue()
    q.finish("nope")
    assert q.snapshot() == {"queued": 0, "active": 0, "done": 0}


def test_start_unknown_id_is_idempotent() -> None:
    q = TasksQueue()
    q.start("nope")
    assert q.snapshot() == {"queued": 0, "active": 0, "done": 0}


def test_finish_a_queued_task_skips_active() -> None:
    """Cancelled-style finish: queued → done directly without running."""
    q = TasksQueue()
    a = q.enqueue("a")
    q.finish(a)
    assert q.snapshot() == {"queued": 0, "active": 0, "done": 1}


def test_module_singleton_exists() -> None:
    from server.tasks import tasks_queue

    assert isinstance(tasks_queue, TasksQueue)

"""In-memory task queue for the Tasks panel.

Tracks counts of queued/active/done jobs. Hooks reserved for the
second-brain ingestor and scheduled-prompt runner — those modules don't
exist yet; tests use the queue directly.

Done counter is monotonic in v2 (no eviction).
"""

from __future__ import annotations

import secrets


class TasksQueue:
    def __init__(self) -> None:
        self._queued: dict[str, str] = {}
        self._active: dict[str, str] = {}
        self._done = 0

    def enqueue(self, name: str) -> str:
        task_id = secrets.token_hex(4)
        self._queued[task_id] = name
        return task_id

    def start(self, task_id: str) -> None:
        name = self._queued.pop(task_id, None)
        if name is None:
            return
        self._active[task_id] = name

    def finish(self, task_id: str) -> None:
        if self._active.pop(task_id, None) is not None:
            self._done += 1
            return
        if self._queued.pop(task_id, None) is not None:
            self._done += 1

    def snapshot(self) -> dict[str, int]:
        return {
            "queued": len(self._queued),
            "active": len(self._active),
            "done": self._done,
        }


tasks_queue = TasksQueue()

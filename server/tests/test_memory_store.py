"""MemoryStore tests run entirely against :memory: SQLite."""

from __future__ import annotations

import pytest

from server.memory.store import MemoryStore


@pytest.fixture
async def store() -> MemoryStore:
    s = await MemoryStore.open(":memory:")
    yield s
    await s.close()


async def test_open_creates_all_tables(store: MemoryStore) -> None:
    cur = await store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    names = {row[0] for row in await cur.fetchall()}
    assert {"sessions", "turns", "session_summaries", "facts", "recent_summary"} <= names


async def test_open_is_idempotent(tmp_path) -> None:
    path = str(tmp_path / "m.db")
    s1 = await MemoryStore.open(path)
    await s1.close()
    s2 = await MemoryStore.open(path)
    await s2.close()  # no exception

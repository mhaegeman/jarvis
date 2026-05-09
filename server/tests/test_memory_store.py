"""MemoryStore tests run entirely against :memory: SQLite."""

from __future__ import annotations

import asyncio

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


async def test_start_and_end_session(store: MemoryStore) -> None:
    sid = await store.start_session()
    assert isinstance(sid, str) and sid
    cur = await store._conn.execute("SELECT ended_at FROM sessions WHERE session_id=?", (sid,))
    row = await cur.fetchone()
    assert row is not None and row[0] is None
    await store.end_session(sid)
    cur = await store._conn.execute("SELECT ended_at FROM sessions WHERE session_id=?", (sid,))
    row = await cur.fetchone()
    assert row is not None and row[0] is not None


async def test_start_session_assigns_sequential_counter_ids(store: MemoryStore) -> None:
    ids = [await store.start_session() for _ in range(3)]
    assert ids == ["1", "2", "3"]


async def test_start_session_ignores_legacy_hex_ids(store: MemoryStore) -> None:
    # Pre-populate with a hex session_id to simulate an upgraded DB.
    await store._conn.execute(
        "INSERT INTO sessions(session_id, started_at, ended_at) VALUES (?, '2026-01-01T00:00:00Z', NULL)",
        ("a3b4c5d6e7f80123",),
    )
    await store._conn.commit()
    assert await store.start_session() == "1"
    assert await store.start_session() == "2"


async def test_start_session_is_safe_under_concurrent_callers(store: MemoryStore) -> None:
    """A shared MemoryStore is reused across websocket sessions, so concurrent
    start_session() calls must not collide on the session_id PK."""
    ids = await asyncio.gather(*(store.start_session() for _ in range(20)))
    assert sorted(ids, key=int) == [str(i) for i in range(1, 21)]
    assert len(set(ids)) == len(ids)


async def test_append_and_load_turns(store: MemoryStore) -> None:
    sid = await store.start_session()
    tid1 = await store.append_turn(sid, "user", "hello")
    tid2 = await store.append_turn(sid, "assistant", "hi back")
    assert tid2 > tid1
    turns = await store.load_session_turns(sid, cap=10)
    assert [t.role for t in turns] == ["user", "assistant"]
    assert [t.content for t in turns] == ["hello", "hi back"]


async def test_load_session_turns_caps_to_latest(store: MemoryStore) -> None:
    sid = await store.start_session()
    for i in range(5):
        await store.append_turn(sid, "user", f"u{i}")
        await store.append_turn(sid, "assistant", f"a{i}")
    turns = await store.load_session_turns(sid, cap=3)
    assert len(turns) == 3
    # Last 3 rows from a 10-turn series in chronological order: a3, u4, a4.
    assert [t.content for t in turns] == ["a3", "u4", "a4"]


async def test_find_resumable_uses_last_turn_ts(store: MemoryStore) -> None:
    sid = await store.start_session()
    await store.append_turn(sid, "user", "u1")
    found = await store.find_resumable(within_minutes=30)
    assert found == sid


async def test_find_resumable_returns_none_when_no_recent(store: MemoryStore) -> None:
    # No sessions at all.
    assert await store.find_resumable(within_minutes=30) is None


async def test_find_resumable_skips_stale(store: MemoryStore) -> None:
    sid = await store.start_session()
    # Backdate the only turn to be outside the window.
    await store._conn.execute(
        "INSERT INTO turns(session_id, ts, role, content) VALUES (?, ?, ?, ?)",
        (sid, "2000-01-01T00:00:00Z", "user", "ancient"),
    )
    await store._conn.commit()
    assert await store.find_resumable(within_minutes=30) is None


async def test_recent_summary_empty_initially(store: MemoryStore) -> None:
    assert await store.get_recent_summary() == ""


async def test_write_and_read_recent_summary(store: MemoryStore) -> None:
    await store.write_recent_summary("recently we shipped α", last_turn_id=10)
    assert await store.get_recent_summary() == "recently we shipped α"
    meta = await store.get_recent_summary_meta()
    assert meta.summary == "recently we shipped α"
    assert meta.last_turn_id == 10


async def test_write_recent_summary_overwrites(store: MemoryStore) -> None:
    await store.write_recent_summary("first", last_turn_id=1)
    await store.write_recent_summary("second", last_turn_id=2)
    meta = await store.get_recent_summary_meta()
    assert meta.summary == "second"
    assert meta.last_turn_id == 2


async def test_turns_since_counts_correctly(store: MemoryStore) -> None:
    sid = await store.start_session()
    t1 = await store.append_turn(sid, "user", "u1")
    await store.append_turn(sid, "assistant", "a1")
    await store.append_turn(sid, "user", "u2")
    assert await store.turns_since(t1) == 2


async def test_get_facts_empty(store: MemoryStore) -> None:
    assert await store.get_facts() == {}


async def test_upsert_and_get_facts(store: MemoryStore) -> None:
    sid = await store.start_session()
    from server.memory.types import Fact

    await store.upsert_facts([Fact("lang", "TS"), Fact("city", "Brussels")], sid)
    assert await store.get_facts() == {"lang": "TS", "city": "Brussels"}


async def test_upsert_overwrites_existing_key(store: MemoryStore) -> None:
    sid = await store.start_session()
    from server.memory.types import Fact

    await store.upsert_facts([Fact("lang", "Python")], sid)
    await store.upsert_facts([Fact("lang", "TypeScript")], sid)
    assert (await store.get_facts())["lang"] == "TypeScript"


async def test_evict_facts_to_cap_keeps_most_recent(store: MemoryStore) -> None:
    sid = await store.start_session()
    from server.memory.types import Fact

    # Insert keys 0..9 with manually controlled updated_at so LRU is deterministic.
    for i in range(10):
        await store.upsert_facts([Fact(f"k{i}", f"v{i}")], sid)
        # Ensure distinct timestamps even on fast clocks.
        await store._conn.execute(
            "UPDATE facts SET updated_at=? WHERE key=?",
            (f"2026-05-08T10:00:{i:02d}Z", f"k{i}"),
        )
        await store._conn.commit()
    await store.evict_facts_to_cap(3)
    facts = await store.get_facts()
    assert set(facts.keys()) == {"k7", "k8", "k9"}


async def test_write_and_list_session_summaries(store: MemoryStore) -> None:
    sid1 = await store.start_session()
    sid2 = await store.start_session()
    await store.write_session_summary(sid1, "discussed deploys")
    await store.write_session_summary(sid2, "reviewed schema")
    summaries = await store.list_recent_summaries(limit=5)
    assert [s.summary for s in summaries] == ["reviewed schema", "discussed deploys"]


async def test_list_recent_summaries_respects_limit(store: MemoryStore) -> None:
    for i in range(5):
        sid = await store.start_session()
        await store.write_session_summary(sid, f"s{i}")
    summaries = await store.list_recent_summaries(limit=2)
    assert len(summaries) == 2
    assert summaries[0].summary == "s4"


async def test_search_turns_like_match(store: MemoryStore) -> None:
    sid = await store.start_session()
    await store.append_turn(sid, "user", "I prefer to deploy on Fridays")
    await store.append_turn(sid, "assistant", "noted: Fridays")
    await store.append_turn(sid, "user", "what's the weather")
    matches = await store.search_turns("deploy", limit=5)
    assert any("deploy" in t.content.lower() for t in matches)
    assert all(isinstance(t.id, int) for t in matches)


async def test_search_turns_returns_empty_for_no_match(store: MemoryStore) -> None:
    sid = await store.start_session()
    await store.append_turn(sid, "user", "hello")
    assert await store.search_turns("nonexistent_phrase", limit=5) == []

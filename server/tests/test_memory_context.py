"""MemoryContext blob assembly."""

from __future__ import annotations

import pytest

from server.memory.context import MemoryContext
from server.memory.store import MemoryStore
from server.memory.types import Fact


@pytest.fixture
async def store() -> MemoryStore:
    s = await MemoryStore.open(":memory:")
    yield s
    await s.close()


async def test_default_returns_empty_when_no_summary(store: MemoryStore) -> None:
    assert await MemoryContext.default(store) == ""


async def test_default_returns_formatted_when_summary_present(store: MemoryStore) -> None:
    await store.write_recent_summary("we shipped α", last_turn_id=1)
    blob = await MemoryContext.default(store)
    assert "Background (recent conversation summary):" in blob
    assert "we shipped α" in blob


async def test_full_includes_all_sections_when_populated(store: MemoryStore) -> None:
    sid = await store.start_session()
    await store.append_turn(sid, "user", "I prefer to deploy on Fridays")
    await store.append_turn(sid, "assistant", "noted")
    await store.write_recent_summary("we set a Friday deploy rule", last_turn_id=2)
    await store.write_session_summary(sid, "agreed Fridays for deploys")
    await store.upsert_facts([Fact("deploy_day", "Friday")], sid)
    blob = await MemoryContext.full(store, "did we discuss deploys")
    assert "Background" in blob
    assert "What I know about you" in blob
    assert "deploy_day: Friday" in blob
    assert "Recent sessions" in blob
    assert "agreed Fridays for deploys" in blob
    assert "Possibly relevant past exchanges" in blob


async def test_full_omits_empty_sections(store: MemoryStore) -> None:
    blob = await MemoryContext.full(store, "what did we discuss")
    assert "What I know about you" not in blob
    assert "Recent sessions" not in blob
    assert "Possibly relevant past exchanges" not in blob


async def test_full_caps_facts_sessions_and_search(store: MemoryStore) -> None:
    sid = await store.start_session()
    # 60 facts → must be capped to 50.
    await store.upsert_facts([Fact(f"k{i}", f"v{i}") for i in range(60)], sid)
    blob = await MemoryContext.full(store, "what's my k0")
    # Facts section: each fact is one line "- key: value". Count fact lines.
    fact_lines = [ln for ln in blob.splitlines() if ln.startswith("- k")]
    assert len(fact_lines) <= 50

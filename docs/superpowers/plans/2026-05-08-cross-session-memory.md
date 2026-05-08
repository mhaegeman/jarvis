# Cross-Session Memory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in cross-session memory to JARVIS — same-day resume + on-demand long-term recall — without changing default per-turn token cost beyond a small "recent conversation summary" blob.

**Architecture:** A new `server/server/memory/` package with four pieces (`MemoryStore`, `Summarizer`, `triggers`, `MemoryContext`) backed by a single SQLite file. `Session` gains an optional `MemoryStore` dependency and routes each turn through `MemoryContext` (default vs full blob, decided by phrase-match on `user_text`) which is forwarded to the LLM via a new `extra_context` kwarg on the `LLM.stream` ABC. Consolidation (session summary + fact extraction) runs synchronously in `Session.cleanup`.

**Tech Stack:** Python 3.12, FastAPI, `aiosqlite`, `anthropic` SDK (Haiku for summarization), pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-05-08-cross-session-memory-design.md`

---

## File Structure

**Create:**

| Path | Responsibility |
|---|---|
| `server/server/memory/__init__.py` | Package marker; re-exports `MemoryStore`, `MemoryContext`, types |
| `server/server/memory/types.py` | Frozen dataclasses: `Turn`, `Fact`, `SessionSummary`, `RecentSummaryMeta` |
| `server/server/memory/triggers.py` | Pure `is_memory_query(text) -> bool` + `_TRIGGER_PHRASES` constant |
| `server/server/memory/store.py` | `MemoryStore` — async SQLite wrapper, all persistence |
| `server/server/memory/summarizer.py` | `Summarizer` Protocol + `ClaudeSummarizer` impl (Haiku); `Fact` parsing |
| `server/server/memory/context.py` | `MemoryContext.default` / `.full` blob builders |
| `server/tests/test_memory_types.py` | Dataclass construction sanity |
| `server/tests/test_memory_triggers.py` | Phrase matrix incl. false-positive landmines |
| `server/tests/test_memory_store.py` | Schema, all CRUD, LRU eviction, resume-window math |
| `server/tests/test_memory_summarizer.py` | Mocked Anthropic; model id + JSON parse tolerance |
| `server/tests/test_memory_context.py` | Default/full blob shapes |
| `server/tests/test_memory_session.py` | E2E: Session ⊕ `:memory:` store ⊕ FakeSummarizer ⊕ MockLLM |

**Modify:**

| Path | Change |
|---|---|
| `server/pyproject.toml` | Add `aiosqlite>=0.20` to `dependencies` |
| `.gitignore` | Add `server/data/` |
| `server/server/pipelines/interfaces.py:21-31` | `LLM.stream` gains `*, extra_context: str = ""` |
| `server/server/pipelines/claude_llm.py:103-122` | `stream` accepts `extra_context`; concatenated to `system=` |
| `server/server/pipelines/mock_llm.py:18-22` | `stream` accepts and ignores `extra_context` |
| `server/server/session.py` | `__init__` accepts `memory: MemoryStore \| None`; `run`, `_do_llm_and_tts`, `cleanup` integrate memory |
| `server/server/main.py:25-99` | Open `MemoryStore` at lifespan startup, pass to `Session`, close at shutdown; honor `JARVIS_MEMORY` and `JARVIS_MEMORY_DB` env vars |
| `server/server/config.py` | Add memory settings (paths, caps, window) |

---

## Conventions for every task

- TDD strict: failing test first, run it (must fail), implement minimum, run again (must pass), commit.
- One commit per task. Commit message: `feat(memory): <task summary>` for code tasks, `chore(memory): ...` for bootstrap.
- All paths in this plan are relative to the worktree root: `/home/user/jarvis/.worktrees/feat-cross-session-memory/`.
- `cd server` before running pytest — the package's `pyproject.toml` defines `testpaths = ["tests"]` from there.
- Use `uv run pytest` (the project uses `uv`) — never bare `pytest`.

---

## Task 0: Bootstrap dependencies and gitignore

**Files:**
- Modify: `server/pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Confirm baseline tests pass**

```bash
cd server && uv sync --extra dev && uv run pytest -q
```

Expected: all existing tests pass (one timing-flaky test in `test_state_snapshot.py` may fail in a single run; pass on rerun is acceptable). If structural failures appear, stop and investigate before adding new deps.

- [ ] **Step 2: Add `aiosqlite` to dependencies**

In `server/pyproject.toml`, inside the `dependencies = [...]` list, after the `"anthropic>=0.40,<1.0",` line, add:

```toml
  "aiosqlite>=0.20",
```

- [ ] **Step 3: Add `server/data/` to .gitignore**

In `.gitignore`, after the existing `.worktrees/` line, append:

```
server/data/
```

- [ ] **Step 4: Sync and re-run tests**

```bash
cd server && uv sync --extra dev && uv run pytest -q
```

Expected: `aiosqlite` installed, all existing tests still pass (timing-flake on `test_run_emits_periodic_snapshots` allowed if the rerun passes).

- [ ] **Step 5: Commit**

```bash
git add server/pyproject.toml server/uv.lock .gitignore
git commit -m "chore(memory): add aiosqlite dep, gitignore server/data/"
```

---

## Task 1: Memory package skeleton + types

**Files:**
- Create: `server/server/memory/__init__.py`
- Create: `server/server/memory/types.py`
- Create: `server/tests/test_memory_types.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_memory_types.py`:

```python
"""Sanity checks on the memory dataclasses."""

from server.memory.types import Fact, RecentSummaryMeta, SessionSummary, Turn


def test_turn_is_frozen() -> None:
    t = Turn(id=1, session_id="s1", ts="2026-05-08T10:00:00Z", role="user", content="hi")
    assert t.role == "user"
    try:
        t.content = "nope"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Turn should be frozen")


def test_fact_construction() -> None:
    f = Fact(key="lang", value="TypeScript")
    assert (f.key, f.value) == ("lang", "TypeScript")


def test_session_summary_optional_ended_at() -> None:
    s = SessionSummary(
        session_id="s1",
        started_at="2026-05-08T10:00:00Z",
        ended_at=None,
        summary="Discussed deploys.",
    )
    assert s.ended_at is None


def test_recent_summary_meta() -> None:
    m = RecentSummaryMeta(summary="hi", refreshed_at="2026-05-08T10:00:00Z", last_turn_id=42)
    assert m.last_turn_id == 42
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd server && uv run pytest tests/test_memory_types.py -v
```

Expected: ModuleNotFoundError for `server.memory.types`.

- [ ] **Step 3: Create the package**

Create `server/server/memory/__init__.py`:

```python
"""Cross-session memory package.

Exports MemoryStore (persistence), MemoryContext (per-turn blob builder),
and the dataclasses used at the boundaries.
"""

from .types import Fact, RecentSummaryMeta, SessionSummary, Turn

__all__ = ["Fact", "RecentSummaryMeta", "SessionSummary", "Turn"]
```

Create `server/server/memory/types.py`:

```python
"""Frozen dataclasses used at the memory-package boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Turn:
    id: int
    session_id: str
    ts: str
    role: str
    content: str


@dataclass(frozen=True)
class Fact:
    key: str
    value: str


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    started_at: str
    ended_at: str | None
    summary: str


@dataclass(frozen=True)
class RecentSummaryMeta:
    summary: str
    refreshed_at: str
    last_turn_id: int
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd server && uv run pytest tests/test_memory_types.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add server/server/memory/__init__.py server/server/memory/types.py server/tests/test_memory_types.py
git commit -m "feat(memory): add package skeleton with boundary dataclasses"
```

---

## Task 2: Triggers (`is_memory_query`)

**Files:**
- Create: `server/server/memory/triggers.py`
- Create: `server/tests/test_memory_triggers.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_memory_triggers.py`:

```python
"""Phrase matrix for is_memory_query.

True positives must match. False positives marked 'accepted' may match
(documented trade-off). False positives marked 'must NOT match' are
regression locks against naively expanding _TRIGGER_PHRASES.
"""

import pytest

from server.memory.triggers import is_memory_query


@pytest.mark.parametrize(
    "text",
    [
        "Do you remember when we discussed the deploy?",
        "did i mention the friday rule?",
        "Did I tell you about Wednesday's meeting?",
        "You said TypeScript was preferred.",
        "you mentioned a rollback last week",
        "you told me to prefer Vite",
        "we discussed this on Tuesday",
        "we covered the API design earlier",
        "we talked about deployments",
        "did we discuss the gate timeline?",
        "Earlier you said something about caching.",
        "last time we talked about this",
        "last time you suggested a redo",
        "What do you know about my project?",
        "what's my preferred language?",
        "whats my timezone again",
        "what are my open tasks",
        "what did i say about Friday?",
        "what did we decide on the schema?",
        "Recall the last release notes.",
        "remember when we shipped α?",
    ],
)
def test_true_positives(text: str) -> None:
    assert is_memory_query(text), f"should trigger: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "I'll remember to call mom",
        "I recalled it later",
        "Remember me to your mother",
        "I want to remember this",
        "Remind me later",
        "Tell me a joke",
        "What's the weather?",
    ],
)
def test_must_not_match(text: str) -> None:
    assert not is_memory_query(text), f"should NOT trigger: {text!r}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd server && uv run pytest tests/test_memory_triggers.py -v
```

Expected: ModuleNotFoundError for `server.memory.triggers`.

- [ ] **Step 3: Implement `triggers.py`**

Create `server/server/memory/triggers.py`:

```python
"""Phrase-level detection of 'user is asking JARVIS to consult memory'.

Phrase-level (not single-word) by design — bare 'remember' would catch
'I'll remember to call mom'. Trailing-space patterns ('recall ') keep
'recalled' from matching. Tweak the constant; tests in
test_memory_triggers.py lock the behaviour.
"""

from __future__ import annotations

_TRIGGER_PHRASES: tuple[str, ...] = (
    "do you remember",
    "did i mention",
    "did i tell you",
    "you said",
    "you mentioned",
    "you told me",
    "we discussed",
    "we covered",
    "we talked about",
    "did we discuss",
    "earlier you",
    "last time we",
    "last time you",
    "what do you know about",
    "what's my",
    "whats my",
    "what are my",
    "what did i",
    "what did we",
    "recall ",
    "remember when",
)


def is_memory_query(text: str) -> bool:
    """True iff `text` looks like a request to consult memory."""
    s = text.lower()
    return any(p in s for p in _TRIGGER_PHRASES)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd server && uv run pytest tests/test_memory_triggers.py -v
```

Expected: all parametrized cases pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/memory/triggers.py server/tests/test_memory_triggers.py
git commit -m "feat(memory): add phrase-level is_memory_query trigger"
```

---

## Task 3: MemoryStore — schema, open, close

**Files:**
- Create: `server/server/memory/store.py`
- Create: `server/tests/test_memory_store.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_memory_store.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd server && uv run pytest tests/test_memory_store.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement schema + open/close**

Create `server/server/memory/store.py`:

```python
"""Async SQLite-backed persistence for cross-session memory.

Single connection per MemoryStore instance. WAL journal mode for crash
durability. Driver: aiosqlite. Tests run against ":memory:".
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Self

import aiosqlite

from .types import Fact, RecentSummaryMeta, SessionSummary, Turn

log = logging.getLogger(__name__)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    ended_at    TEXT
);

CREATE TABLE IF NOT EXISTS turns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(session_id),
    ts          TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, id);

CREATE TABLE IF NOT EXISTS session_summaries (
    session_id  TEXT PRIMARY KEY REFERENCES sessions(session_id),
    summary     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS facts (
    key                TEXT PRIMARY KEY,
    value              TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    source_session_id  TEXT REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS recent_summary (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    summary         TEXT NOT NULL,
    refreshed_at    TEXT NOT NULL,
    last_turn_id    INTEGER NOT NULL
);
"""


def _utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class MemoryStore:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    @classmethod
    async def open(cls, path: str) -> Self:
        conn = await aiosqlite.connect(path)
        # WAL is unsupported on :memory:; ignore failures.
        try:
            await conn.execute("PRAGMA journal_mode=WAL")
        except aiosqlite.Error:
            pass
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.executescript(_SCHEMA_SQL)
        await conn.commit()
        return cls(conn)

    async def close(self) -> None:
        await self._conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd server && uv run pytest tests/test_memory_store.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add server/server/memory/store.py server/tests/test_memory_store.py
git commit -m "feat(memory): MemoryStore schema + open/close"
```

---

## Task 4: MemoryStore — sessions, turns, find_resumable

**Files:**
- Modify: `server/server/memory/store.py`
- Modify: `server/tests/test_memory_store.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_memory_store.py`:

```python
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
    # Must be the LAST 3 in chronological order.
    assert [t.content for t in turns] == ["u4", "a4", "u4"][:3] or [t.content for t in turns][-1] == "a4"
    assert len(turns) == 3


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/test_memory_store.py -v
```

Expected: 6 new failures, AttributeError for missing methods.

- [ ] **Step 3: Implement methods**

Append to `server/server/memory/store.py`:

```python
    # ─── sessions ─────────────────────────────────────────────────────

    async def start_session(self) -> str:
        import secrets

        session_id = secrets.token_hex(8)
        await self._conn.execute(
            "INSERT INTO sessions(session_id, started_at, ended_at) VALUES (?, ?, NULL)",
            (session_id, _utcnow_iso()),
        )
        await self._conn.commit()
        return session_id

    async def end_session(self, session_id: str) -> None:
        await self._conn.execute(
            "UPDATE sessions SET ended_at=? WHERE session_id=? AND ended_at IS NULL",
            (_utcnow_iso(), session_id),
        )
        await self._conn.commit()

    async def find_resumable(self, within_minutes: int) -> str | None:
        """Return the most recently-active session if its last turn is within the window."""
        cur = await self._conn.execute(
            """
            SELECT s.session_id, MAX(t.ts) AS last_ts
              FROM sessions s
              JOIN turns t ON t.session_id = s.session_id
             GROUP BY s.session_id
             ORDER BY last_ts DESC
             LIMIT 1
            """
        )
        row = await cur.fetchone()
        if row is None or row[1] is None:
            return None
        last_ts = datetime.strptime(row[1], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        if datetime.now(UTC) - last_ts > timedelta(minutes=within_minutes):
            return None
        return row[0]

    # ─── turns ────────────────────────────────────────────────────────

    async def append_turn(self, session_id: str, role: str, content: str) -> int:
        cur = await self._conn.execute(
            "INSERT INTO turns(session_id, ts, role, content) VALUES (?, ?, ?, ?)",
            (session_id, _utcnow_iso(), role, content),
        )
        await self._conn.commit()
        return cur.lastrowid or 0

    async def load_session_turns(self, session_id: str, cap: int) -> list[Turn]:
        """Return the LAST `cap` turns of the session, in chronological order."""
        cur = await self._conn.execute(
            """
            SELECT id, session_id, ts, role, content
              FROM turns
             WHERE session_id = ?
             ORDER BY id DESC
             LIMIT ?
            """,
            (session_id, cap),
        )
        rows = await cur.fetchall()
        rows = list(reversed(rows))
        return [Turn(id=r[0], session_id=r[1], ts=r[2], role=r[3], content=r[4]) for r in rows]
```

Also fix the test I wrote with a typo on cap=3. Replace the `test_load_session_turns_caps_to_latest` body with:

```python
async def test_load_session_turns_caps_to_latest(store: MemoryStore) -> None:
    sid = await store.start_session()
    for i in range(5):
        await store.append_turn(sid, "user", f"u{i}")
        await store.append_turn(sid, "assistant", f"a{i}")
    turns = await store.load_session_turns(sid, cap=3)
    assert len(turns) == 3
    # Last 3 rows from a 10-turn series in chronological order: a3, u4, a4.
    assert [t.content for t in turns] == ["a3", "u4", "a4"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && uv run pytest tests/test_memory_store.py -v
```

Expected: all tests in this file pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/memory/store.py server/tests/test_memory_store.py
git commit -m "feat(memory): MemoryStore sessions, turns, find_resumable"
```

---

## Task 5: MemoryStore — recent_summary

**Files:**
- Modify: `server/server/memory/store.py`
- Modify: `server/tests/test_memory_store.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_memory_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/test_memory_store.py -v
```

Expected: AttributeError on the new methods.

- [ ] **Step 3: Implement methods**

Append to `server/server/memory/store.py`:

```python
    # ─── recent_summary (single-row table) ────────────────────────────

    async def get_recent_summary(self) -> str:
        cur = await self._conn.execute("SELECT summary FROM recent_summary WHERE id=1")
        row = await cur.fetchone()
        return row[0] if row else ""

    async def get_recent_summary_meta(self) -> RecentSummaryMeta:
        cur = await self._conn.execute(
            "SELECT summary, refreshed_at, last_turn_id FROM recent_summary WHERE id=1"
        )
        row = await cur.fetchone()
        if row is None:
            return RecentSummaryMeta(summary="", refreshed_at="", last_turn_id=0)
        return RecentSummaryMeta(summary=row[0], refreshed_at=row[1], last_turn_id=row[2])

    async def write_recent_summary(self, summary: str, last_turn_id: int) -> None:
        await self._conn.execute(
            """
            INSERT INTO recent_summary(id, summary, refreshed_at, last_turn_id)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              summary = excluded.summary,
              refreshed_at = excluded.refreshed_at,
              last_turn_id = excluded.last_turn_id
            """,
            (summary, _utcnow_iso(), last_turn_id),
        )
        await self._conn.commit()

    async def turns_since(self, last_turn_id: int) -> int:
        cur = await self._conn.execute(
            "SELECT COUNT(*) FROM turns WHERE id > ?", (last_turn_id,)
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && uv run pytest tests/test_memory_store.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/memory/store.py server/tests/test_memory_store.py
git commit -m "feat(memory): MemoryStore recent_summary upsert + turns_since"
```

---

## Task 6: MemoryStore — facts (upsert, get, LRU evict)

**Files:**
- Modify: `server/server/memory/store.py`
- Modify: `server/tests/test_memory_store.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_memory_store.py`:

```python
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
    import asyncio

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/test_memory_store.py -v
```

Expected: AttributeError on `upsert_facts`, `get_facts`, `evict_facts_to_cap`.

- [ ] **Step 3: Implement methods**

Append to `server/server/memory/store.py`:

```python
    # ─── facts ────────────────────────────────────────────────────────

    async def get_facts(self) -> dict[str, str]:
        cur = await self._conn.execute("SELECT key, value FROM facts ORDER BY updated_at")
        return {row[0]: row[1] for row in await cur.fetchall()}

    async def upsert_facts(self, facts: list[Fact], source_session_id: str) -> None:
        if not facts:
            return
        now = _utcnow_iso()
        await self._conn.executemany(
            """
            INSERT INTO facts(key, value, updated_at, source_session_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at,
              source_session_id = excluded.source_session_id
            """,
            [(f.key, f.value, now, source_session_id) for f in facts],
        )
        await self._conn.commit()

    async def evict_facts_to_cap(self, cap: int) -> None:
        await self._conn.execute(
            """
            DELETE FROM facts
             WHERE key IN (
               SELECT key FROM facts
                ORDER BY updated_at DESC
                LIMIT -1 OFFSET ?
             )
            """,
            (cap,),
        )
        await self._conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && uv run pytest tests/test_memory_store.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/memory/store.py server/tests/test_memory_store.py
git commit -m "feat(memory): MemoryStore facts upsert + LRU eviction"
```

---

## Task 7: MemoryStore — session_summaries + search_turns

**Files:**
- Modify: `server/server/memory/store.py`
- Modify: `server/tests/test_memory_store.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_memory_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/test_memory_store.py -v
```

Expected: AttributeError on `write_session_summary`, `list_recent_summaries`, `search_turns`.

- [ ] **Step 3: Implement methods**

Append to `server/server/memory/store.py`:

```python
    # ─── session_summaries ────────────────────────────────────────────

    async def write_session_summary(self, session_id: str, summary: str) -> None:
        await self._conn.execute(
            """
            INSERT INTO session_summaries(session_id, summary, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
              summary = excluded.summary,
              created_at = excluded.created_at
            """,
            (session_id, summary, _utcnow_iso()),
        )
        await self._conn.commit()

    async def list_recent_summaries(self, limit: int) -> list[SessionSummary]:
        cur = await self._conn.execute(
            """
            SELECT s.session_id, s.started_at, s.ended_at, ss.summary
              FROM session_summaries ss
              JOIN sessions s ON s.session_id = ss.session_id
             ORDER BY ss.created_at DESC
             LIMIT ?
            """,
            (limit,),
        )
        rows = await cur.fetchall()
        return [
            SessionSummary(session_id=r[0], started_at=r[1], ended_at=r[2], summary=r[3])
            for r in rows
        ]

    # ─── verbatim search ──────────────────────────────────────────────

    async def search_turns(self, query: str, limit: int) -> list[Turn]:
        q = query.strip().lower()
        if not q:
            return []
        like = f"%{q}%"
        cur = await self._conn.execute(
            """
            SELECT id, session_id, ts, role, content
              FROM turns
             WHERE LOWER(content) LIKE ?
             ORDER BY id DESC
             LIMIT ?
            """,
            (like, limit),
        )
        rows = await cur.fetchall()
        return [Turn(id=r[0], session_id=r[1], ts=r[2], role=r[3], content=r[4]) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && uv run pytest tests/test_memory_store.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/server/memory/store.py server/tests/test_memory_store.py
git commit -m "feat(memory): MemoryStore session_summaries + search_turns"
```

---

## Task 8: Summarizer (Haiku, mocked in tests)

**Files:**
- Create: `server/server/memory/summarizer.py`
- Create: `server/tests/test_memory_summarizer.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_memory_summarizer.py`:

```python
"""Summarizer tests with a mocked AsyncAnthropic client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from server.memory.summarizer import ClaudeSummarizer
from server.memory.types import Turn


def _turns(*pairs: tuple[str, str]) -> list[Turn]:
    return [
        Turn(id=i + 1, session_id="s", ts="2026-05-08T10:00:00Z", role=role, content=content)
        for i, (role, content) in enumerate(pairs)
    ]


def _mock_client_returning(text: str) -> Any:
    """Build a MagicMock whose messages.create returns a faux Message with the given text."""
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    client.messages.create = AsyncMock(return_value=msg)
    return client


async def test_refresh_recent_summary_uses_haiku() -> None:
    client = _mock_client_returning("Recent summary text.")
    s = ClaudeSummarizer(client=client, model="claude-haiku-4-5-20251001")
    out = await s.refresh_recent_summary(_turns(("user", "hi"), ("assistant", "hello")))
    assert out == "Recent summary text."
    args, kwargs = client.messages.create.call_args
    assert kwargs["model"] == "claude-haiku-4-5-20251001"


async def test_summarize_session_returns_text() -> None:
    client = _mock_client_returning("We talked about deploys.")
    s = ClaudeSummarizer(client=client)
    out = await s.summarize_session(_turns(("user", "deploys?"), ("assistant", "Friday.")))
    assert out == "We talked about deploys."


async def test_extract_facts_parses_json_list() -> None:
    client = _mock_client_returning('[{"key": "lang", "value": "TS"}, {"key": "city", "value": "BRU"}]')
    s = ClaudeSummarizer(client=client)
    facts = await s.extract_facts(_turns(("user", "I use TS in BRU")))
    assert len(facts) == 2
    assert facts[0].key == "lang" and facts[0].value == "TS"


async def test_extract_facts_returns_empty_on_malformed_json() -> None:
    client = _mock_client_returning("not even close to json")
    s = ClaudeSummarizer(client=client)
    assert await s.extract_facts(_turns(("user", "hi"))) == []


async def test_extract_facts_returns_empty_on_empty_list() -> None:
    client = _mock_client_returning("[]")
    s = ClaudeSummarizer(client=client)
    assert await s.extract_facts(_turns(("user", "hi"))) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/test_memory_summarizer.py -v
```

Expected: ModuleNotFoundError for `server.memory.summarizer`.

- [ ] **Step 3: Implement `summarizer.py`**

Create `server/server/memory/summarizer.py`:

```python
"""Haiku-backed summarization for cross-session memory.

All three calls go to Haiku regardless of which model handles the
conversation. Predictable cost, good-enough quality. Failures are
logged and degraded to safe defaults (empty string / empty list).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from .types import Fact, Turn

log = logging.getLogger(__name__)


_RECENT_SYSTEM = (
    "You are a terse note-taker. Given the latest turns of a conversation, "
    "produce ONE OR TWO sentences capturing what was discussed and any pending "
    "action. No preamble. No bullet points. Plain prose."
)

_SESSION_SYSTEM = (
    "You are a terse note-taker. Given a finished conversation, produce ONE OR "
    "TWO sentences capturing the topic and any decisions or open questions. "
    "No preamble. Plain prose."
)

_FACTS_SYSTEM = (
    "You extract durable user-stated facts from a conversation. A fact is a "
    "stable piece of information about the user (preferences, identity claims, "
    "long-term circumstances). Skip ephemeral state ('I'm tired'), tasks, "
    "and questions. Respond with a JSON array of objects {\"key\": str, "
    "\"value\": str}, or [] if none. Output ONLY the JSON array — no prose."
)


def _format_turns(turns: list[Turn]) -> str:
    return "\n".join(f"{t.role}: {t.content}" for t in turns)


class Summarizer(Protocol):
    async def refresh_recent_summary(self, turns: list[Turn]) -> str: ...
    async def summarize_session(self, turns: list[Turn]) -> str: ...
    async def extract_facts(self, turns: list[Turn]) -> list[Fact]: ...


class ClaudeSummarizer:
    def __init__(
        self,
        *,
        client: Any,
        model: str = "claude-haiku-4-5-20251001",
        max_tokens: int = 256,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    async def _one_shot(self, system: str, transcript: str) -> str:
        try:
            msg = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": transcript}],
            )
            blocks = getattr(msg, "content", []) or []
            for b in blocks:
                text = getattr(b, "text", None)
                if text:
                    return str(text).strip()
            return ""
        except Exception:
            log.exception("summarizer call failed")
            return ""

    async def refresh_recent_summary(self, turns: list[Turn]) -> str:
        if not turns:
            return ""
        return await self._one_shot(_RECENT_SYSTEM, _format_turns(turns))

    async def summarize_session(self, turns: list[Turn]) -> str:
        if not turns:
            return ""
        return await self._one_shot(_SESSION_SYSTEM, _format_turns(turns))

    async def extract_facts(self, turns: list[Turn]) -> list[Fact]:
        if not turns:
            return []
        raw = await self._one_shot(_FACTS_SYSTEM, _format_turns(turns))
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("extract_facts: malformed JSON: %r", raw[:200])
            return []
        if not isinstance(data, list):
            return []
        out: list[Fact] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            value = item.get("value")
            if isinstance(key, str) and isinstance(value, str) and key:
                out.append(Fact(key=key, value=value))
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && uv run pytest tests/test_memory_summarizer.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add server/server/memory/summarizer.py server/tests/test_memory_summarizer.py
git commit -m "feat(memory): Haiku-backed Summarizer (mockable Protocol)"
```

---

## Task 9: MemoryContext — default + full blob

**Files:**
- Create: `server/server/memory/context.py`
- Create: `server/tests/test_memory_context.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_memory_context.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/test_memory_context.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `context.py`**

Create `server/server/memory/context.py`:

```python
"""Builds the per-turn extra_context blob fed to the LLM.

Two paths:
- default(store)         — small "Background: <recent_summary>" only
- full(store, user_text) — full blob: background + facts + recent sessions + matched turns

Section caps are enforced here, not in the store.
"""

from __future__ import annotations

import re

from .store import MemoryStore

FACTS_CAP_DEFAULT = 50
DIGEST_SESSIONS_DEFAULT = 10
SEARCH_CAP_DEFAULT = 5


def _query_tokens(user_text: str) -> list[str]:
    s = re.sub(r"[^\w\s]", " ", user_text.lower())
    tokens = [t for t in s.split() if len(t) > 3]
    tokens.sort(key=len, reverse=True)
    return tokens[:3]


class MemoryContext:
    @staticmethod
    async def default(store: MemoryStore) -> str:
        summary = await store.get_recent_summary()
        if not summary:
            return ""
        return f"Background (recent conversation summary):\n{summary}"

    @staticmethod
    async def full(
        store: MemoryStore,
        user_text: str,
        *,
        facts_cap: int = FACTS_CAP_DEFAULT,
        digest_sessions: int = DIGEST_SESSIONS_DEFAULT,
        search_cap: int = SEARCH_CAP_DEFAULT,
    ) -> str:
        sections: list[str] = []

        recent = await store.get_recent_summary()
        if recent:
            sections.append(f"Background (recent conversation summary):\n{recent}")

        facts = await store.get_facts()
        if facts:
            shown = list(facts.items())[:facts_cap]
            lines = "\n".join(f"- {k}: {v}" for k, v in shown)
            sections.append(f"What I know about you (from prior conversations):\n{lines}")

        summaries = await store.list_recent_summaries(limit=digest_sessions)
        if summaries:
            lines = "\n".join(f"- {s.started_at}: {s.summary}" for s in summaries)
            sections.append(f"Recent sessions (most recent first):\n{lines}")

        # Verbatim search across all turns.
        matches: list = []
        for tok in _query_tokens(user_text):
            matches = await store.search_turns(tok, limit=search_cap)
            if matches:
                break
        if matches:
            lines = "\n".join(
                f"- [{t.role}, {t.ts[:10]}] \"{t.content}\"" for t in matches[:search_cap]
            )
            sections.append(f"Possibly relevant past exchanges:\n{lines}")

        return "\n\n".join(sections)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && uv run pytest tests/test_memory_context.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add server/server/memory/context.py server/tests/test_memory_context.py
git commit -m "feat(memory): MemoryContext default + full blob assembly"
```

---

## Task 10: LLM ABC — `extra_context` kwarg

**Files:**
- Modify: `server/server/pipelines/interfaces.py`
- Modify: `server/server/pipelines/claude_llm.py`
- Modify: `server/server/pipelines/mock_llm.py`
- Modify: `server/tests/test_claude_llm.py` (extend, do not rewrite)

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_claude_llm.py`:

```python
async def test_extra_context_appended_to_system_prompt() -> None:
    """ClaudeLLM.stream concatenates extra_context after the base system prompt."""
    from unittest.mock import AsyncMock, MagicMock
    from server.pipelines.claude_llm import ClaudeLLM, JARVIS_SYSTEM_PROMPT

    class _NoopStream:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        def __aiter__(self): return self
        async def __anext__(self): raise StopAsyncIteration

    captured: dict = {}

    def _stream(**kwargs):
        captured.update(kwargs)
        return _NoopStream()

    client = MagicMock()
    client.messages.stream = MagicMock(side_effect=_stream)
    llm = ClaudeLLM(default_model="claude-haiku-4-5", client=client)
    async for _ in llm.stream(
        history=[{"role": "user", "content": "hi"}],
        user_text="hi",
        extra_context="Background: weather is nice.",
    ):
        pass
    assert captured["system"].startswith(JARVIS_SYSTEM_PROMPT)
    assert "Background: weather is nice." in captured["system"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd server && uv run pytest tests/test_claude_llm.py::test_extra_context_appended_to_system_prompt -v
```

Expected: TypeError "stream() got an unexpected keyword argument 'extra_context'".

- [ ] **Step 3: Update the ABC and impls**

In `server/server/pipelines/interfaces.py`, change the `LLM.stream` signature:

```python
class LLM(ABC):
    """Large language model client."""

    @abstractmethod
    def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]:
        """Yield token deltas. Caller appends user/assistant to history.

        `extra_context` is concatenated onto the system prompt for this turn
        only. Used by Session to inject memory blobs without touching `history`.
        """
```

In `server/server/pipelines/claude_llm.py`, change `ClaudeLLM.stream`:

```python
    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]:
        model, content = parse_prefix(user_text, self._default_model)
        messages = [*history[:-1], {"role": "user", "content": content}]
        system = self._system_prompt
        if extra_context:
            system = f"{system}\n\n{extra_context}"
        try:
            async with self._client.messages.stream(
                model=model,
                max_tokens=max_tokens_for(model, self._max_tokens),
                system=system,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta is not None
                        and event.delta.type == "text_delta"
                    ):
                        yield event.delta.text
        except anthropic.APIError as exc:
            logger.exception("Anthropic API error")
            yield _spoken_error_for(exc)
```

In `server/server/pipelines/mock_llm.py`, change `MockLLM.stream`:

```python
    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]:
        del extra_context  # mock ignores
        scenario = pick_scenario(user_text)
        ...
```

(Keep the rest of `MockLLM.stream` body unchanged.)

- [ ] **Step 4: Run all tests**

```bash
cd server && uv run pytest -v
```

Expected: every test passes — including the new one and every existing one.

- [ ] **Step 5: Commit**

```bash
git add server/server/pipelines/interfaces.py server/server/pipelines/claude_llm.py server/server/pipelines/mock_llm.py server/tests/test_claude_llm.py
git commit -m "feat(llm): add extra_context kwarg to LLM.stream"
```

---

## Task 11: Session — connect with resume

**Files:**
- Modify: `server/server/session.py`
- Create: `server/tests/test_memory_session.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_memory_session.py`:

```python
"""Session × MemoryStore integration with FakeSummarizer + MockLLM."""

from __future__ import annotations

import asyncio

import pytest

from server.memory.store import MemoryStore
from server.memory.types import Fact, Turn
from server.pipelines.mock_llm import MockLLM
from server.pipelines.mock_stt import MockSTT
from server.pipelines.mock_tts import MockTTS
from server.session import Session


class _FakeWS:
    def __init__(self) -> None:
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._closed = False

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def receive(self):
        return await self._inbox.get()

    def queue_disconnect(self) -> None:
        self._inbox.put_nowait({"type": "websocket.disconnect"})


class FakeSummarizer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def refresh_recent_summary(self, turns: list[Turn]) -> str:
        self.calls.append("refresh")
        return f"recent[{len(turns)}]"

    async def summarize_session(self, turns: list[Turn]) -> str:
        self.calls.append("session")
        return f"session[{len(turns)}]"

    async def extract_facts(self, turns: list[Turn]) -> list[Fact]:
        self.calls.append("facts")
        return [Fact("turns_seen", str(len(turns)))]


@pytest.fixture
async def store() -> MemoryStore:
    s = await MemoryStore.open(":memory:")
    yield s
    await s.close()


async def test_session_resume_picks_up_recent_session(store: MemoryStore) -> None:
    sid = await store.start_session()
    await store.append_turn(sid, "user", "earlier hi")
    await store.append_turn(sid, "assistant", "earlier hello")

    ws = _FakeWS()
    sess = Session(
        ws=ws,
        stt=MockSTT(),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
        memory=store,
        summarizer=FakeSummarizer(),
    )
    ws.queue_disconnect()
    await sess.run()
    assert sess.session_id == sid
    # _history seeded from prior session
    assert any(m["content"] == "earlier hi" for m in sess._history)


async def test_session_starts_fresh_when_nothing_resumable(store: MemoryStore) -> None:
    ws = _FakeWS()
    sess = Session(
        ws=ws,
        stt=MockSTT(),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
        memory=store,
        summarizer=FakeSummarizer(),
    )
    ws.queue_disconnect()
    await sess.run()
    assert sess._history == []


async def test_session_no_memory_starts_fresh() -> None:
    ws = _FakeWS()
    sess = Session(
        ws=ws,
        stt=MockSTT(),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
        memory=None,
    )
    ws.queue_disconnect()
    await sess.run()
    assert sess._history == []
    assert sess.session_id  # auto-generated, not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/test_memory_session.py -v
```

Expected: TypeError on `Session.__init__` for `memory`/`summarizer` kwargs.

- [ ] **Step 3: Modify `Session.__init__` and `run`**

In `server/server/session.py`:

Add imports near the top:

```python
from .memory.store import MemoryStore
from .memory.summarizer import Summarizer
```

Update `Session.__init__`:

```python
    def __init__(
        self,
        ws: _WS,
        stt: STT,
        llm: LLM,
        tts: TTS,
        history_cap: int = 20,
        *,
        memory: MemoryStore | None = None,
        summarizer: Summarizer | None = None,
        resume_window_minutes: int = 30,
        recent_summary_refresh_turns: int = 5,
        recent_summary_window: int = 20,
        facts_cap: int = 50,
    ) -> None:
        self._ws = ws
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._history: list[dict[str, str]] = []
        self._history_cap = history_cap
        self._memory = memory
        self._summarizer = summarizer
        self._resume_window_minutes = resume_window_minutes
        self._refresh_turns = recent_summary_refresh_turns
        self._recent_window = recent_summary_window
        self._facts_cap = facts_cap
        # ... existing field initialisation unchanged ...
```

(Preserve every existing field initialisation; only add the memory-related ones.)

Update `Session.run` to perform resume just before the existing `await self._enqueue_json(ServerMessage.ready(...))`:

```python
    async def run(self) -> None:
        self._sender_task = asyncio.create_task(self._sender_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._state_task = asyncio.create_task(self.emitter.run())

        # ── memory: resume or start a new session ──────────────────
        if self._memory is not None:
            resumable = await self._memory.find_resumable(
                within_minutes=self._resume_window_minutes
            )
            if resumable is not None:
                self.session_id = resumable
                turns = await self._memory.load_session_turns(resumable, cap=self._history_cap)
                self._history = [{"role": t.role, "content": t.content} for t in turns]
            else:
                self.session_id = await self._memory.start_session()

        await self._enqueue_json(ServerMessage.ready(session_id=self.session_id))
        # ... rest of run() unchanged ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && uv run pytest tests/test_memory_session.py -v
cd server && uv run pytest -v
```

Expected: new tests pass; no regressions in existing tests.

- [ ] **Step 5: Commit**

```bash
git add server/server/session.py server/tests/test_memory_session.py
git commit -m "feat(session): memory-backed connect/resume on Session.run"
```

---

## Task 12: Session — per-turn writes + extra_context + refresh

**Files:**
- Modify: `server/server/session.py`
- Modify: `server/tests/test_memory_session.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_memory_session.py`:

```python
class _RecordingLLM:
    def __init__(self) -> None:
        self.last_extra: str = "<unset>"

    async def stream(self, history, user_text, *, extra_context: str = ""):
        self.last_extra = extra_context
        for ch in "ok":
            yield ch


async def _drive_session(sess: Session, ws: _FakeWS, *texts: str) -> None:
    """Run sess.run() while sending text.in turns and waiting for each to complete."""
    import json

    run_task = asyncio.create_task(sess.run())
    try:
        await asyncio.sleep(0)  # let run() reach the receive loop
        for text in texts:
            payload = json.dumps({"type": "text.in", "content": text})
            ws._inbox.put_nowait({"type": "websocket.receive", "text": payload})
            # Wait for the turn task to be created AND complete.
            for _ in range(500):
                await asyncio.sleep(0.005)
                t = sess._turn_task
                if t is not None and t.done():
                    break
        ws._inbox.put_nowait({"type": "websocket.disconnect"})
        await run_task
    except Exception:
        run_task.cancel()
        raise


async def test_session_writes_user_and_assistant_turns(store: MemoryStore) -> None:
    ws = _FakeWS()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=_RecordingLLM(), tts=MockTTS(),
        memory=store, summarizer=FakeSummarizer(),
    )
    await _drive_session(sess, ws, "hello")
    turns = await store.load_session_turns(sess.session_id, cap=10)
    assert [t.role for t in turns] == ["user", "assistant"]
    assert turns[0].content == "hello"


async def test_session_passes_default_extra_context_when_no_trigger(store: MemoryStore) -> None:
    await store.write_recent_summary("recent stuff", last_turn_id=0)
    ws = _FakeWS()
    rec = _RecordingLLM()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=rec, tts=MockTTS(),
        memory=store, summarizer=FakeSummarizer(),
    )
    await _drive_session(sess, ws, "hello there")
    assert "Background" in rec.last_extra
    assert "What I know about you" not in rec.last_extra


async def test_session_passes_full_extra_context_on_trigger(store: MemoryStore) -> None:
    sid = await store.start_session()
    await store.upsert_facts([Fact("lang", "TypeScript")], sid)
    await store.write_recent_summary("recent stuff", last_turn_id=0)
    ws = _FakeWS()
    rec = _RecordingLLM()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=rec, tts=MockTTS(),
        memory=store, summarizer=FakeSummarizer(),
    )
    await _drive_session(sess, ws, "what's my preferred lang")
    assert "What I know about you" in rec.last_extra
    assert "lang: TypeScript" in rec.last_extra


async def test_session_refreshes_recent_summary_after_threshold(store: MemoryStore) -> None:
    ws = _FakeWS()
    fake = FakeSummarizer()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=_RecordingLLM(), tts=MockTTS(),
        memory=store, summarizer=fake, recent_summary_refresh_turns=2,
    )
    await _drive_session(sess, ws, "turn 0", "turn 1", "turn 2")
    assert "refresh" in fake.calls
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/test_memory_session.py -v
```

Expected: tests fail because per-turn integration is not yet wired.

- [ ] **Step 3: Modify `Session._do_llm_and_tts`**

In `server/server/session.py`, replace the existing `_do_llm_and_tts` body — keeping every existing block (fanout, sentence split, TTS, history append, token-budget metric) and inserting the memory hooks:

```python
    async def _do_llm_and_tts(self, user_text: str) -> None:
        from .memory.context import MemoryContext
        from .memory.triggers import is_memory_query

        self._history.append({"role": "user", "content": user_text})
        if self._memory is not None:
            await self._memory.append_turn(self.session_id, "user", user_text)

        extra = ""
        if self._memory is not None:
            if is_memory_query(user_text):
                extra = await MemoryContext.full(self._memory, user_text)
            else:
                extra = await MemoryContext.default(self._memory)

        llm_iter = self._llm.stream(self._history, user_text, extra_context=extra)
        token_q: asyncio.Queue[str | None] = asyncio.Queue()
        sentence_q: asyncio.Queue[str | None] = asyncio.Queue()
        assistant_buf: list[str] = []

        # ── existing fanout / consume_tokens_to_sentences / speak_sentences blocks
        # ── unchanged from current session.py — keep them as-is.

        await asyncio.gather(fanout(), consume_tokens_to_sentences(), speak_sentences())

        full = "".join(assistant_buf)
        if full:
            self._history.append({"role": "assistant", "content": full})
            if self._memory is not None:
                await self._memory.append_turn(self.session_id, "assistant", full)
        if len(self._history) > self._history_cap:
            self._history = self._history[-self._history_cap :]

        total_chars = sum(len(m["content"]) for m in self._history)
        self.emitter.record_token_budget(total_chars // 4)

        await self._maybe_refresh_recent_summary()
```

Add the helper at the end of the class:

```python
    async def _maybe_refresh_recent_summary(self) -> None:
        if self._memory is None or self._summarizer is None:
            return
        meta = await self._memory.get_recent_summary_meta()
        delta = await self._memory.turns_since(meta.last_turn_id)
        if delta < self._refresh_turns:
            return
        # Pull the latest N turns across all sessions for the summary.
        cur = await self._memory._conn.execute(
            "SELECT id, session_id, ts, role, content FROM turns ORDER BY id DESC LIMIT ?",
            (self._recent_window,),
        )
        rows = list(reversed(await cur.fetchall()))
        from .memory.types import Turn
        latest = [Turn(id=r[0], session_id=r[1], ts=r[2], role=r[3], content=r[4]) for r in rows]
        if not latest:
            return
        try:
            summary = await self._summarizer.refresh_recent_summary(latest)
            if summary:
                await self._memory.write_recent_summary(summary, latest[-1].id)
        except Exception:
            log.exception("recent_summary refresh failed")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && uv run pytest tests/test_memory_session.py -v
cd server && uv run pytest -v
```

Expected: new tests pass; no regressions.

- [ ] **Step 5: Commit**

```bash
git add server/server/session.py server/tests/test_memory_session.py
git commit -m "feat(session): per-turn memory writes + extra_context routing"
```

---

## Task 13: Session — cleanup consolidation

**Files:**
- Modify: `server/server/session.py`
- Modify: `server/tests/test_memory_session.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_memory_session.py`:

```python
async def test_cleanup_consolidates_when_session_has_turns(store: MemoryStore) -> None:
    ws = _FakeWS()
    fake = FakeSummarizer()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=_RecordingLLM(), tts=MockTTS(),
        memory=store, summarizer=fake,
    )
    await _drive_session(sess, ws, "hi")  # cleanup runs in run()'s finally

    summaries = await store.list_recent_summaries(limit=5)
    assert len(summaries) == 1
    facts = await store.get_facts()
    assert "turns_seen" in facts


async def test_cleanup_skips_consolidation_for_empty_session(store: MemoryStore) -> None:
    ws = _FakeWS()
    fake = FakeSummarizer()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=_RecordingLLM(), tts=MockTTS(),
        memory=store, summarizer=fake,
    )
    ws.queue_disconnect()
    await sess.run()

    assert "session" not in fake.calls  # no summarize_session
    assert await store.list_recent_summaries(limit=5) == []


async def test_cleanup_swallows_summarizer_exceptions(store: MemoryStore) -> None:
    class _Bomb(FakeSummarizer):
        async def summarize_session(self, turns):
            raise RuntimeError("boom")

    ws = _FakeWS()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=_RecordingLLM(), tts=MockTTS(),
        memory=store, summarizer=_Bomb(),
    )
    await _drive_session(sess, ws, "hi")  # MUST NOT raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/test_memory_session.py -v
```

Expected: 3 new failures.

- [ ] **Step 3: Modify `Session.cleanup`**

In `server/server/session.py`, append a new private helper and call it from `cleanup` AFTER existing task cancellations but BEFORE the sender-stop block:

```python
    async def cleanup(self) -> None:
        self._closing = True
        for t in (
            self._partials_task,
            self._turn_task,
            self._heartbeat_task,
            self._state_task,
            self._calendar_sync_task,
        ):
            if t and not t.done():
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t

        await self._consolidate_memory()  # NEW

        if self._sender_task and not self._sender_task.done():
            try:
                self._send_q.put_nowait(("__stop__", ""))
            except asyncio.QueueFull:
                self._sender_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._sender_task

    async def _consolidate_memory(self) -> None:
        if self._memory is None or self._summarizer is None:
            return
        try:
            turns = await self._memory.load_session_turns(self.session_id, cap=200)
            if len(turns) >= 2:
                summary = await self._summarizer.summarize_session(turns)
                if summary:
                    await self._memory.write_session_summary(self.session_id, summary)
                facts = await self._summarizer.extract_facts(turns)
                if facts:
                    await self._memory.upsert_facts(facts, source_session_id=self.session_id)
                    await self._memory.evict_facts_to_cap(self._facts_cap)
            await self._memory.end_session(self.session_id)
        except Exception:
            log.exception("memory consolidation failed")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && uv run pytest tests/test_memory_session.py -v
cd server && uv run pytest -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add server/server/session.py server/tests/test_memory_session.py
git commit -m "feat(session): synchronous memory consolidation in cleanup"
```

---

## Task 14: Wire MemoryStore at startup; honour env vars

**Files:**
- Modify: `server/server/config.py`
- Modify: `server/server/main.py`

- [ ] **Step 1: Inspect current config**

Read `server/server/config.py` to see the existing `Settings` class. The pattern below assumes pydantic-settings; if the file uses a different style, mirror it.

- [ ] **Step 2: Add memory settings**

In `server/server/config.py`, add to the `Settings` class:

```python
    memory_enabled: bool = True            # JARVIS_MEMORY ("off"/"false" disables)
    memory_db_path: str = "server/data/memory.db"   # JARVIS_MEMORY_DB
    memory_resume_minutes: int = 30        # JARVIS_MEMORY_RESUME_MIN
    memory_refresh_turns: int = 5          # JARVIS_MEMORY_REFRESH_TURNS
    memory_recent_window: int = 20         # JARVIS_MEMORY_RECENT_WINDOW
    memory_facts_cap: int = 50             # JARVIS_MEMORY_FACTS_CAP
    memory_model: str = "claude-haiku-4-5-20251001"  # JARVIS_MEMORY_MODEL
```

If the existing `Settings` uses pydantic-settings field aliases, mirror that style. Otherwise rely on default `JARVIS_*` env-var binding consistent with the existing `model_name` / `anthropic_api_key` fields.

If `JARVIS_MEMORY` is set to `off` or `false`, set `memory_enabled = False`. Add a `@field_validator` if needed.

- [ ] **Step 3: Wire it in `main.py`**

Replace `server/server/main.py:52-56` (the existing `lifespan`) and `server/server/main.py:82-99` (the websocket endpoint) with:

```python
from pathlib import Path

from .memory.store import MemoryStore
from .memory.summarizer import ClaudeSummarizer, Summarizer


_memory_store: MemoryStore | None = None
_summarizer: Summarizer | None = None


def _build_summarizer() -> Summarizer | None:
    if settings.anthropic_api_key is None:
        log.warning("memory: ANTHROPIC_API_KEY unset; summarization disabled")
        return None
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    return ClaudeSummarizer(client=client, model=settings.memory_model)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _memory_store, _summarizer
    log.info("lifespan: Phase 1 mock pipelines (no model loading)")
    if settings.memory_enabled:
        Path(settings.memory_db_path).parent.mkdir(parents=True, exist_ok=True)
        _memory_store = await MemoryStore.open(settings.memory_db_path)
        _summarizer = _build_summarizer()
        log.info("memory: enabled at %s", settings.memory_db_path)
    else:
        log.info("memory: disabled")
    try:
        yield
    finally:
        if _memory_store is not None:
            await _memory_store.close()


app = FastAPI(lifespan=lifespan, title="Jarvis backend (spec-02 Phase 1)")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


class _StarletteWSAdapter:
    """Adapter so Session._WS protocol matches FastAPI WebSocket."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def send_text(self, data: str) -> None:
        await self._ws.send_text(data)

    async def send_bytes(self, data: bytes) -> None:
        await self._ws.send_bytes(data)

    async def receive(self) -> MutableMapping[str, Any]:
        return await self._ws.receive()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    session = Session(
        ws=_StarletteWSAdapter(ws),
        stt=MockSTT(),
        llm=_build_llm(),
        tts=MockTTS(),
        memory=_memory_store,
        summarizer=_summarizer,
        resume_window_minutes=settings.memory_resume_minutes,
        recent_summary_refresh_turns=settings.memory_refresh_turns,
        recent_summary_window=settings.memory_recent_window,
        facts_cap=settings.memory_facts_cap,
    )
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    finally:
        await session.cleanup()
        with contextlib.suppress(Exception):
            await ws.close()
```

- [ ] **Step 4: Smoke-run the server**

```bash
cd server && JARVIS_MEMORY=off uv run uvicorn server.main:app --port 8001 &
sleep 2
curl -s http://localhost:8001/health
kill %1
```

Expected: `{"status":"ok"}` and the log line `memory: disabled`.

Repeat with memory enabled:

```bash
cd server && uv run uvicorn server.main:app --port 8001 &
sleep 2
curl -s http://localhost:8001/health
ls -la data/memory.db
kill %1
```

Expected: `{"status":"ok"}`, log line `memory: enabled at server/data/memory.db`, and the SQLite file exists.

- [ ] **Step 5: Run full test suite**

```bash
cd server && uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add server/server/config.py server/server/main.py
git commit -m "feat(memory): wire MemoryStore + Summarizer in app lifespan"
```

---

## Task 15: Verification before completion

**Files:**
- No code changes; verification only.

- [ ] **Step 1: Read the verification skill**

```bash
cat .claude/skills/verification-before-completion.md
```

Follow it exactly.

- [ ] **Step 2: Lint and typecheck**

```bash
cd server && uv run ruff check .
cd server && uv run mypy server
```

Expected: zero errors. Fix any new warnings introduced by this branch (do not touch unrelated existing warnings).

- [ ] **Step 3: Run the full test suite once more**

```bash
cd server && uv run pytest -v
```

Expected: all pass.

- [ ] **Step 4: Acceptance-criteria walkthrough**

Walk through every item in spec §13 and confirm a test or observation backs it:

1. `pytest server/tests/test_memory_*.py` passes — `uv run pytest tests/test_memory_*.py`
2. `pytest server/tests/test_session.py` still passes — covered above
3. `JARVIS_MEMORY=off` reverts to in-RAM behaviour — Task 14 step 4 smoke
4. Resume-on-reconnect works — `test_session_resume_picks_up_recent_session`
5. Trigger phrase loads full blob — `test_session_passes_full_extra_context_on_trigger`
6. ≥2-turn session leaves rows in `session_summaries` and `facts` — `test_cleanup_consolidates_when_session_has_turns`

If any criterion has no backing test, add one before declaring done.

- [ ] **Step 5: Manual smoke (optional, dev machine)**

With a real `ANTHROPIC_API_KEY` set:

```bash
cd server && uv run uvicorn server.main:app --port 8000
```

Then run `client/jarvis-cli` (or whichever client) and verify:
- A short conversation, then disconnect.
- Reconnect within 30 minutes — JARVIS picks up the prior context (visible by the model referencing what was just discussed).
- Disconnect, wait, reconnect after window — fresh `_history`, but a memory-trigger phrase ("do you remember…") surfaces the prior session's content.

---

## Self-review

After tasks 0–15 are written, this plan was checked against `2026-05-08-cross-session-memory-design.md`:

- §4.1 `MemoryStore` API — every method covered (Tasks 3–7).
- §4.2 `Summarizer` — Task 8.
- §4.3 `triggers.is_memory_query` — Task 2.
- §4.4 `MemoryContext.default` / `.full` — Task 9, with caps from §8 enforced and tested.
- §4.5 `LLM.extra_context` — Task 10.
- §5 Schema — Task 3.
- §6.1 Resume on connect — Task 11.
- §6.2 Per-turn flow — Task 12.
- §6.3 Cleanup consolidation — Task 13.
- §7 Trigger landmines — Task 2 false-positive cases.
- §8 Defaults / env vars — Task 14.
- §9 Test files — every file enumerated in §9 has a corresponding task.
- §13 Acceptance criteria — Task 15 step 4 walkthrough.
- §12 Out-of-scope items — none implemented (correct).

No placeholders, no "implement later". Type names (`Turn`, `Fact`, `SessionSummary`, `RecentSummaryMeta`) used consistently from Task 1 onward.

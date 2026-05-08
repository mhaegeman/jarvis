"""Async SQLite-backed persistence for cross-session memory.

Single connection per MemoryStore instance. WAL journal mode for crash
durability. Driver: aiosqlite. Tests run against ":memory:".
"""

from __future__ import annotations

import contextlib
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
        with contextlib.suppress(aiosqlite.Error):
            await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.executescript(_SCHEMA_SQL)
        await conn.commit()
        return cls(conn)

    async def close(self) -> None:
        await self._conn.close()

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
             ORDER BY ss.rowid DESC
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

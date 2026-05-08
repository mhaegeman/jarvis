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

from .types import Fact, RecentSummaryMeta, SessionSummary, Turn  # noqa: F401

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

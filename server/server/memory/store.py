"""Async SQLite-backed persistence for cross-session memory.

Single connection per MemoryStore instance. WAL journal mode for crash
durability. Driver: aiosqlite. Tests run against ":memory:".
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
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

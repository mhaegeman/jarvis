"""Phase 5 schema migration tests."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from server.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_dispatch_log_table_created(tmp_path: Path) -> None:
    store = await MemoryStore.open(str(tmp_path / "memory.db"))
    try:
        async with aiosqlite.connect(str(tmp_path / "memory.db")) as db:
            cur = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='dispatch_log'"
            )
            row = await cur.fetchone()
            assert row is not None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_personas_table_created(tmp_path: Path) -> None:
    store = await MemoryStore.open(str(tmp_path / "memory.db"))
    try:
        async with aiosqlite.connect(str(tmp_path / "memory.db")) as db:
            cur = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='personas'"
            )
            assert await cur.fetchone() is not None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_migrations_idempotent(tmp_path: Path) -> None:
    """Re-opening the same DB doesn't error or duplicate tables."""
    path = str(tmp_path / "memory.db")
    s1 = await MemoryStore.open(path)
    await s1.close()
    s2 = await MemoryStore.open(path)
    try:
        async with aiosqlite.connect(path) as db:
            cur = await db.execute(
                "SELECT count(*) FROM sqlite_master "
                "WHERE type='table' AND name IN ('dispatch_log','personas')"
            )
            count_row = await cur.fetchone()
            assert count_row is not None
            assert count_row[0] == 2
    finally:
        await s2.close()


@pytest.mark.asyncio
async def test_dispatch_log_columns(tmp_path: Path) -> None:
    """Spec §8.1: turn_id, ts, utterance, explicit, plan_json, rationale, outcome_json."""
    path = str(tmp_path / "memory.db")
    store = await MemoryStore.open(path)
    try:
        async with aiosqlite.connect(path) as db:
            cur = await db.execute("PRAGMA table_info(dispatch_log)")
            cols = {row[1] for row in await cur.fetchall()}
            assert {
                "turn_id", "ts", "utterance", "explicit",
                "plan_json", "rationale", "outcome_json",
            }.issubset(cols)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_personas_columns(tmp_path: Path) -> None:
    """Spec §8.1: id, profile, last_refresh, refresh_count."""
    path = str(tmp_path / "memory.db")
    store = await MemoryStore.open(path)
    try:
        async with aiosqlite.connect(path) as db:
            cur = await db.execute("PRAGMA table_info(personas)")
            cols = {row[1] for row in await cur.fetchall()}
            assert {"id", "profile", "last_refresh", "refresh_count"}.issubset(cols)
    finally:
        await store.close()

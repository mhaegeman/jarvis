"""Tests for server.dialog.feedback.FeedbackLogger."""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite
import pytest

from server.dialog.types import Outcome, Plan, Segment
from server.memory.store import MemoryStore

# ── helpers ──────────────────────────────────────────────────────────────

def _make_plan(speaker: str = "jarvis") -> Plan:
    return Plan(
        segments=[Segment(speaker=speaker, tier="fast", mode="chat", intent="test intent")],  # type: ignore[arg-type]
        rationale="test rationale",
    )


def _make_outcome(completed: bool = True) -> Outcome:
    return Outcome(completed=completed, latency_ms=120.5)


async def _open_store_and_logger(tmp_path: Path):  # type: ignore[return]
    """Open a MemoryStore (which creates the tables) + a FeedbackLogger on the same DB."""
    from server.dialog.feedback import FeedbackLogger

    db_path = str(tmp_path / "memory.db")
    store = await MemoryStore.open(db_path)
    logger = FeedbackLogger(db_path)
    return store, logger, db_path


# ── row-written tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_turn_inserts_row(tmp_path: Path) -> None:
    store, logger, db_path = await _open_store_and_logger(tmp_path)
    try:
        await logger.record_turn(
            turn_id="t1",
            utterance="hello",
            explicit=None,
            plan=_make_plan(),
            outcome=_make_outcome(),
        )
        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute("SELECT turn_id FROM dispatch_log WHERE turn_id='t1'")
            row = await cur.fetchone()
            assert row is not None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_record_turn_stores_utterance(tmp_path: Path) -> None:
    store, logger, db_path = await _open_store_and_logger(tmp_path)
    try:
        await logger.record_turn(
            turn_id="t2",
            utterance="what time is it",
            explicit="jarvis",
            plan=_make_plan("jarvis"),
            outcome=_make_outcome(),
        )
        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute(
                "SELECT utterance, explicit FROM dispatch_log WHERE turn_id='t2'"
            )
            row = await cur.fetchone()
            assert row is not None
            assert row[0] == "what time is it"
            assert row[1] == "jarvis"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_record_turn_outcome_json(tmp_path: Path) -> None:
    store, logger, db_path = await _open_store_and_logger(tmp_path)
    try:
        outcome = Outcome(completed=True, latency_ms=200.0, tokens_out=42)
        await logger.record_turn(
            turn_id="t3",
            utterance="test",
            explicit=None,
            plan=_make_plan(),
            outcome=outcome,
        )
        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute("SELECT outcome_json FROM dispatch_log WHERE turn_id='t3'")
            row = await cur.fetchone()
            assert row is not None
            data = json.loads(row[0])
            assert data["completed"] is True
            assert data["tokens_out"] == 42
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_record_turn_plan_json(tmp_path: Path) -> None:
    store, logger, db_path = await _open_store_and_logger(tmp_path)
    try:
        plan = _make_plan("pepper")
        await logger.record_turn(
            turn_id="t4",
            utterance="run tests",
            explicit=None,
            plan=plan,
            outcome=_make_outcome(),
        )
        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute(
                "SELECT plan_json, rationale FROM dispatch_log WHERE turn_id='t4'"
            )
            row = await cur.fetchone()
            assert row is not None
            plan_data = json.loads(row[0])
            assert plan_data["segments"][0]["speaker"] == "pepper"
            assert row[1] == "test rationale"
    finally:
        await store.close()


# ── tag_readdress tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tag_readdress_updates_prior_turn(tmp_path: Path) -> None:
    store, logger, db_path = await _open_store_and_logger(tmp_path)
    try:
        await logger.record_turn(
            turn_id="prior",
            utterance="jarvis explain this",
            explicit=None,
            plan=_make_plan("jarvis"),
            outcome=Outcome(completed=True),
        )
        await logger.tag_readdress(prior_turn_id="prior", other_speaker="pepper")
        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute(
                "SELECT outcome_json FROM dispatch_log WHERE turn_id='prior'"
            )
            row = await cur.fetchone()
            assert row is not None
            data = json.loads(row[0])
            assert data["next_turn_readdressed"] == "pepper"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_tag_readdress_missing_turn_is_noop(tmp_path: Path) -> None:
    """tag_readdress on a non-existent turn_id should not raise."""
    store, logger, db_path = await _open_store_and_logger(tmp_path)
    try:
        # Should not raise
        await logger.tag_readdress(prior_turn_id="does-not-exist", other_speaker="jarvis")
    finally:
        await store.close()


# ── recent() tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recent_returns_newest_first(tmp_path: Path) -> None:
    """Rows come back newest-first; use explicit ts values for determinism."""
    store, logger, db_path = await _open_store_and_logger(tmp_path)
    try:
        base_ts = 1_700_000_000.0
        for i, tid in enumerate(["old", "mid", "new"]):
            async with aiosqlite.connect(db_path) as db:
                plan = _make_plan()
                outcome = _make_outcome()
                await db.execute(
                    "INSERT OR REPLACE INTO dispatch_log "
                    "(turn_id, ts, utterance, explicit, plan_json, rationale, outcome_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        tid,
                        base_ts + i,       # old=+0, mid=+1, new=+2
                        f"utterance {i}",
                        None,
                        plan.model_dump_json(),
                        plan.rationale,
                        outcome.model_dump_json(),
                    ),
                )
                await db.commit()

        rows = await logger.recent(limit=10)
        assert len(rows) == 3
        ids = [r["turn_id"] for r in rows]
        assert ids[0] == "new"
        assert ids[-1] == "old"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_recent_respects_limit(tmp_path: Path) -> None:
    store, logger, db_path = await _open_store_and_logger(tmp_path)
    try:
        for i in range(5):
            await logger.record_turn(
                turn_id=f"turn-{i}",
                utterance="hi",
                explicit=None,
                plan=_make_plan(),
                outcome=_make_outcome(),
            )
        rows = await logger.recent(limit=3)
        assert len(rows) == 3
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_recent_row_shape(tmp_path: Path) -> None:
    store, logger, db_path = await _open_store_and_logger(tmp_path)
    try:
        await logger.record_turn(
            turn_id="shape-test",
            utterance="shape",
            explicit="jarvis",
            plan=_make_plan(),
            outcome=_make_outcome(),
        )
        rows = await logger.recent(limit=1)
        assert len(rows) == 1
        r = rows[0]
        expected_keys = {"turn_id", "ts", "utterance", "explicit", "plan", "rationale", "outcome"}
        assert set(r.keys()) == expected_keys
        assert r["turn_id"] == "shape-test"
        assert r["explicit"] == "jarvis"
        assert isinstance(r["plan"], dict)
        assert isinstance(r["outcome"], dict)
    finally:
        await store.close()

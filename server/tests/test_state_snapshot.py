"""Tests for the state.snapshot periodic emitter."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from server.heartbeat import Heartbeat
from server.state import StateEmitter, build_snapshot


def test_build_snapshot_packs_four_sub_objects() -> None:
    snap = build_snapshot(
        load=12.5,
        tokens_per_min=240,
        session_id="abc",
        model_name="mock",
        context_used=1024,
        context_max=200000,
        endpoint="ws://localhost:8000/ws",
        latency_ms=4.2,
        packets=17,
        send_queue_depth=3,
        send_queue_max=256,
        tasks={"queued": 1, "active": 0, "done": 5},
    )
    assert snap["type"] == "state.snapshot"
    assert snap["system"] == {
        "load": 12.5,
        "tokensPerMin": 240,
        "sessionId": "abc",
        "modelName": "mock",
    }
    assert snap["memory"] == {"contextUsed": 1024, "contextMax": 200000}
    assert snap["network"]["latencyMs"] == 4.2
    assert snap["tasks"] == {"queued": 1, "active": 0, "done": 5}


def test_build_snapshot_accepts_null_latency() -> None:
    snap = build_snapshot(
        load=0,
        tokens_per_min=0,
        session_id="s",
        model_name="m",
        context_used=0,
        context_max=1,
        endpoint="x",
        latency_ms=None,
        packets=0,
        send_queue_depth=0,
        send_queue_max=256,
        tasks={"queued": 0, "active": 0, "done": 0},
    )
    assert snap["network"]["latencyMs"] is None


class _FakeSession:
    """Minimal Session-shape for StateEmitter unit tests."""

    def __init__(self) -> None:
        self.heartbeat = Heartbeat()
        self.session_id = "test-session"
        self.endpoint = "ws://test/ws"
        self.send_queue_max = 256
        self.send_queue_depth = 0
        self.context_used = 0
        self.enqueued: list[dict] = []

    async def _enqueue_json(self, msg: dict) -> None:
        self.enqueued.append(msg)


def test_emitter_record_token_drives_tokens_per_min() -> None:
    sess = _FakeSession()
    em = StateEmitter(sess, interval_s=0.01)  # type: ignore[arg-type]
    for _ in range(120):
        em.record_token()
    assert em.tokens_per_min() >= 60  # at least 60 in last 60s


def test_emitter_record_packet_increments_counter() -> None:
    sess = _FakeSession()
    em = StateEmitter(sess, interval_s=0.01)  # type: ignore[arg-type]
    em.record_packet()
    em.record_packet()
    em.record_packet()
    assert em.packets() == 3


def test_emitter_record_token_budget_persists_until_replaced() -> None:
    sess = _FakeSession()
    em = StateEmitter(sess, interval_s=0.01)  # type: ignore[arg-type]
    em.record_token_budget(1500)
    assert em.context_used() == 1500
    em.record_token_budget(2200)
    assert em.context_used() == 2200


@pytest.mark.asyncio
async def test_run_emits_periodic_snapshots() -> None:
    sess = _FakeSession()
    em = StateEmitter(sess, interval_s=0.02)  # type: ignore[arg-type]
    task = asyncio.create_task(em.run())
    await asyncio.sleep(0.08)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert len(sess.enqueued) >= 3
    msg = sess.enqueued[0]
    assert msg["type"] == "state.snapshot"
    assert msg["network"]["endpoint"] == "ws://test/ws"
    assert msg["network"]["sendQueueMax"] == 256

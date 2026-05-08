"""Tests for the ping/pong heartbeat with RTT tracking."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from server.heartbeat import Heartbeat


def test_send_ping_returns_monotonic_seq() -> None:
    hb = Heartbeat()
    a = hb.send_ping()
    b = hb.send_ping()
    c = hb.send_ping()
    assert a == 0
    assert b == 1
    assert c == 2


def test_record_pong_sets_last_rtt_ms() -> None:
    hb = Heartbeat(now=lambda: 100.0)
    seq = hb.send_ping()
    assert hb.last_rtt_ms is None
    hb.now = lambda: 100.025  # 25 ms later
    hb.record_pong(seq)
    assert hb.last_rtt_ms is not None
    assert abs(hb.last_rtt_ms - 25.0) < 0.01


def test_record_pong_unknown_seq_is_ignored() -> None:
    hb = Heartbeat()
    hb.record_pong(999)
    assert hb.last_rtt_ms is None


def test_pending_eviction_after_threshold() -> None:
    hb = Heartbeat(now=lambda: 0.0, pending_ttl_s=30.0)
    seq = hb.send_ping()
    hb.now = lambda: 31.0
    hb.evict_stale()
    hb.record_pong(seq)
    assert hb.last_rtt_ms is None  # eviction ate the pending entry


def test_evict_stale_keeps_recent_pending() -> None:
    hb = Heartbeat(now=lambda: 0.0, pending_ttl_s=30.0)
    seq = hb.send_ping()
    hb.now = lambda: 5.0
    hb.evict_stale()
    hb.now = lambda: 5.010
    hb.record_pong(seq)
    assert hb.last_rtt_ms is not None
    assert abs(hb.last_rtt_ms - 5010.0) < 0.5


@pytest.mark.asyncio
async def test_run_loop_emits_pings_and_records_rtt() -> None:
    """End-to-end: a Heartbeat with a fast tick produces multiple pings; pongs feed back RTT."""
    sent: list[int] = []
    hb = Heartbeat(interval_s=0.01)

    async def emit(seq: int) -> None:
        sent.append(seq)

    task = asyncio.create_task(hb.run(emit))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert len(sent) >= 3
    # Pong the most recent ping
    hb.record_pong(sent[-1])
    assert hb.last_rtt_ms is not None

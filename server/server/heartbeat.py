"""Ping/pong heartbeat with RTT tracking.

Replaces the legacy `telemetry: heartbeat` 5-second emission. The session
emits a small `ping` JSON message; the client echoes `pong` with the same
seq; the server records the round-trip time. The most recent RTT is
exposed via `last_rtt_ms` and consumed by the state.snapshot emitter for
the Network panel's latency field.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

DEFAULT_INTERVAL_S = 5.0
DEFAULT_PENDING_TTL_S = 30.0


class Heartbeat:
    def __init__(
        self,
        *,
        interval_s: float = DEFAULT_INTERVAL_S,
        pending_ttl_s: float = DEFAULT_PENDING_TTL_S,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.interval_s = interval_s
        self.pending_ttl_s = pending_ttl_s
        self.now = now or time.monotonic
        self._next_seq = 0
        self._pending: dict[int, float] = {}
        self._last_rtt_ms: float | None = None

    @property
    def last_rtt_ms(self) -> float | None:
        return self._last_rtt_ms

    def send_ping(self) -> int:
        seq = self._next_seq
        self._next_seq += 1
        self._pending[seq] = self.now()
        return seq

    def record_pong(self, seq: int) -> None:
        sent_at = self._pending.pop(seq, None)
        if sent_at is None:
            return
        self._last_rtt_ms = (self.now() - sent_at) * 1000.0

    def evict_stale(self) -> None:
        cutoff = self.now() - self.pending_ttl_s
        stale = [s for s, t in self._pending.items() if t < cutoff]
        for s in stale:
            del self._pending[s]

    async def run(self, emit: Callable[[int], Awaitable[None]]) -> None:
        """Periodically emit pings via the supplied async callback."""
        while True:
            await asyncio.sleep(self.interval_s)
            self.evict_stale()
            seq = self.send_ping()
            await emit(seq)

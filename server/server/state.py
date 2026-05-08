"""Periodic `state.snapshot` emitter for the v2 panels.

Owned by `Session`. Runs as an asyncio task started from `Session.run()`.
Bundles system / memory / network / tasks data and emits at 1 Hz via
the session's outbound queue.

Tokens-per-minute uses a rolling 60-second window of `record_token()`
calls (one per LLM token observed). CPU load comes from `psutil` at
process scope. Context-used is updated by the session per turn.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import TYPE_CHECKING, Any

from .config import settings
from .protocol import ServerMessage
from .tasks import tasks_queue

if TYPE_CHECKING:
    from .session import Session

log = logging.getLogger(__name__)

_TOKEN_WINDOW_S = 60.0


def build_snapshot(
    *,
    load: float,
    tokens_per_min: int,
    session_id: str,
    model_name: str,
    context_used: int,
    context_max: int,
    endpoint: str,
    latency_ms: float | None,
    packets: int,
    send_queue_depth: int,
    send_queue_max: int,
    tasks: dict[str, int],
) -> dict[str, Any]:
    return ServerMessage.state_snapshot(
        system={
            "load": load,
            "tokensPerMin": tokens_per_min,
            "sessionId": session_id,
            "modelName": model_name,
        },
        memory={"contextUsed": context_used, "contextMax": context_max},
        network={
            "endpoint": endpoint,
            "latencyMs": latency_ms,
            "packets": packets,
            "sendQueueDepth": send_queue_depth,
            "sendQueueMax": send_queue_max,
        },
        tasks=tasks,
    )


class StateEmitter:
    def __init__(self, session: Session, *, interval_s: float = 1.0) -> None:
        self._session = session
        self._interval_s = interval_s
        self._token_times: deque[float] = deque()
        self._packets = 0
        self._context_used = 0

    def record_token(self) -> None:
        now = time.monotonic()
        self._token_times.append(now)
        cutoff = now - _TOKEN_WINDOW_S
        while self._token_times and self._token_times[0] < cutoff:
            self._token_times.popleft()

    def record_packet(self) -> None:
        self._packets += 1

    def record_token_budget(self, used: int) -> None:
        self._context_used = used

    def tokens_per_min(self) -> int:
        cutoff = time.monotonic() - _TOKEN_WINDOW_S
        while self._token_times and self._token_times[0] < cutoff:
            self._token_times.popleft()
        return len(self._token_times)

    def packets(self) -> int:
        return self._packets

    def context_used(self) -> int:
        return self._context_used

    def _load(self) -> float:
        try:
            import psutil

            return float(psutil.cpu_percent(interval=None))
        except ImportError:
            return 0.0

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._interval_s)
            try:
                snap = build_snapshot(
                    load=self._load(),
                    tokens_per_min=self.tokens_per_min(),
                    session_id=getattr(self._session, "session_id", "unknown"),
                    model_name=settings.model_name,
                    context_used=self._context_used,
                    context_max=settings.model_context_max,
                    endpoint=getattr(self._session, "endpoint", "ws://localhost:8000/ws"),
                    latency_ms=self._session.heartbeat.last_rtt_ms,
                    packets=self._packets,
                    send_queue_depth=getattr(self._session, "send_queue_depth", 0),
                    send_queue_max=getattr(self._session, "send_queue_max", 256),
                    tasks=tasks_queue.snapshot(),
                )
                await self._session._enqueue_json(snap)  # noqa: SLF001
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("state.snapshot emit failed")

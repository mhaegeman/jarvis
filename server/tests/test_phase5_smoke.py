"""Phase 5 end-to-end smoke test.

Covers Task 5 wiring:
- DialogManager.handle_turn calls FeedbackLogger.record_turn after llm.end.
- ProfileRefresher is scheduled via asyncio.create_task after N turns.
- state.snapshot.system.personas grows lastRefreshTs + refreshCount.
- GET /personas reflects refresher state after a refresh.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ── Minimal stubs for DialogManager tests ────────────────────────────────────


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_text(self, data: str) -> None:
        import json
        self.sent.append(json.loads(data))

    async def send_bytes(self, data: bytes) -> None:
        pass


class _ScriptedLLM:
    def __init__(self, deltas: list[str] | None = None) -> None:
        self._deltas = deltas or ["hello"]

    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> Any:
        for d in self._deltas:
            yield d


class _ScriptedDispatcher:
    def __init__(self) -> None:
        from server.dialog.types import Plan, Segment
        self._plan = Plan(
            segments=[Segment(speaker="jarvis", tier="fast", mode="chat", intent="greet")],
            rationale="just greet",
        )

    async def dispatch(self, text: str, state: Any, *, now_ts: float | None = None) -> Any:
        return self._plan


class _FakeMultiVoiceTTS:
    async def synthesize_for_speaker(
        self, text: str, audio_id: str, *, speaker: str
    ) -> Any:
        if False:
            yield b""


# ── Test 1: FeedbackLogger gets a row after handle_turn ──────────────────────


@pytest.mark.asyncio
async def test_handle_turn_writes_dispatch_log_row(tmp_path: Path) -> None:
    """After handle_turn, dispatch_log has one row for the turn."""
    import aiosqlite

    from server.dialog.feedback import FeedbackLogger
    from server.dialog.manager import DialogManager
    from server.memory.store import MemoryStore
    from server.personas.registry import PersonaRegistry

    db_path = str(tmp_path / "memory.db")
    store = await MemoryStore.open(db_path)
    try:
        registry = PersonaRegistry.build(
            warmth="subtle",
            anthropic_available=True,
            openai_available=True,
            codex_binary=None,
            codex_workdir=None,
        )
        feedback = FeedbackLogger(db_path)
        mgr = DialogManager(
            registry=registry,
            dispatcher=_ScriptedDispatcher(),
            llm_factory=lambda persona, mid: _ScriptedLLM(),
            tts=_FakeMultiVoiceTTS(),
            feedback=feedback,
        )

        ws = _FakeWS()
        await mgr.handle_turn(ws, text="hello jarvis", history=[])

        # Give asyncio a tick to process anything pending
        await asyncio.sleep(0)

        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute("SELECT turn_id, utterance FROM dispatch_log")
            rows = await cur.fetchall()

        assert len(rows) == 1
        assert rows[0][1] == "hello jarvis"
    finally:
        await store.close()


# ── Test 2: Turn counter triggers refresh ────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_scheduled_after_n_turns(tmp_path: Path) -> None:
    """After refresh_every turns, asyncio.create_task fires the refresher."""
    from server.dialog.feedback import FeedbackLogger
    from server.dialog.manager import DialogManager
    from server.memory.store import MemoryStore
    from server.personas.registry import PersonaRegistry

    db_path = str(tmp_path / "memory.db")
    store = await MemoryStore.open(db_path)
    try:
        registry = PersonaRegistry.build(
            warmth="subtle",
            anthropic_available=True,
            openai_available=True,
            codex_binary=None,
            codex_workdir=None,
        )
        feedback = FeedbackLogger(db_path)

        refresh_calls: list[int] = []

        class _FakeRefresher:
            async def refresh(self) -> dict[str, Any]:
                refresh_calls.append(1)
                return {"status": "ok", "summary": "test"}

        refresher = _FakeRefresher()
        mgr = DialogManager(
            registry=registry,
            dispatcher=_ScriptedDispatcher(),
            llm_factory=lambda persona, mid: _ScriptedLLM(),
            tts=_FakeMultiVoiceTTS(),
            feedback=feedback,
            refresher=refresher,
            refresh_every=3,
        )

        ws = _FakeWS()
        for _ in range(3):
            await mgr.handle_turn(ws, text="test", history=[])

        # Let the asyncio.create_task-ed refresh run
        await asyncio.sleep(0.05)

        assert len(refresh_calls) >= 1
    finally:
        await store.close()


# ── Test 3: state.snapshot includes personas keys ─────────────────────────────


def test_build_snapshot_includes_personas() -> None:
    """build_snapshot accepts personas kwarg and includes it in system."""
    from server.state import build_snapshot

    snap = build_snapshot(
        load=0.0,
        tokens_per_min=0,
        session_id="s1",
        model_name="mock",
        context_used=0,
        context_max=200000,
        endpoint="ws://localhost/ws",
        latency_ms=None,
        packets=0,
        send_queue_depth=0,
        send_queue_max=256,
        tasks={},
        personas={"lastRefreshTs": 1234567890.0, "refreshCount": 2},
    )
    assert snap["system"]["personas"]["lastRefreshTs"] == 1234567890.0
    assert snap["system"]["personas"]["refreshCount"] == 2


# ── Test 4: GET /personas reflects refresher after manual refresh ─────────────


@pytest.mark.asyncio
async def test_personas_endpoint_shows_refresh_ts_after_refresh(tmp_path: Path) -> None:
    """After calling refresher._persist(), GET /personas shows the ts."""
    from fastapi.testclient import TestClient

    from server.dialog.feedback import FeedbackLogger
    from server.dialog.profile_refresher import ProfileRefresher
    from server.memory.store import MemoryStore
    from server.personas.registry import PersonaRegistry

    db_path = str(tmp_path / "memory.db")
    store = await MemoryStore.open(db_path)
    try:
        feedback = FeedbackLogger(db_path)
        registry = PersonaRegistry.build(
            warmth="subtle",
            anthropic_available=True,
            openai_available=False,  # only jarvis
            codex_binary=None,
            codex_workdir=None,
        )
        refresher = ProfileRefresher(
            registry=registry,
            feedback=feedback,
            client=None,  # not calling LLM in this test
            db_path=db_path,
        )
        # Manually call _persist to simulate a refresh having happened
        await refresher._persist("jarvis", "updated jarvis profile text here ok")

        from fastapi.testclient import TestClient

        import server.main as main_mod

        with (
            patch.object(main_mod, "_persona_registry", registry),
            patch.object(main_mod, "_profile_refresher", refresher),
        ):
            client = TestClient(main_mod.app, raise_server_exceptions=False)
            resp = client.get("/personas")

        assert resp.status_code == 200
        data = resp.json()
        assert "jarvis" in data
        assert data["jarvis"]["lastRefreshTs"] is not None
        assert data["jarvis"]["refreshCount"] == 1
    finally:
        await store.close()

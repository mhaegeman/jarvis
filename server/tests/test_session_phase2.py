"""Session integration with the DialogManager (flag on)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest


class _FakeWSAdapter:
    def __init__(self) -> None:
        import asyncio
        self.sent: list[dict[str, Any]] = []
        self.sent_bytes: list[bytes] = []
        self._inbox: asyncio.Queue[Any] = asyncio.Queue()

    async def send_text(self, data: str) -> None:
        import json
        self.sent.append(json.loads(data))

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def receive(self) -> Any:
        return await self._inbox.get()

    def push_text(self, msg: dict[str, Any]) -> None:
        import json
        self._inbox.put_nowait({"type": "websocket.receive", "text": json.dumps(msg)})

    def push_disconnect(self) -> None:
        self._inbox.put_nowait({"type": "websocket.disconnect"})


class _ScriptedLLM:
    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]:
        for d in ["Hi.", " Max."]:
            yield d


class _FakeMultiVoiceTTS:
    def sample_rate(self) -> int:
        return 24000

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        if False:
            yield b""

    async def synthesize_for_speaker(
        self,
        text: str,
        audio_id: str,
        *,
        speaker: str,
    ) -> AsyncIterator[bytes]:
        if False:
            yield b""


class _ScriptedDispatcher:
    def __init__(self, plan) -> None:  # type: ignore[no-untyped-def]
        self._plan = plan

    async def dispatch(self, text, state, *, now_ts=None):  # type: ignore[no-untyped-def]
        return self._plan


async def _wait_for_type(ws: _FakeWSAdapter, msg_type: str, wait: float = 3.0) -> None:
    """Poll until a message of the given type appears in ws.sent."""
    import asyncio
    deadline = asyncio.get_event_loop().time() + wait
    while asyncio.get_event_loop().time() < deadline:
        if any(m["type"] == msg_type for m in ws.sent):
            return
        await asyncio.sleep(0.02)
    seen = [m["type"] for m in ws.sent]
    raise TimeoutError(f"never saw {msg_type!r}; saw: {seen}")


@pytest.mark.asyncio
async def test_session_delegates_to_dialog_manager_when_configured() -> None:
    """When a DialogManager is passed to Session, text turns produce
    dispatch.plan + speaker-tagged llm.token events on the WS."""
    import asyncio

    from server.dialog.manager import DialogManager
    from server.dialog.types import Plan, Segment
    from server.personas.registry import PersonaRegistry

    plan = Plan(
        segments=[Segment(speaker="pepper", tier="fast", mode="chat", intent="hi")],
        rationale="trivial",
    )
    mgr = DialogManager(
        registry=PersonaRegistry.build(
            warmth="subtle",
            anthropic_available=True,
            openai_available=True,
            codex_binary=None,
            codex_workdir=None,
        ),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: _ScriptedLLM(),
        tts=_FakeMultiVoiceTTS(),
    )
    ws = _FakeWSAdapter()
    sess = _build_session(ws=ws, dialog_manager=mgr)
    # Run the session concurrently so the turn task can complete before disconnect.
    task = asyncio.create_task(sess.run())
    ws.push_text({"type": "text", "content": "Pepper, hi"})
    await _wait_for_type(ws, "llm.end")
    ws.push_disconnect()
    await task
    types = [m["type"] for m in ws.sent]
    assert "dispatch.plan" in types
    speaker_tokens = [m for m in ws.sent if m["type"] == "llm.token"]
    assert speaker_tokens
    assert all(t.get("speaker") == "pepper" for t in speaker_tokens)


def _build_session(*, ws, dialog_manager):
    """Helper — constructs a Session with the existing fakes for STT/LLM/TTS
    plus the new dialog_manager kwarg. Adapt args to the actual Session
    constructor's signature."""
    from server.pipelines.mock_llm import MockLLM
    from server.pipelines.mock_stt import MockSTT
    from server.pipelines.mock_tts import MockTTS
    from server.session import Session
    # The exact kwargs depend on Session's signature — adapt as needed.
    return Session(
        ws=ws,
        stt=MockSTT(),
        llm=MockLLM(),
        tts=MockTTS(),
        memory=None,
        summarizer=None,
        resume_window_minutes=30,
        recent_summary_refresh_turns=5,
        recent_summary_window=20,
        facts_cap=50,
        dialog_manager=dialog_manager,  # NEW kwarg added in this task
    )

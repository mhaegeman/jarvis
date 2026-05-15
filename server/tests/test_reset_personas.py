"""Tests for the /reset personas text trigger in Session.

Phase 5 Task 4: `/reset personas` is detected before dispatch,
runs refresher.reset(), emits a spoken tts.sentence confirmation,
and returns without touching the DialogManager.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

# ── Minimal stubs ────────────────────────────────────────────────────────────


class _FakeWS:
    def __init__(self) -> None:
        self.sent_texts: list[str] = []
        self.sent_bytes: list[bytes] = []

    async def send_text(self, data: str) -> None:
        self.sent_texts.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def receive(self) -> dict[str, Any]:
        # Simulate disconnect immediately
        return {"type": "websocket.disconnect"}


class _FakeSTT:
    async def final(self, _: Any) -> str:
        return ""

    async def partials(self, _: Any) -> AsyncIterator[str]:
        if False:
            yield ""


class _FakeLLM:
    async def stream(  # type: ignore[return]
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[str]:
        if False:
            yield ""


class _FakeTTS:
    async def synthesize(  # type: ignore[return]
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[bytes]:
        if False:
            yield b""


class _FakeRefresher:
    def __init__(self) -> None:
        self.reset_called = 0

    async def reset(self) -> None:
        self.reset_called += 1


class _FakeDialogManager:
    def __init__(self) -> None:
        self.handle_turn_called = 0

    async def handle_turn(self, *args: Any, **kwargs: Any) -> None:
        self.handle_turn_called += 1

    def last_assistant_text(self) -> str:
        return ""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_session(
    *,
    refresher: _FakeRefresher | None = None,
    dialog_manager: _FakeDialogManager | None = None,
) -> Any:
    """Build a Session with minimal stubs."""
    from server.session import Session

    ws = _FakeWS()
    session = Session(
        ws=ws,
        stt=_FakeLLM(),  # type: ignore[arg-type]
        llm=_FakeLLM(),  # type: ignore[arg-type]
        tts=_FakeTTS(),  # type: ignore[arg-type]
        dialog_manager=dialog_manager,  # type: ignore[arg-type]
        refresher=refresher,  # type: ignore[arg-type]
    )
    return session, ws


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_personas_calls_refresher_reset() -> None:
    """'/reset personas' triggers refresher.reset() exactly once."""
    refresher = _FakeRefresher()
    session, ws = _make_session(refresher=refresher)

    await session._do_llm_and_tts("/reset personas")

    assert refresher.reset_called == 1


@pytest.mark.asyncio
async def test_reset_personas_case_insensitive() -> None:
    """Text matching is case-insensitive."""
    refresher = _FakeRefresher()
    session, ws = _make_session(refresher=refresher)

    await session._do_llm_and_tts("/RESET PERSONAS")
    assert refresher.reset_called == 1


@pytest.mark.asyncio
async def test_reset_personas_strips_whitespace() -> None:
    """Leading/trailing whitespace is stripped before matching."""
    refresher = _FakeRefresher()
    session, ws = _make_session(refresher=refresher)

    await session._do_llm_and_tts("  /reset personas  ")
    assert refresher.reset_called == 1


@pytest.mark.asyncio
async def test_reset_personas_emits_tts_sentence() -> None:
    """A tts.sentence event is emitted as the spoken confirmation."""
    import json

    refresher = _FakeRefresher()
    session, ws = _make_session(refresher=refresher)

    # Start the sender loop so enqueued messages flow to ws.send_text().
    sender_task = asyncio.create_task(session._sender_loop())
    try:
        await session._do_llm_and_tts("/reset personas")
        # Give the sender loop a tick to drain the queue.
        await asyncio.sleep(0)
    finally:
        sender_task.cancel()
        import contextlib
        with contextlib.suppress(asyncio.CancelledError):
            await sender_task

    tts_sentences = [
        json.loads(t)
        for t in ws.sent_texts
        if "tts.sentence" in t
    ]
    assert len(tts_sentences) >= 1
    # The confirmation text should mention "reset" or "personas"
    # tts.sentence format: {"type": "tts.sentence", "text": "...", "audioId": "..."}
    confirmation_text = tts_sentences[0].get("text", "")
    assert "reset" in confirmation_text.lower() or "personas" in confirmation_text.lower()


@pytest.mark.asyncio
async def test_reset_personas_skips_dialog_manager() -> None:
    """/reset personas must NOT call DialogManager.handle_turn."""
    refresher = _FakeRefresher()
    dialog_manager = _FakeDialogManager()
    session, ws = _make_session(refresher=refresher, dialog_manager=dialog_manager)

    await session._do_llm_and_tts("/reset personas")

    assert dialog_manager.handle_turn_called == 0


@pytest.mark.asyncio
async def test_non_reset_command_not_intercepted() -> None:
    """Other text is NOT intercepted by the /reset personas guard."""
    refresher = _FakeRefresher()
    session, ws = _make_session(refresher=refresher)

    # This should NOT trigger reset (no exception, just goes to normal path)
    # Without a dialog manager, it falls through to the legacy LLM path
    # which tries to stream from _FakeLLM (an empty generator) — that's fine.
    await session._do_llm_and_tts("hello jarvis")

    assert refresher.reset_called == 0


@pytest.mark.asyncio
async def test_reset_personas_no_refresher_is_noop() -> None:
    """When refresher is None, /reset personas falls through to the normal path."""
    session, ws = _make_session(refresher=None)

    # Should not raise — the guard is a no-op when refresher is None
    await session._do_llm_and_tts("/reset personas")
    # No reset — no refresher to call

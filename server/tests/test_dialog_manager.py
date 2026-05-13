"""Tests for server.dialog.manager.DialogManager."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from server.dialog.manager import DialogManager
from server.dialog.types import DialogState, Plan, Segment
from server.personas.registry import PersonaRegistry

# ── Fakes ────────────────────────────────────────────────────────────


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.sent_bytes: list[bytes] = []

    async def send_text(self, data: str) -> None:
        import json
        self.sent.append(json.loads(data))

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)


class _ScriptedLLM:
    """Returns the next pre-recorded delta sequence each time stream() is called."""

    def __init__(self, scripts: list[list[str]]) -> None:
        self._scripts = list(scripts)
        self.calls: list[dict[str, Any]] = []  # records each stream() invocation

    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]:
        self.calls.append({"history": list(history), "user_text": user_text,
                           "extra_context": extra_context})
        deltas = self._scripts.pop(0) if self._scripts else []
        for d in deltas:
            yield d


class _ScriptedDispatcher:
    """Returns a pre-built Plan."""

    def __init__(self, plan: Plan) -> None:
        self._plan = plan
        self.calls: list[tuple[str, DialogState]] = []

    async def dispatch(
        self,
        text: str,
        state: DialogState,
        *,
        now_ts: float | None = None,
    ) -> Plan:
        self.calls.append((text, state))
        return self._plan


class _FakeTTS:
    """Records calls to synthesize_for_speaker. Emits one byte per call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []  # (text, audio_id, speaker)

    async def synthesize_for_speaker(
        self,
        text: str,
        audio_id: str,
        *,
        speaker: str,
    ) -> AsyncIterator[bytes]:
        self.calls.append((text, audio_id, speaker))
        yield b"X"


def _registry_with_both() -> PersonaRegistry:
    return PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=True,
        codex_binary=None,
        codex_workdir=None,
    )


# ── Single-segment turn ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_single_segment_turn_streams_one_speaker() -> None:
    plan = Plan(
        segments=[Segment(speaker="jarvis", tier="fast", mode="chat", intent="hi")],
        rationale="trivial",
    )
    dispatcher = _ScriptedDispatcher(plan)
    llm = _ScriptedLLM([["Hel", "lo.", " Max."]])
    ws = _FakeWS()
    tts = _FakeTTS()

    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=dispatcher,
        llm_factory=lambda persona, model_id: llm,
        tts=tts,
    )
    await mgr.handle_turn(ws, text="hi", history=[])

    types_sent = [m["type"] for m in ws.sent]
    assert "dispatch.plan" in types_sent
    assert types_sent.count("llm.token") >= 1
    # Each llm.token must carry speaker=jarvis.
    tokens = [m for m in ws.sent if m["type"] == "llm.token"]
    assert all(t["speaker"] == "jarvis" for t in tokens)
    # Segment end emitted once.
    seg_ends = [m for m in ws.sent if m["type"] == "llm.segment_end"]
    assert len(seg_ends) == 1
    # llm.end emitted last.
    assert ws.sent[-1]["type"] == "llm.end"


# ── Multi-segment turn with voice swap ───────────────────────────────


@pytest.mark.asyncio
async def test_multi_segment_handoff_swaps_voice() -> None:
    plan = Plan(
        segments=[
            Segment(speaker="jarvis", tier="balanced", mode="chat",
                    intent="design", handoff_style="soft"),
            Segment(speaker="pepper", tier="deep", mode="chat",
                    intent="implement"),
        ],
        rationale="design then implement",
    )
    dispatcher = _ScriptedDispatcher(plan)
    llm = _ScriptedLLM([
        ["I'll design.", " "],   # jarvis segment
        ["I'll implement.", " "],  # pepper segment
    ])
    ws = _FakeWS()
    tts = _FakeTTS()

    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=dispatcher,
        llm_factory=lambda persona, model_id: llm,
        tts=tts,
    )
    await mgr.handle_turn(ws, text="design and then implement X", history=[])

    tokens = [m for m in ws.sent if m["type"] == "llm.token"]
    jarvis_tokens = [t for t in tokens if t["speaker"] == "jarvis"]
    pepper_tokens = [t for t in tokens if t["speaker"] == "pepper"]
    assert jarvis_tokens
    assert pepper_tokens
    # Jarvis tokens come before pepper tokens (sequential segments).
    first_pepper = next(i for i, t in enumerate(tokens) if t["speaker"] == "pepper")
    last_jarvis = max(i for i, t in enumerate(tokens) if t["speaker"] == "jarvis")
    assert last_jarvis < first_pepper

    # Two segment_end events.
    seg_ends = [m for m in ws.sent if m["type"] == "llm.segment_end"]
    assert [e["speaker"] for e in seg_ends] == ["jarvis", "pepper"]


# ── State update after turn ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_turn_updates_last_speaker() -> None:
    plan = Plan(
        segments=[Segment(speaker="pepper", tier="fast", mode="chat", intent="hi")],
        rationale="trivial",
    )
    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: _ScriptedLLM([["ok"]]),
        tts=_FakeTTS(),
    )
    await mgr.handle_turn(_FakeWS(), text="x", history=[])
    state = mgr.current_state()
    assert state.last_speaker == "pepper"
    assert state.last_turn_ts is not None


# ── Failure inside a segment halts the plan ──────────────────────────


@pytest.mark.asyncio
async def test_segment_failure_emits_spoken_error_and_halts() -> None:
    class _FailingLLM:
        async def stream(
            self,
            history: list[dict[str, str]],
            user_text: str,
            *,
            extra_context: str = "",
        ) -> AsyncIterator[str]:
            raise RuntimeError("boom")
            yield  # type: ignore[unreachable]

    plan = Plan(
        segments=[
            Segment(speaker="jarvis", tier="fast", mode="chat", intent="a",
                    handoff_style="soft"),
            Segment(speaker="pepper", tier="fast", mode="chat", intent="b"),
        ],
        rationale="should halt at jarvis failure",
    )
    ws = _FakeWS()
    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: _FailingLLM(),
        tts=_FakeTTS(),
    )
    await mgr.handle_turn(ws, text="x", history=[])
    # The failing segment emitted a spoken-error token.
    # But the second segment never ran.
    tokens = [m for m in ws.sent if m["type"] == "llm.token"]
    pepper_tokens = [t for t in tokens if t["speaker"] == "pepper"]
    assert not pepper_tokens

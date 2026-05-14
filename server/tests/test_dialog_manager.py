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


# ── Regression tests for Codex review on PR #32 ──────────────────────


@pytest.mark.asyncio
async def test_last_assistant_text_captures_streamed_output() -> None:
    """Session reads `last_assistant_text()` to append to its history.
    Must be the concatenated stream of every successfully-streamed segment.
    """
    plan = Plan(
        segments=[
            Segment(speaker="jarvis", tier="balanced", mode="chat",
                    intent="design", handoff_style="soft"),
            Segment(speaker="pepper", tier="deep", mode="chat", intent="implement"),
        ],
        rationale="design then implement",
    )
    # Share one _ScriptedLLM across both segments so each pop() consumes
    # the next script entry (the factory lambda returns the same instance).
    shared_llm = _ScriptedLLM([
        ["Design ", "first."],
        ["Then ", "implement."],
    ])
    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: shared_llm,
        tts=_FakeTTS(),
    )
    await mgr.handle_turn(_FakeWS(), text="design and then implement X", history=[])
    assert mgr.last_assistant_text() == "Design first.Then implement."


@pytest.mark.asyncio
async def test_last_assistant_text_resets_per_turn() -> None:
    """Each new turn replaces the buffer — no leakage from prior turn."""
    plan1 = Plan(
        segments=[Segment(speaker="jarvis", tier="fast", mode="chat", intent="a")],
        rationale="t1",
    )
    plan2 = Plan(
        segments=[Segment(speaker="pepper", tier="fast", mode="chat", intent="b")],
        rationale="t2",
    )

    class _DualDispatcher:
        def __init__(self) -> None:
            self._plans = [plan1, plan2]
            self.calls = 0

        async def dispatch(self, text, state, *, now_ts=None):  # type: ignore[no-untyped-def]
            p = self._plans[self.calls]
            self.calls += 1
            return p

    shared_llm = _ScriptedLLM([["first"], ["second"]])
    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_DualDispatcher(),
        llm_factory=lambda persona, model_id: shared_llm,
        tts=_FakeTTS(),
    )
    await mgr.handle_turn(_FakeWS(), text="x", history=[])
    assert mgr.last_assistant_text() == "first"
    await mgr.handle_turn(_FakeWS(), text="y", history=[])
    # Second turn replaces buffer, not appends.
    assert mgr.last_assistant_text() == "second"


@pytest.mark.asyncio
async def test_sticky_speaker_reflects_actual_streamer_not_planned_tail() -> None:
    """If the plan halts at segment 0 (e.g. unavailable persona at segment 1),
    sticky speaker must be the persona who actually streamed (segment 0's
    speaker), not the planned last segment's speaker.
    """
    # Construct a registry where Pepper is unavailable, so segment 1 will be
    # skipped. Sticky must end up on jarvis (who DID stream), not pepper.
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=False,  # Pepper unavailable
        codex_binary=None,
        codex_workdir=None,
    )
    plan = Plan(
        segments=[
            Segment(speaker="jarvis", tier="balanced", mode="chat",
                    intent="design", handoff_style="soft"),
            Segment(speaker="pepper", tier="deep", mode="chat", intent="implement"),
        ],
        rationale="planned handoff but pepper not registered",
    )
    mgr = DialogManager(
        registry=reg,
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: _ScriptedLLM([["ok"]]),
        tts=_FakeTTS(),
    )
    await mgr.handle_turn(_FakeWS(), text="x", history=[])
    assert mgr.current_state().last_speaker == "jarvis"


@pytest.mark.asyncio
async def test_sticky_speaker_unset_when_no_segment_streams() -> None:
    """If NO segment produces output (all halt), sticky speaker keeps its
    prior value rather than being mispriied to a planned-but-not-run speaker.
    """
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=False,  # Jarvis unavailable
        openai_available=False,     # Pepper unavailable
        codex_binary=None,
        codex_workdir=None,
    )
    plan = Plan(
        segments=[
            Segment(speaker="jarvis", tier="fast", mode="chat", intent="a"),
        ],
        rationale="all unavailable",
    )
    mgr = DialogManager(
        registry=reg,
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: _ScriptedLLM([["x"]]),
        tts=_FakeTTS(),
    )
    await mgr.handle_turn(_FakeWS(), text="x", history=[])
    # No segment ran → sticky stays at its default (None).
    assert mgr.current_state().last_speaker is None

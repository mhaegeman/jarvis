"""DialogManager dispatch when mode=codex_agent."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from server.dialog.manager import DialogManager
from server.dialog.types import Plan, Segment
from server.personas.registry import PersonaRegistry


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.sent_bytes: list[bytes] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)


class _ScriptedDispatcher:
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    async def dispatch(self, text, state, *, now_ts=None):  # type: ignore[no-untyped-def]
        return self._plan


class _FakeTTS:
    async def synthesize_for_speaker(self, text, audio_id, *, speaker):  # type: ignore[no-untyped-def]
        yield b""


class _ScriptedAgent:
    """Records calls + emits scripted narration sentences + WS events."""

    def __init__(self, narration: list[str], end_status: str = "ok") -> None:
        self._narration = narration
        self._end_status = end_status
        self.runs: list[dict[str, Any]] = []

    async def run(
        self, *, ws, task: str, run_id: str, speaker: str = "pepper",
    ) -> AsyncIterator[str]:
        self.runs.append({"task": task, "run_id": run_id, "speaker": speaker})
        # Emit a couple of WS events directly so the manager can see them.
        import server.protocol as proto
        await ws.send_text(proto.encode_server(proto.ServerMessage.agent_start(
            speaker=speaker, task=task, run_id=run_id,
        )))
        for s in self._narration:
            yield s
        await ws.send_text(proto.encode_server(proto.ServerMessage.agent_end(
            run_id=run_id, status=self._end_status, summary="done",
        )))

    async def cancel(self, run_id: str) -> None:
        pass


def _registry_with_both() -> PersonaRegistry:
    return PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=True,
        codex_binary=None,
        codex_workdir=None,
    )


# ── Codex segment dispatches to the agent ─────────────────────────────


@pytest.mark.asyncio
async def test_codex_agent_segment_emits_agent_events() -> None:
    plan = Plan(
        segments=[Segment(
            speaker="pepper", tier="deep", mode="codex_agent",
            intent="refactor X",
        )],
        rationale="codex segment",
    )
    agent = _ScriptedAgent(narration=["Editing foo.py.", "Done."])
    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: None,  # not called in codex path
        tts=_FakeTTS(),
        codex_agent=agent,
    )
    ws = _FakeWS()
    await mgr.handle_turn(ws, text="Pepper, refactor X", history=[])

    types = [m["type"] for m in ws.sent]
    assert "agent.start" in types
    assert "agent.end" in types
    # Narration sentences flowed through tts.sentence (speaker=pepper).
    tts_msgs = [m for m in ws.sent if m["type"] == "tts.sentence"]
    assert all(m["speaker"] == "pepper" for m in tts_msgs)
    assert any("Editing" in m["text"] for m in tts_msgs)


@pytest.mark.asyncio
async def test_codex_segment_falls_back_to_chat_when_no_agent() -> None:
    """Without a CodexAgent configured (binary missing), mode=codex_agent
    segments fall back to chat mode with a logged warning (Phase 2 behaviour)."""
    plan = Plan(
        segments=[Segment(
            speaker="pepper", tier="deep", mode="codex_agent",
            intent="rename X to Y",
        )],
        rationale="codex segment but no agent",
    )

    class _ScriptedLLM:
        async def stream(self, history, user_text, *, extra_context=""):  # type: ignore[no-untyped-def]
            yield "Falling back to chat."

    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: _ScriptedLLM(),
        tts=_FakeTTS(),
        codex_agent=None,  # explicit
    )
    ws = _FakeWS()
    await mgr.handle_turn(ws, text="Pepper, rename X to Y", history=[])

    # No agent events emitted.
    assert not any(m["type"].startswith("agent.") for m in ws.sent)
    # Chat path ran instead: llm.token + llm.segment_end + llm.end.
    tokens = [m for m in ws.sent if m["type"] == "llm.token"]
    assert tokens


@pytest.mark.asyncio
async def test_codex_segment_assistant_text_includes_narration() -> None:
    """The agent's narration sentences must end up in last_assistant_text()
    so Session can keep the history coherent."""
    plan = Plan(
        segments=[Segment(
            speaker="pepper", tier="deep", mode="codex_agent",
            intent="rename",
        )],
        rationale="codex",
    )
    agent = _ScriptedAgent(narration=["Editing foo.", "Rename complete."])
    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: None,
        tts=_FakeTTS(),
        codex_agent=agent,
    )
    await mgr.handle_turn(_FakeWS(), text="Pepper, rename X", history=[])
    text = mgr.last_assistant_text()
    assert "Editing foo." in text
    assert "Rename complete." in text


@pytest.mark.asyncio
async def test_codex_segment_jarvis_speaker_does_not_dispatch_to_agent() -> None:
    """Per spec §5.3.4: mode=codex_agent is only for Pepper. If the
    dispatcher ever emits a Jarvis codex_agent segment (it shouldn't, but
    the type system allows it), the manager treats it as chat."""
    plan = Plan(
        segments=[Segment(
            speaker="jarvis", tier="fast", mode="codex_agent",
            intent="bad plan",
        )],
        rationale="should not dispatch to agent",
    )
    agent = _ScriptedAgent(narration=["should not run"])

    class _ScriptedLLM:
        async def stream(self, history, user_text, *, extra_context=""):  # type: ignore[no-untyped-def]
            yield "Chat instead."

    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: _ScriptedLLM(),
        tts=_FakeTTS(),
        codex_agent=agent,
    )
    ws = _FakeWS()
    await mgr.handle_turn(ws, text="x", history=[])
    # No agent events; chat ran instead.
    assert not any(m["type"].startswith("agent.") for m in ws.sent)
    assert not agent.runs

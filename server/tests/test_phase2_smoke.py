"""Phase 2 smoke — DialogManager + Session compose end-to-end with mocks.

Doesn't touch the network; uses fake clients. Confirms the WS message
sequence for a single-segment turn and a multi-segment handoff turn.
"""

from __future__ import annotations

import pytest

from server.dialog.manager import DialogManager
from server.dialog.types import Plan, Segment
from server.personas.registry import PersonaRegistry


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.bytes_chunks: list[bytes] = []

    async def send_text(self, data: str) -> None:
        import json
        self.sent.append(json.loads(data))

    async def send_bytes(self, data: bytes) -> None:
        self.bytes_chunks.append(data)


class _ScriptedLLM:
    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas

    async def stream(self, history, user_text, *, extra_context=""):  # type: ignore[no-untyped-def]
        for d in self._deltas:
            yield d


class _ScriptedDispatcher:
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    async def dispatch(self, text, state, *, now_ts=None):  # type: ignore[no-untyped-def]
        return self._plan


class _FakeMultiVoiceTTS:
    async def synthesize_for_speaker(self, text, audio_id, *, speaker):  # type: ignore[no-untyped-def]
        yield b""


@pytest.mark.asyncio
async def test_phase2_single_segment_smoke() -> None:
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=True,
        codex_binary=None,
        codex_workdir=None,
    )
    plan = Plan(
        segments=[Segment(speaker="pepper", tier="fast", mode="chat", intent="hi")],
        rationale="pepper greets",
    )
    mgr = DialogManager(
        registry=reg,
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, mid: _ScriptedLLM(["Hi.", " Max."]),
        tts=_FakeMultiVoiceTTS(),
    )
    ws = _FakeWS()
    await mgr.handle_turn(ws, text="Pepper, hi", history=[])

    types = [m["type"] for m in ws.sent]
    assert types[0] == "dispatch.plan"
    assert "llm.token" in types
    assert any(m.get("speaker") == "pepper" for m in ws.sent if m["type"] == "llm.token")
    assert types[-1] == "llm.end"


@pytest.mark.asyncio
async def test_phase2_handoff_smoke() -> None:
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=True,
        codex_binary=None,
        codex_workdir=None,
    )
    plan = Plan(
        segments=[
            Segment(speaker="jarvis", tier="balanced", mode="chat",
                    intent="design", handoff_style="soft"),
            Segment(speaker="pepper", tier="deep", mode="chat", intent="implement"),
        ],
        rationale="design then implement",
    )
    mgr = DialogManager(
        registry=reg,
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, mid: _ScriptedLLM(["ok."]),
        tts=_FakeMultiVoiceTTS(),
    )
    ws = _FakeWS()
    await mgr.handle_turn(ws, text="design and then implement X", history=[])

    seg_ends = [m for m in ws.sent if m["type"] == "llm.segment_end"]
    assert [e["speaker"] for e in seg_ends] == ["jarvis", "pepper"]


@pytest.mark.asyncio
async def test_phase2_dormant_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same regression guard as Phase 1, extended to new Phase 2 modules."""
    import importlib
    import sys

    monkeypatch.setenv("JARVIS_PERSONAS_ENABLED", "false")
    import server.config as cfg
    importlib.reload(cfg)

    for mod in [
        "server.dialog.manager",
        "server.dialog.dispatcher",
        "server.pipelines.multi_voice_tts",
        "server.personas.registry",
        "server.pipelines.openai_llm",
    ]:
        sys.modules.pop(mod, None)

    importlib.import_module("server.main")

    # None of the Phase 2 modules should be eagerly imported.
    for mod in [
        "server.dialog.manager",
        "server.pipelines.multi_voice_tts",
    ]:
        assert mod not in sys.modules, f"{mod} was auto-imported with the flag off"

# Multi-model support — Phase 2 (Dialog manager + chat-only multi-persona) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Jarvis + Pepper into the Session via a new `DialogManager`. With `JARVIS_PERSONAS_ENABLED=true` and both API keys, you can talk to either colleague by name, hand off mid-turn, and hear voice swaps. No Codex agent yet — chat only.

**Architecture:** New `DialogManager` (`dialog/manager.py`) owns the per-turn flow: cheap LLM dispatcher → segment-by-segment streaming → voice swaps → outcome recording. A new `MultiVoiceTTS` wrapper holds one `EdgeTTS` instance per voice and routes synthesis by speaker. The WS protocol grows optional `speaker` / `segmentIdx` fields and two new server messages (`dispatch.plan`, `llm.segment_end`). With the flag off, the existing single-Jarvis Session path is unchanged.

**Tech Stack:** Python 3.12, `anthropic>=0.40` (Dispatcher uses haiku via tool-use for structured output), `openai>=1.55,<2.0` (Pepper chat), pydantic v2 (Plan schema validation), FastAPI / Starlette WS.

**Spec:** `docs/superpowers/specs/2026-05-13-multi-model-support-design.md` — read §3 (per-turn flow), §5 (Dispatcher), §6 (segment execution), §9 (Protocol).

**Branch:** `claude/multi-model-support-phase-2` (already checked out off `main` @ `8c11c6a`).

**Working directory:** `server/` for all `pytest` commands. **Run tests via `python -m pytest`** (the bare `pytest` binary in this env is a separate uv install that lacks fastapi).

---

## Phase 1 → Phase 2 decision log

These are the concrete decisions made during Phase 1 that downstream phases need to know about. Carrying them forward intact (spec §11.1):

| # | Decision | Implication for Phase 2 |
|---|---|---|
| 1 | `python -m pytest` (system Python at `/usr/local/bin/python`) is the only pytest that sees the deps. Bare `pytest` errors with `ModuleNotFoundError: fastapi`. | Every test command in this plan uses `python -m pytest`. |
| 2 | `PersonaId = Literal["jarvis", "pepper"]` is defined in three places (`dialog/types.py`, `personas/models.py`, `personas/registry.py`). Structurally identical; mypy treats them as the same type. | Phase 2 modules import `PersonaId` from `dialog.types` (single source). Don't redeclare it. |
| 3 | Mutate-and-validate pattern: `type(p).model_validate({**p.model_dump(), field: new})`, **not** `p.model_copy(update={...})` (pydantic v2 skips validators on copy-update). | Any "edit one field" operation in Phase 2 (e.g. Outcome updates) uses the validate pattern. |
| 4 | Slash-prefix matching is case-folded in `RuleBasedDispatcher._detect_slash` and both `parse_prefix` functions (`claude_llm.py`, `openai_llm.py`). | The new `LLMBackedDispatcher` lowercases too. Phase 2 may extract a shared `_normalize_slash` helper if a third caller appears. |
| 5 | `OpenAILLM.stream` injects `extra_context` as a **separate `system` message** (idiomatic for Chat Completions API). `ClaudeLLM.stream` concatenates onto the system string (Anthropic only accepts one system). | `DialogManager` passes `extra_context` uniformly; each backend handles its own materialization. Don't try to unify the wire format. |
| 6 | `EdgeTTS` voice is fixed at construction time. Phase 2 Unit 3 wraps multiple instances behind a single facade (`MultiVoiceTTS`) instead of changing the `TTS` ABC — keeps the existing factory `_build_tts()` and tests intact. | New file `pipelines/multi_voice_tts.py`. The wrapper itself implements `TTS` so Session can stay generic, plus a `synthesize_for_speaker(text, audio_id, speaker)` extension for the Phase 2 path. |
| 7 | Dormancy regression guard (`tests/test_phase1_smoke.py::test_phase1_dormant_when_flag_off`) confirms `server.dialog.*`, `server.personas.*`, `server.pipelines.openai_llm` are not auto-imported by `main.py` when `JARVIS_PERSONAS_ENABLED=false`. | Phase 2 must keep this green. New modules (`dialog/manager.py`, `pipelines/multi_voice_tts.py`) must also stay dormant when the flag is off. The Session refactor in Task 5 reads the flag at runtime and lazy-imports the manager. |
| 8 | `Plan` max-segment cap is **3** (enforced at pydantic level). `RuleBasedDispatcher` in Phase 1 always emits a single-segment plan. | Phase 2's `LLMBackedDispatcher` can emit 1–3 segments; the schema rejects more. |
| 9 | `Outcome` is defined but not persisted in Phase 1. | Phase 2's `DialogManager` records `Outcome` in-memory only (kept per-session, attached to the last turn). Phase 5 will persist via `FeedbackLogger`. |
| 10 | `personas/registry.py::update_profile` re-validates via `model_validate({**model_dump, …})`. | Phase 2 doesn't need to call it (no learning loop yet), but if any test mutates a persona's profile it must use this seam — direct attribute assignment is not supported by pydantic v2. |

---

## File map

| Path | Status | Purpose |
|---|---|---|
| `server/server/protocol.py` | modify | Add optional `speaker` / `segmentIdx` to existing `llm.token` / `tts.sentence`; new `llm.segment_end`, `dispatch.plan` factories |
| `server/server/pipelines/multi_voice_tts.py` | create | `MultiVoiceTTS` — wraps N `TTS` instances (one per voice) behind the `TTS` ABC + speaker-aware `synthesize_for_speaker()` |
| `server/server/dialog/dispatcher.py` | modify | Add `LLMBackedDispatcher` next to existing `RuleBasedDispatcher`. Fast-path keyword check; falls back to rule-based on LLM error / malformed JSON / schema violation |
| `server/server/dialog/manager.py` | create | `DialogManager` — per-turn orchestrator: dispatcher → agent loop → segment streaming → voice swap → state update |
| `server/server/dialog/state.py` | create | Helpers for building `DialogState` from a `Session`'s memory + tracking warmth-budget across turns |
| `server/server/session.py` | modify | When `personas_enabled`, delegate the turn loop to `DialogManager.handle_turn`. When off, existing behaviour untouched. |
| `server/server/main.py` | modify | Lifespan: when `personas_enabled`, build `PersonaRegistry` once + `DialogManager`. When off, current factories untouched. |
| `server/tests/test_dialog_dispatcher_llm.py` | create | Tests for `LLMBackedDispatcher` (mocked anthropic client + fixtures) |
| `server/tests/test_dialog_manager.py` | create | Tests for `DialogManager` (mocked backends; single segment, multi-segment, handoff, failure recovery) |
| `server/tests/test_multi_voice_tts.py` | create | Tests for `MultiVoiceTTS` voice routing |
| `server/tests/test_protocol_phase2.py` | create | Round-trip tests for new + extended messages |
| `server/tests/test_session_phase2.py` | create | Integration tests for Session with the flag on (the existing `test_session.py` covers flag-off) |
| `server/tests/test_phase2_smoke.py` | create | End-to-end smoke with mocked WS + mocked backends + dormancy regression (flag off = no new modules imported) |
| `server/README.md` | modify | Update the Phase 1 section to a "Phase 2 — dialog manager active" section, with a quick check + manual run snippet |

**Phase 1 files NOT modified:** `personas/models.py`, `personas/seed.py`, `personas/registry.py`, `pipelines/openai_llm.py`, `pipelines/claude_llm.py`, `dialog/types.py`, `config.py`. The rule-based dispatcher in `dialog/dispatcher.py` is preserved verbatim and used as the fallback path inside `LLMBackedDispatcher`.

---

## Task 1: Protocol additions (`protocol.py`)

**Files:**
- Modify: `server/server/protocol.py`
- Create: `server/tests/test_protocol_phase2.py`

Protocol changes must be additive — existing clients that ignore unknown fields keep working. Old `llm.token` (no `speaker`) is still valid; new ones include `speaker` and `segmentIdx`.

- [ ] **Step 1: Write failing tests for the new messages**

Create `server/tests/test_protocol_phase2.py`:

```python
"""Round-trip tests for Phase 2 protocol additions."""

from __future__ import annotations

import json

from server.protocol import ServerMessage, encode_server


def test_llm_token_without_speaker_unchanged() -> None:
    """Back-compat: old shape still produced when speaker omitted."""
    msg = ServerMessage.llm_token("hello")
    assert msg == {"type": "llm.token", "delta": "hello"}
    encoded = json.loads(encode_server(msg))
    assert "speaker" not in encoded
    assert "segmentIdx" not in encoded


def test_llm_token_with_speaker_and_segment() -> None:
    msg = ServerMessage.llm_token("hi", speaker="pepper", segment_idx=1)
    assert msg["type"] == "llm.token"
    assert msg["delta"] == "hi"
    assert msg["speaker"] == "pepper"
    assert msg["segmentIdx"] == 1


def test_llm_segment_end() -> None:
    msg = ServerMessage.llm_segment_end(speaker="jarvis", segment_idx=0)
    assert msg == {"type": "llm.segment_end", "speaker": "jarvis", "segmentIdx": 0}


def test_dispatch_plan() -> None:
    msg = ServerMessage.dispatch_plan(
        turn_id="t-abc",
        segments=[
            {"speaker": "jarvis", "tier": "balanced", "mode": "chat", "intent": "design"},
            {"speaker": "pepper", "tier": "deep", "mode": "chat", "intent": "implement"},
        ],
        rationale="design then implement",
    )
    assert msg["type"] == "dispatch.plan"
    assert msg["turnId"] == "t-abc"
    assert len(msg["segments"]) == 2
    assert msg["rationale"] == "design then implement"
    # Encoded JSON round-trips
    decoded = json.loads(encode_server(msg))
    assert decoded == msg


def test_tts_sentence_without_speaker_unchanged() -> None:
    msg = ServerMessage.tts_sentence("hi.", "audio-1")
    assert msg == {"type": "tts.sentence", "text": "hi.", "audioId": "audio-1"}


def test_tts_sentence_with_speaker() -> None:
    msg = ServerMessage.tts_sentence("hi.", "audio-1", speaker="pepper")
    assert msg["speaker"] == "pepper"


def test_state_snapshot_personas_field() -> None:
    msg = ServerMessage.state_snapshot(
        system={
            "load": 0.1,
            "tokensPerMin": 0,
            "sessionId": "s1",
            "modelName": "claude-haiku-4-5",
            "personas": {
                "jarvis": {"model": "claude-haiku-4-5", "tier": "fast", "status": "idle"},
                "pepper": {"model": "gpt-5-mini", "tier": "fast", "status": "idle"},
                "lastDispatch": None,
            },
        },
        memory={"contextUsed": 0, "contextMax": 200000},
        network={"endpoint": "ws://localhost:8000/ws", "latencyMs": 12, "packets": 5,
                 "sendQueueDepth": 0, "sendQueueMax": 32},
        tasks={"active": 0, "queued": 0, "done": 0},
    )
    assert "personas" in msg["system"]
    assert msg["system"]["personas"]["jarvis"]["model"] == "claude-haiku-4-5"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && python -m pytest tests/test_protocol_phase2.py -v
```

Expected: every test fails with `AttributeError` or `TypeError` because the new factories don't exist yet.

- [ ] **Step 3: Extend `ServerMessage`**

Edit `server/server/protocol.py`. Update the `ServerMessage` class — add optional kwargs to `llm_token` / `tts_sentence`, and two new factories. The existing JSON keys are unchanged; new fields are only added when supplied.

Find the existing class and add / modify:

```python
class ServerMessage:
    """Factory class — methods return JSON-serializable dicts."""

    # … existing factories (ready, stt_partial, stt_final) unchanged …

    @staticmethod
    def llm_token(
        delta: str,
        *,
        speaker: str | None = None,
        segment_idx: int | None = None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {"type": "llm.token", "delta": delta}
        if speaker is not None:
            out["speaker"] = speaker
        if segment_idx is not None:
            out["segmentIdx"] = segment_idx
        return out

    @staticmethod
    def llm_segment_end(*, speaker: str, segment_idx: int) -> dict[str, Any]:
        return {"type": "llm.segment_end", "speaker": speaker, "segmentIdx": segment_idx}

    @staticmethod
    def llm_end() -> dict[str, Any]:
        return {"type": "llm.end"}

    @staticmethod
    def tts_sentence(
        text: str,
        audio_id: str,
        *,
        speaker: str | None = None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": "tts.sentence",
            "text": text,
            "audioId": audio_id,
        }
        if speaker is not None:
            out["speaker"] = speaker
        return out

    @staticmethod
    def tts_end(audio_id: str) -> dict[str, Any]:
        return {"type": "tts.end", "audioId": audio_id}

    @staticmethod
    def dispatch_plan(
        *,
        turn_id: str,
        segments: list[dict[str, Any]],
        rationale: str,
    ) -> dict[str, Any]:
        return {
            "type": "dispatch.plan",
            "turnId": turn_id,
            "segments": segments,
            "rationale": rationale,
        }

    # … remaining factories (error, telemetry, state_snapshot, calendar_update, ping) unchanged …
```

Keep the existing `state_snapshot` signature; the `system` dict can already accept a `personas` key (it's `dict[str, Any]`), so no factory change is needed for that — the test in Step 1 verifies the field passes through.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && python -m pytest tests/test_protocol_phase2.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Run the full suite**

```bash
cd server && python -m pytest -q
```

Expected: green — existing protocol tests still pass (the new optional kwargs default to None, preserving old shape).

- [ ] **Step 6: Lint**

```bash
cd server && ruff check . && mypy
```

Expected: ruff clean; mypy may have pre-existing errors but no new ones from `protocol.py`.

- [ ] **Step 7: Commit**

```bash
git add server/server/protocol.py server/tests/test_protocol_phase2.py
git commit -m "feat(protocol): add Phase 2 server messages

Optional speaker / segmentIdx on llm.token + tts.sentence (additive,
old shape preserved when omitted). New llm.segment_end and
dispatch.plan factories. state_snapshot.system already accepts a
'personas' key without factory changes; test locks the contract."
```

---

## Task 2: `MultiVoiceTTS` wrapper

**Files:**
- Create: `server/server/pipelines/multi_voice_tts.py`
- Create: `server/tests/test_multi_voice_tts.py`

The existing `EdgeTTS` (`server/server/pipelines/edge_tts.py`) holds one voice. Phase 2 needs voice-per-segment without changing the `TTS` ABC. Solution: a `MultiVoiceTTS` wrapper that holds a `{voice_id: TTS}` map. Implements the existing `TTS` ABC (so today's Session keeps working with a single voice), plus an extra `synthesize_for_speaker(text, audio_id, speaker, voice)` method the new DialogManager calls.

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_multi_voice_tts.py`:

```python
"""Tests for server.pipelines.multi_voice_tts — speaker-keyed TTS facade."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from server.pipelines.multi_voice_tts import MultiVoiceTTS


class _FakeTTS:
    """Records the texts it was asked to synthesize."""

    def __init__(self, voice_label: str, sample_rate: int = 24000) -> None:
        self.voice_label = voice_label
        self._sample_rate = sample_rate
        self.calls: list[tuple[str, str]] = []  # (text, audio_id)

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        self.calls.append((text, audio_id))
        # Yield one fake chunk so the async iterator is non-empty.
        yield self.voice_label.encode("utf-8")

    def sample_rate(self) -> int:
        return self._sample_rate


async def _collect(stream: AsyncIterator[bytes]) -> list[bytes]:
    return [b async for b in stream]


# ── Construction ──────────────────────────────────────────────────────


def test_construct_with_voice_map() -> None:
    jarvis = _FakeTTS("J")
    pepper = _FakeTTS("P")
    tts = MultiVoiceTTS({"jarvis": jarvis, "pepper": pepper}, default_speaker="jarvis")
    assert tts.sample_rate() == 24000


def test_construct_rejects_mismatched_sample_rates() -> None:
    jarvis = _FakeTTS("J", sample_rate=24000)
    pepper = _FakeTTS("P", sample_rate=16000)
    with pytest.raises(ValueError):
        MultiVoiceTTS({"jarvis": jarvis, "pepper": pepper}, default_speaker="jarvis")


def test_construct_rejects_empty_map() -> None:
    with pytest.raises(ValueError):
        MultiVoiceTTS({}, default_speaker="jarvis")


def test_construct_rejects_unknown_default() -> None:
    jarvis = _FakeTTS("J")
    with pytest.raises(ValueError):
        MultiVoiceTTS({"jarvis": jarvis}, default_speaker="pepper")


# ── synthesize_for_speaker (Phase 2 entry point) ──────────────────────


@pytest.mark.asyncio
async def test_synthesize_for_speaker_routes_to_jarvis() -> None:
    jarvis = _FakeTTS("J")
    pepper = _FakeTTS("P")
    tts = MultiVoiceTTS({"jarvis": jarvis, "pepper": pepper}, default_speaker="jarvis")
    out = await _collect(tts.synthesize_for_speaker("hello.", "a1", speaker="jarvis"))
    assert out == [b"J"]
    assert jarvis.calls == [("hello.", "a1")]
    assert pepper.calls == []


@pytest.mark.asyncio
async def test_synthesize_for_speaker_routes_to_pepper() -> None:
    jarvis = _FakeTTS("J")
    pepper = _FakeTTS("P")
    tts = MultiVoiceTTS({"jarvis": jarvis, "pepper": pepper}, default_speaker="jarvis")
    out = await _collect(tts.synthesize_for_speaker("hi.", "a1", speaker="pepper"))
    assert out == [b"P"]
    assert pepper.calls == [("hi.", "a1")]
    assert jarvis.calls == []


@pytest.mark.asyncio
async def test_synthesize_for_speaker_falls_back_when_speaker_missing() -> None:
    jarvis = _FakeTTS("J")
    tts = MultiVoiceTTS({"jarvis": jarvis}, default_speaker="jarvis")
    # Pepper isn't registered; route to default.
    out = await _collect(tts.synthesize_for_speaker("hi.", "a1", speaker="pepper"))
    assert out == [b"J"]
    assert jarvis.calls == [("hi.", "a1")]


# ── TTS ABC compatibility ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_synthesize_uses_default_speaker() -> None:
    """`synthesize` (the ABC method) routes to the default speaker."""
    jarvis = _FakeTTS("J")
    pepper = _FakeTTS("P")
    tts = MultiVoiceTTS({"jarvis": jarvis, "pepper": pepper}, default_speaker="jarvis")
    out = await _collect(tts.synthesize("hi.", "a1"))
    assert out == [b"J"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && python -m pytest tests/test_multi_voice_tts.py -v
```

Expected: every test fails with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `multi_voice_tts.py`**

Create `server/server/pipelines/multi_voice_tts.py`:

```python
"""MultiVoiceTTS — routes synthesis to one of N TTS instances by speaker.

The existing `EdgeTTS` holds one voice (Microsoft neural voice id). Phase 2
needs a different voice per Jarvis / Pepper segment without modifying the
`TTS` ABC or the existing `_build_tts()` factory.

This wrapper holds a map `{speaker_id: TTS}` and:
  * Implements the `TTS` ABC by routing `synthesize()` to the default speaker
    (so the existing single-voice code path keeps working).
  * Exposes `synthesize_for_speaker(text, audio_id, speaker)` for the
    Phase 2 `DialogManager` to pick a voice per segment.

If a speaker isn't registered (e.g. Codex CLI binary missing and we fall
back to chat-only Pepper — but Pepper's voice never reaches this wrapper
because Pepper is just unavailable) we route to `default_speaker`. That
shouldn't happen in practice; logged as a warning.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from .interfaces import TTS

log = logging.getLogger(__name__)


class MultiVoiceTTS(TTS):
    """A `TTS` that dispatches by speaker id."""

    def __init__(self, voices: dict[str, TTS], *, default_speaker: str) -> None:
        if not voices:
            raise ValueError("MultiVoiceTTS requires at least one voice")
        if default_speaker not in voices:
            raise ValueError(
                f"default_speaker {default_speaker!r} not in voices: {sorted(voices)}"
            )
        rates = {v.sample_rate() for v in voices.values()}
        if len(rates) != 1:
            raise ValueError(
                f"all voices must share a sample_rate (got {sorted(rates)})"
            )
        self._voices = dict(voices)
        self._default_speaker = default_speaker
        self._sample_rate = next(iter(rates))

    def sample_rate(self) -> int:
        return self._sample_rate

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        """ABC entry point — routes to the default speaker.

        Preserves the existing single-voice code path so today's Session
        (with the flag off) keeps working unchanged.
        """
        backend = self._voices[self._default_speaker]
        async for chunk in backend.synthesize(text, audio_id):
            yield chunk

    async def synthesize_for_speaker(
        self,
        text: str,
        audio_id: str,
        *,
        speaker: str,
    ) -> AsyncIterator[bytes]:
        """Phase 2 entry point — pick the speaker's voice."""
        backend = self._voices.get(speaker)
        if backend is None:
            log.warning(
                "MultiVoiceTTS: speaker %r not registered; using default %r",
                speaker, self._default_speaker,
            )
            backend = self._voices[self._default_speaker]
        async for chunk in backend.synthesize(text, audio_id):
            yield chunk
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && python -m pytest tests/test_multi_voice_tts.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 5: Full suite + lint**

```bash
cd server && python -m pytest -q && ruff check . && mypy
```

Expected: green / clean.

- [ ] **Step 6: Commit**

```bash
git add server/server/pipelines/multi_voice_tts.py server/tests/test_multi_voice_tts.py
git commit -m "feat(pipelines): add MultiVoiceTTS wrapper

Routes TTS synthesis by speaker id. Implements the existing TTS ABC
by delegating synthesize() to a default speaker (so single-voice
code paths keep working) and exposes synthesize_for_speaker() for
the Phase 2 DialogManager. All voices must share a sample_rate;
unknown speakers fall back to default with a logged warning."
```

---

## Task 3: `LLMBackedDispatcher`

**Files:**
- Modify: `server/server/dialog/dispatcher.py` (add `LLMBackedDispatcher` next to `RuleBasedDispatcher`)
- Create: `server/tests/test_dialog_dispatcher_llm.py`

The LLM-backed dispatcher uses Anthropic's tool-use feature to force a structured `Plan` output. On any error (network, malformed JSON, schema violation), it falls back to the rule-based dispatcher. There's also a "fast path" — when the utterance starts with a recognized name AND no domain-crossing keywords are present, skip the LLM entirely (the rule-based dispatcher already handles this case correctly).

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_dialog_dispatcher_llm.py`:

```python
"""Tests for server.dialog.dispatcher.LLMBackedDispatcher."""

from __future__ import annotations

import json
from typing import Any

import pytest

from server.dialog.dispatcher import LLMBackedDispatcher, RuleBasedDispatcher
from server.dialog.types import DialogState


# ── Fake Anthropic client ─────────────────────────────────────────────


class _FakeBlock:
    def __init__(self, *, btype: str, input: dict[str, Any] | None = None) -> None:
        self.type = btype
        self.input = input or {}


class _FakeMessage:
    def __init__(self, content: list[_FakeBlock]) -> None:
        self.content = content


class _FakeMessages:
    def __init__(
        self,
        *,
        return_msg: _FakeMessage | None = None,
        raise_on_create: Exception | None = None,
    ) -> None:
        self.return_msg = return_msg
        self.raise_on_create = raise_on_create
        self.captured_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> _FakeMessage:
        self.captured_kwargs = kwargs
        if self.raise_on_create:
            raise self.raise_on_create
        assert self.return_msg is not None
        return self.return_msg


class _FakeClient:
    def __init__(
        self,
        *,
        return_msg: _FakeMessage | None = None,
        raise_on_create: Exception | None = None,
    ) -> None:
        self.messages = _FakeMessages(
            return_msg=return_msg, raise_on_create=raise_on_create,
        )


def _plan_tool_use(segments: list[dict[str, Any]], rationale: str) -> _FakeMessage:
    return _FakeMessage(
        content=[
            _FakeBlock(
                btype="tool_use",
                input={"segments": segments, "rationale": rationale},
            ),
        ],
    )


# ── Fast path (no LLM call) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_fast_path_name_at_start_skips_llm() -> None:
    client = _FakeClient(return_msg=_plan_tool_use([], "should not be called"))
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Pepper, run the tests", DialogState())
    assert plan.segments[0].speaker == "pepper"
    # Fast path: LLM wasn't called.
    assert client.messages.captured_kwargs == {}


@pytest.mark.asyncio
async def test_fast_path_with_domain_keyword_invokes_llm() -> None:
    client = _FakeClient(
        return_msg=_plan_tool_use(
            [
                {"speaker": "jarvis", "tier": "balanced", "mode": "chat",
                 "intent": "design", "handoff_style": "soft"},
                {"speaker": "pepper", "tier": "deep", "mode": "chat",
                 "intent": "implement"},
            ],
            "design then implement",
        ),
    )
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch(
        "Jarvis, design and then implement the CSV exporter",
        DialogState(),
    )
    # LLM was called (domain keywords detected).
    assert client.messages.captured_kwargs != {}
    assert len(plan.segments) == 2


# ── Happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_call_returns_valid_plan() -> None:
    client = _FakeClient(
        return_msg=_plan_tool_use(
            [
                {"speaker": "jarvis", "tier": "balanced", "mode": "chat",
                 "intent": "compare A and B"},
            ],
            "ambiguous comparison",
        ),
    )
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Should we ship Monday or Wednesday?", DialogState())
    assert len(plan.segments) == 1
    assert plan.segments[0].tier == "balanced"
    assert "compare" in plan.segments[0].intent


# ── Fallback paths ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_falls_back_on_llm_error() -> None:
    import anthropic
    import httpx

    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(status_code=500, request=req)
    client = _FakeClient(
        raise_on_create=anthropic.APIStatusError("server error", response=resp, body=None),
    )
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Should we refactor X?", DialogState())
    # Fell back to rule-based: default speaker (Jarvis), single segment.
    assert len(plan.segments) == 1
    assert plan.segments[0].speaker == "jarvis"
    assert "fallback" in plan.rationale.lower()


@pytest.mark.asyncio
async def test_falls_back_on_invalid_schema() -> None:
    """If the LLM returns segments that don't validate (e.g. unknown speaker),
    the dispatcher falls back to the rule-based path."""
    client = _FakeClient(
        return_msg=_plan_tool_use(
            [{"speaker": "bob", "tier": "fast", "mode": "chat", "intent": "x"}],
            "bad output",
        ),
    )
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Should we refactor X?", DialogState())
    assert plan.segments[0].speaker == "jarvis"
    assert "fallback" in plan.rationale.lower()


@pytest.mark.asyncio
async def test_falls_back_when_no_tool_use_block() -> None:
    """LLM returned text but didn't invoke the plan tool — fall back."""
    msg = _FakeMessage(content=[_FakeBlock(btype="text")])
    client = _FakeClient(return_msg=msg)
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Should we refactor X?", DialogState())
    assert "fallback" in plan.rationale.lower()


# ── Slash prefix preserved through LLM path ───────────────────────────


@pytest.mark.asyncio
async def test_slash_prefix_uses_fast_path() -> None:
    """`/codex …` should always use the rule-based fast path so it never
    misroutes due to a quirky LLM output."""
    client = _FakeClient(return_msg=_plan_tool_use([], "should not be called"))
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("/codex add a test", DialogState())
    assert client.messages.captured_kwargs == {}
    assert plan.segments[0].speaker == "pepper"
    assert plan.segments[0].mode == "codex_agent"


# ── Cap enforcement ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_falls_back_when_llm_returns_too_many_segments() -> None:
    """Plan schema caps at 3 — anything more is treated as malformed."""
    client = _FakeClient(
        return_msg=_plan_tool_use(
            [
                {"speaker": "jarvis", "tier": "fast", "mode": "chat", "intent": "a"},
                {"speaker": "pepper", "tier": "fast", "mode": "chat", "intent": "b"},
                {"speaker": "jarvis", "tier": "fast", "mode": "chat", "intent": "c"},
                {"speaker": "pepper", "tier": "fast", "mode": "chat", "intent": "d"},
            ],
            "too many",
        ),
    )
    d = LLMBackedDispatcher(client=client, model="claude-haiku-4-5")
    plan = await d.dispatch("Should we refactor X?", DialogState())
    assert "fallback" in plan.rationale.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && python -m pytest tests/test_dialog_dispatcher_llm.py -v
```

Expected: every test fails with `ImportError` because `LLMBackedDispatcher` doesn't exist yet.

- [ ] **Step 3: Implement `LLMBackedDispatcher`**

Append to `server/server/dialog/dispatcher.py` (after `RuleBasedDispatcher`):

```python
# ── LLM-backed dispatcher (Phase 2) ────────────────────────────────────

import logging
from typing import Any

import anthropic
from pydantic import ValidationError

logger = logging.getLogger(__name__)


# Domain-crossing keywords that disable the fast path (spec §5.4).
_DOMAIN_KEYWORDS = frozenset(
    {
        "but also",
        "and then",
        "code",
        "test",
        "tests",
        "implement",
        "implementation",
        "design",
        "plan",
        "refactor",
        "decide",
        "compare",
    }
)


# JSON schema for the structured Plan output. Anthropic tool-use validates
# the input against this; we re-validate via pydantic for safety.
_PLAN_TOOL = {
    "name": "emit_plan",
    "description": (
        "Emit a per-turn routing plan. Choose 1-3 segments. The user spoke; "
        "decide which persona (Jarvis = Claude / strategy, Pepper = OpenAI / "
        "code) answers, at what tier (fast / balanced / deep), in what mode "
        "(chat or codex_agent — codex_agent only for Pepper on concretely "
        "actionable code work). Emit a one-sentence rationale."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "segments": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker": {"type": "string", "enum": ["jarvis", "pepper"]},
                        "tier": {"type": "string", "enum": ["fast", "balanced", "deep"]},
                        "mode": {"type": "string", "enum": ["chat", "codex_agent"]},
                        "intent": {"type": "string", "minLength": 1, "maxLength": 200},
                        "handoff_style": {
                            "type": ["string", "null"],
                            "enum": ["flat", "soft", None],
                        },
                    },
                    "required": ["speaker", "tier", "mode", "intent"],
                    "additionalProperties": False,
                },
            },
            "rationale": {"type": "string", "minLength": 1, "maxLength": 400},
        },
        "required": ["segments", "rationale"],
        "additionalProperties": False,
    },
}


_DISPATCHER_SYSTEM_PROMPT = """\
You are the dispatcher for a two-persona AI system. The user just spoke to
their voice assistant. Decide whether Jarvis (Claude, strategy/conversational),
Pepper (OpenAI, code/dev), or both should respond, at what tier (fast /
balanced / deep), and whether Pepper should escalate to the Codex CLI agent
(mode=codex_agent — only for concretely actionable code work).

Tier rules:
- fast: simple Q&A, conversational, short factual.
- balanced: comparison, multi-step reasoning, >300 token expected output.
- deep: architecture / design / refactor / decide / plan verbs, or long
  context. Jarvis's deep tier is Opus 4.7; Pepper's is GPT-5 Codex.

Hand-off rules: emit ≥2 segments ONLY when there's a clear domain crossing
(e.g. Jarvis sets context → Pepper implements). Otherwise stay solo.

Persona profiles:
{profiles}

Reply by invoking the `emit_plan` tool. No prose.
"""


class _PlanFromLLMError(Exception):
    """Internal — raised when the LLM output can't be turned into a Plan."""


def _utterance_has_domain_keyword(text: str) -> bool:
    """Cheap allow-list check for fast-path bypass (spec §5.4)."""
    lower = text.lower()
    return any(kw in lower for kw in _DOMAIN_KEYWORDS)


def _strip_name_prefix(text: str) -> str:
    """Used only by the fast-path detector — name-at-start check.

    Returns the suffix after a recognized name prefix, or the original
    text if no name was matched.
    """
    m = _NAME_RE.match(text)
    return text[m.end():].lstrip() if m else text


class LLMBackedDispatcher:
    """Per-turn dispatcher backed by claude-haiku-4-5 tool-use.

    Has a built-in `RuleBasedDispatcher` fallback for: fast-path turns
    (name-at-start, no domain keywords), slash prefix turns (handled by
    rule-based directly), LLM errors, malformed output, and schema
    violations. Functional even if Anthropic is down.
    """

    def __init__(
        self,
        *,
        client: Any,
        model: str = "claude-haiku-4-5",
        max_tokens: int = 1024,
        profiles: str = "(profiles not provided)",
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._profiles = profiles
        self._rule_based = RuleBasedDispatcher()

    async def dispatch(
        self,
        text: str,
        state: DialogState,
        *,
        now_ts: float | None = None,
    ) -> Plan:
        """Return a Plan for the given utterance + state."""
        # Slash prefix always uses the rule-based fast path so it can't be
        # misrouted by a quirky LLM output.
        if _detect_slash(text) is not None:
            return self._rule_based.dispatch(text, state, now_ts=now_ts)

        # Name-at-start fast path: skip the LLM unless a domain keyword is
        # present in the rest of the utterance.
        name_match = _detect_name(text)
        if name_match is not None:
            _, rest = name_match
            if not _utterance_has_domain_keyword(rest):
                return self._rule_based.dispatch(text, state, now_ts=now_ts)

        # Otherwise call the LLM. On any failure, fall back.
        try:
            return await self._call_llm(text)
        except (_PlanFromLLMError, anthropic.APIError) as exc:
            logger.warning("LLMBackedDispatcher fallback: %s", exc)
            plan = self._rule_based.dispatch(text, state, now_ts=now_ts)
            return plan.model_copy(
                update={"rationale": f"{plan.rationale}; fallback ({exc.__class__.__name__})"},
            )

    async def _call_llm(self, text: str) -> Plan:
        system = _DISPATCHER_SYSTEM_PROMPT.format(profiles=self._profiles)
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": text}],
            tools=[_PLAN_TOOL],
            tool_choice={"type": "tool", "name": "emit_plan"},
        )
        # Find the tool_use block.
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                try:
                    return Plan.model_validate(block.input)
                except ValidationError as exc:
                    raise _PlanFromLLMError(f"schema violation: {exc}") from exc
        raise _PlanFromLLMError("no tool_use block in LLM response")
```

**Important:** The new code imports `_detect_slash`, `_detect_name`, and `_NAME_RE` from the existing module. These are already module-private helpers in `dispatcher.py`. If they have a leading underscore but you need to reference them within the same module (you do — `LLMBackedDispatcher` is appended to the same file), that works without changes. If for some reason you decide to split into a separate file, promote them to non-underscore or import explicitly.

Also export the new class from the dialog package:

Edit `server/server/dialog/__init__.py` to add `LLMBackedDispatcher`:

```python
from server.dialog.dispatcher import LLMBackedDispatcher, RuleBasedDispatcher
from server.dialog.types import (
    DialogState,
    Outcome,
    Plan,
    Segment,
    TurnRef,
)

__all__ = [
    "DialogState",
    "LLMBackedDispatcher",
    "Outcome",
    "Plan",
    "RuleBasedDispatcher",
    "Segment",
    "TurnRef",
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && python -m pytest tests/test_dialog_dispatcher_llm.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 5: Full suite + lint**

```bash
cd server && python -m pytest -q && ruff check . && mypy
```

Expected: green / clean.

- [ ] **Step 6: Commit**

```bash
git add server/server/dialog/dispatcher.py server/server/dialog/__init__.py server/tests/test_dialog_dispatcher_llm.py
git commit -m "feat(dialog): add LLMBackedDispatcher (claude-haiku-4-5 tool-use)

Calls Anthropic with the emit_plan tool to get a structured Plan.
Falls back to RuleBasedDispatcher on: slash prefix turn, name-at-
start with no domain keyword (fast path, ~70% of turns), LLM error,
schema violation, missing tool_use block. Fallback path tags the
rationale with the failure class for telemetry."
```

---

## Task 4: `DialogManager`

**Files:**
- Create: `server/server/dialog/manager.py`
- Create: `server/tests/test_dialog_manager.py`

The `DialogManager` is the per-turn orchestrator. It owns: a `PersonaRegistry`, a dispatcher (LLM-backed in production), an `LLMFactory` callable that produces an `LLM` per `(persona, model_id)`, and a `MultiVoiceTTS`. The Session calls `DialogManager.handle_turn(ws, text, history)` once per user utterance.

Per-turn flow (spec §3.3):
1. Build a `DialogState` snapshot from session memory.
2. Dispatch → `Plan`.
3. Emit `dispatch.plan` to the WS.
4. For each segment: build prompt, stream LLM → `llm.token` (with speaker), buffer sentences → `tts.sentence` (with speaker). On segment end, emit `llm.segment_end`.
5. Emit `llm.end`. Update sticky-speaker / last-turn-ts.
6. Record an `Outcome` (in-memory; Phase 5 persists).

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_dialog_manager.py`:

```python
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
            yield "API error. Check the logs."  # spoken error from _spoken_error_for

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
    # The failing segment did emit tokens (the spoken error sentence).
    # But the second segment never ran.
    tokens = [m for m in ws.sent if m["type"] == "llm.token"]
    pepper_tokens = [t for t in tokens if t["speaker"] == "pepper"]
    assert not pepper_tokens
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && python -m pytest tests/test_dialog_manager.py -v
```

Expected: every test fails with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `DialogManager`**

Create `server/server/dialog/manager.py`:

```python
"""DialogManager — per-turn orchestrator.

Spec anchors: §3.3 (per-turn flow), §6 (segment execution), §9.1 (protocol).

The Manager owns the routing → streaming → voice-swap pipeline. It's
constructed once per Session (in main.py's lifespan when
`personas_enabled` is true) and `handle_turn` is called from
`Session.run` per user utterance.

Streaming model:
  1. Build DialogState from session memory.
  2. Dispatch (LLMBackedDispatcher or fallback) → Plan.
  3. Emit `dispatch.plan` to WS.
  4. For each segment:
     - Resolve persona + model_id from registry.tier
     - Build extra_context = specialty_profile + segment.intent
     - llm_factory(persona, model_id).stream(...) → token deltas
     - Per token: send llm.token (with speaker, segmentIdx)
     - Per sentence boundary: send tts.sentence + stream audio chunks
     - On segment end: send llm.segment_end
  5. Send llm.end.
  6. Update sticky-speaker (last_speaker, last_turn_ts) for next turn.
  7. Record Outcome in-memory.

In Phase 2 there's no Codex agent yet — `mode=codex_agent` segments are
treated as `mode=chat` with a logged warning. Phase 3 introduces the
CodexAgent backend and wires it here.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol

from server.dialog.types import (
    DialogState,
    Outcome,
    PersonaId,
    Plan,
    Segment,
)
from server.personas.models import Persona
from server.personas.registry import PersonaRegistry
from server.pipelines.sentence_split import SentenceBuffer
from server.protocol import ServerMessage, encode_server

logger = logging.getLogger(__name__)


class _WSLike(Protocol):
    async def send_text(self, data: str) -> None: ...
    async def send_bytes(self, data: bytes) -> None: ...


class _LLMLike(Protocol):
    def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]: ...


class _DispatcherLike(Protocol):
    async def dispatch(
        self,
        text: str,
        state: DialogState,
        *,
        now_ts: float | None = None,
    ) -> Plan: ...


class _MultiVoiceTTSLike(Protocol):
    async def synthesize_for_speaker(
        self,
        text: str,
        audio_id: str,
        *,
        speaker: str,
    ) -> AsyncIterator[bytes]: ...


LLMFactory = Callable[[Persona, str], _LLMLike]


class DialogManager:
    """Per-turn orchestrator (Phase 2, chat-only)."""

    def __init__(
        self,
        *,
        registry: PersonaRegistry,
        dispatcher: _DispatcherLike,
        llm_factory: LLMFactory,
        tts: _MultiVoiceTTSLike,
    ) -> None:
        self._registry = registry
        self._dispatcher = dispatcher
        self._llm_factory = llm_factory
        self._tts = tts
        self._state = DialogState()
        self._outcomes: list[Outcome] = []

    def current_state(self) -> DialogState:
        return self._state

    def last_outcome(self) -> Outcome | None:
        return self._outcomes[-1] if self._outcomes else None

    async def handle_turn(
        self,
        ws: _WSLike,
        *,
        text: str,
        history: list[dict[str, str]],
    ) -> None:
        """Run one turn end-to-end. Emits all WS messages; does not raise."""
        turn_id = f"t-{uuid.uuid4().hex[:8]}"
        start = time.monotonic()

        plan = await self._dispatcher.dispatch(text, self._state)
        await self._send(ws, ServerMessage.dispatch_plan(
            turn_id=turn_id,
            segments=[s.model_dump() for s in plan.segments],
            rationale=plan.rationale,
        ))

        outcome = Outcome()
        try:
            for idx, segment in enumerate(plan.segments):
                ok = await self._run_segment(
                    ws, idx=idx, segment=segment, history=history, plan=plan,
                )
                if not ok:
                    break
            outcome = outcome.model_copy(update={"completed": True})
        finally:
            await self._send(ws, ServerMessage.llm_end())
            # Sticky-speaker update: the LAST speaker who actually streamed.
            last_speaker = self._last_streamed_speaker(plan, outcome)
            if last_speaker is not None:
                self._state = DialogState(
                    last_speaker=last_speaker,
                    last_turn_ts=time.time(),
                    recent_turns=self._state.recent_turns,  # Phase 2: leave compact
                    warmth_budget=self._state.warmth_budget,
                )
            outcome = outcome.model_copy(update={
                "latency_ms": (time.monotonic() - start) * 1000.0,
            })
            self._outcomes.append(outcome)

    async def _run_segment(
        self,
        ws: _WSLike,
        *,
        idx: int,
        segment: Segment,
        history: list[dict[str, str]],
        plan: Plan,
    ) -> bool:
        """Run a single segment. Returns False on failure (caller halts plan)."""
        if not self._registry.is_available(segment.speaker):
            logger.warning("segment %d: persona %s unavailable; skipping",
                           idx, segment.speaker)
            return False
        persona = self._registry.get(segment.speaker)
        tier = persona.tiers[segment.tier]
        llm = self._llm_factory(persona, tier.model_id)

        # Phase 2: codex_agent mode degrades to chat with a logged warning.
        # Phase 3 will dispatch to CodexAgent instead.
        if segment.mode == "codex_agent":
            logger.warning(
                "segment %d (pepper, codex_agent) degraded to chat in Phase 2",
                idx,
            )

        extra_context = (
            f"Persona profile: {persona.specialty_profile}\n"
            f"Segment intent: {segment.intent}"
        )

        buf = SentenceBuffer()
        audio_id_base = f"seg-{idx}"
        sent_anything = False
        try:
            async for delta in llm.stream(
                history=history,
                user_text=plan_text_for_segment(plan, idx, persona),
                extra_context=extra_context,
            ):
                sent_anything = True
                await self._send(ws, ServerMessage.llm_token(
                    delta, speaker=segment.speaker, segment_idx=idx,
                ))
                for sentence in buf.feed(delta):
                    await self._emit_sentence(
                        ws, sentence, audio_id=f"{audio_id_base}-{buf.count}",
                        speaker=segment.speaker,
                    )
            # Flush any remaining buffered text.
            tail = buf.flush()
            if tail:
                await self._emit_sentence(
                    ws, tail, audio_id=f"{audio_id_base}-tail",
                    speaker=segment.speaker,
                )
        except Exception as exc:  # noqa: BLE001 — defensive at top of stream
            logger.exception("segment %d crashed", idx)
            # Emit a spoken error in the same voice.
            await self._send(ws, ServerMessage.llm_token(
                f"Error: {exc}",
                speaker=segment.speaker,
                segment_idx=idx,
            ))
            await self._send(ws, ServerMessage.llm_segment_end(
                speaker=segment.speaker, segment_idx=idx,
            ))
            return False

        await self._send(ws, ServerMessage.llm_segment_end(
            speaker=segment.speaker, segment_idx=idx,
        ))
        return sent_anything

    async def _emit_sentence(
        self,
        ws: _WSLike,
        text: str,
        *,
        audio_id: str,
        speaker: PersonaId,
    ) -> None:
        await self._send(ws, ServerMessage.tts_sentence(
            text=text, audio_id=audio_id, speaker=speaker,
        ))
        async for chunk in self._tts.synthesize_for_speaker(
            text, audio_id, speaker=speaker,
        ):
            await ws.send_bytes(chunk)
        await self._send(ws, ServerMessage.tts_end(audio_id))

    async def _send(self, ws: _WSLike, payload: dict[str, Any]) -> None:
        await ws.send_text(encode_server(payload))

    def _last_streamed_speaker(self, plan: Plan, outcome: Outcome) -> PersonaId | None:
        return plan.segments[-1].speaker if plan.segments else None


def plan_text_for_segment(plan: Plan, idx: int, persona: Persona) -> str:
    """Build the user-visible text the LLM sees for a given segment.

    Phase 2: the original utterance is fine for solo turns; for multi-
    segment plans the second persona sees "Continuing from <prior speaker>:
    <intent>" so it doesn't blindly repeat. Detail is intentionally minimal —
    the persona's system prompt + specialty profile + extra_context carry
    the heavy lifting.
    """
    if idx == 0:
        return plan.segments[0].intent
    prior = plan.segments[idx - 1]
    return (
        f"Continuing from {prior.speaker}'s segment "
        f"({prior.intent[:80]}). Your part: {plan.segments[idx].intent}"
    )
```

**Note on `SentenceBuffer`:** the existing `server/server/pipelines/sentence_split.py` has a `SentenceBuffer` class with `feed(delta) → iterable[str]`, `flush() → str | None`, and a `count` attribute. Verify the exact API and adapt if the names differ. The DialogManager test in Step 1 doesn't exercise sentence boundaries deeply; the integration test in Task 6 will.

**If `count` doesn't exist** on `SentenceBuffer`, replace `buf.count` with a local sentence counter you increment inside the `for sentence in buf.feed(delta):` loop.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && python -m pytest tests/test_dialog_manager.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Update the dialog package exports**

Edit `server/server/dialog/__init__.py`:

```python
from server.dialog.dispatcher import LLMBackedDispatcher, RuleBasedDispatcher
from server.dialog.manager import DialogManager
from server.dialog.types import (
    DialogState,
    Outcome,
    Plan,
    Segment,
    TurnRef,
)

__all__ = [
    "DialogManager",
    "DialogState",
    "LLMBackedDispatcher",
    "Outcome",
    "Plan",
    "RuleBasedDispatcher",
    "Segment",
    "TurnRef",
]
```

- [ ] **Step 6: Full suite + lint**

```bash
cd server && python -m pytest -q && ruff check . && mypy
```

- [ ] **Step 7: Commit**

```bash
git add server/server/dialog/manager.py server/server/dialog/__init__.py server/tests/test_dialog_manager.py
git commit -m "feat(dialog): add DialogManager (per-turn orchestrator, chat-only)

Runs the dispatch → segment-by-segment streaming → voice-swap loop.
Emits dispatch.plan, llm.token (with speaker+segmentIdx), tts.sentence,
llm.segment_end, llm.end. Updates sticky-speaker state after each turn.
Records Outcome in-memory (Phase 5 will persist). codex_agent mode
degrades to chat with a warning in Phase 2 — Phase 3 wires the
CodexAgent backend."
```

---

## Task 5: Session integration

**Files:**
- Modify: `server/server/session.py`
- Modify: `server/server/main.py`
- Create: `server/tests/test_session_phase2.py`

Goal: when `settings.personas_enabled` is true, the Session delegates the per-turn loop to `DialogManager.handle_turn(ws, text=…, history=…)` instead of running its existing inline `_run_llm` / `_run_tts` path. When false, behaviour is byte-for-byte unchanged.

Strategy:
- Add a `dialog_manager: DialogManager | None = None` constructor kwarg to `Session`.
- In the turn handler, branch on `dialog_manager`:
  - If set → call `dialog_manager.handle_turn(...)`.
  - If None → existing behaviour.
- In `main.py`'s lifespan, when `settings.personas_enabled`, construct the registry + dispatcher + manager once and pass it into each new Session.

The detailed Session diff depends on the current `session.py` shape — read it before editing. Below is the contract; the exact diff lines vary.

- [ ] **Step 1: Read `session.py` to find the turn handler entry point**

Open `server/server/session.py` and find the method that runs a turn (probably `_handle_user_text` or `_run_llm_turn` — names may differ). Note the signature and where it dispatches to `self._llm.stream(...)` and `self._tts.synthesize(...)`. This is the branch point.

- [ ] **Step 2: Write failing tests** for the personas-on path

Create `server/tests/test_session_phase2.py`:

```python
"""Session integration with the DialogManager (flag on)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from server.dialog.manager import DialogManager
from server.dialog.types import Plan, Segment
from server.session import Session
from tests.test_session import _FakeWS  # reuse the existing fake


class _ScriptedDispatcher:
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    async def dispatch(self, text, state, *, now_ts=None):  # type: ignore[no-untyped-def]
        return self._plan


class _ScriptedLLM:
    def __init__(self) -> None:
        pass

    async def stream(self, history, user_text, *, extra_context=""):  # type: ignore[no-untyped-def]
        for d in ["hi.", " "]:
            yield d


class _FakeTTS:
    def sample_rate(self) -> int:
        return 24000

    async def synthesize(self, text, audio_id):  # type: ignore[no-untyped-def]
        yield b""

    async def synthesize_for_speaker(self, text, audio_id, *, speaker):  # type: ignore[no-untyped-def]
        yield b""


@pytest.mark.asyncio
async def test_session_delegates_to_dialog_manager_when_configured() -> None:
    """If a DialogManager is supplied, the Session uses it for text turns."""
    from server.personas.registry import PersonaRegistry

    plan = Plan(
        segments=[Segment(speaker="jarvis", tier="fast", mode="chat", intent="hi")],
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
        tts=_FakeTTS(),
    )

    # Build a Session with the manager. Use existing test fakes for STT/LLM/TTS;
    # the manager is what drives the turn when configured.
    # (Construct kwargs vary; adapt to actual Session signature.)
    # ... (test body adapted to actual Session constructor; goal:
    #      send a TextIn message and verify dispatch.plan + llm.token (with speaker) flow)
```

**Note:** the exact test body depends on the Session constructor. Adapt the fixture to match the real signature. The intent is: a Session with a `dialog_manager` set, fed a `TextIn` message, produces a `dispatch.plan` and speaker-tagged `llm.token` events on the WS. Without `dialog_manager`, no `dispatch.plan` is emitted (regression preservation).

- [ ] **Step 3: Add `dialog_manager` kwarg to Session**

Edit `server/server/session.py`:

1. Add `dialog_manager: DialogManager | None = None` to `__init__`.
2. Store as `self._dialog_manager`.
3. In the user-text handler, branch:

```python
if self._dialog_manager is not None:
    # Phase 2 path: DialogManager owns the turn.
    await self._dialog_manager.handle_turn(
        self._ws,
        text=user_text,
        history=self._history_snapshot(),
    )
else:
    # Existing single-Jarvis path — unchanged.
    ...  # original inline logic
```

Add the import: `from server.dialog.manager import DialogManager`.

**Don't** delete or modify the existing single-Jarvis path. Only branch around it.

- [ ] **Step 4: Wire up `main.py` lifespan**

Edit `server/server/main.py`. When `settings.personas_enabled` is true:

1. In `lifespan()`, after the memory store is opened, construct:
   - `_persona_registry = build_registry_from_settings(settings, codex_workdir=str(_git_root()))`
   - `_dispatcher = LLMBackedDispatcher(client=<anthropic client>, model=settings.dispatcher_model, profiles=<formatted from registry>)`
   - `_multi_voice_tts = MultiVoiceTTS({...})` — one voice per available persona
2. In the WS endpoint, when constructing the per-connection `Session`, also build a per-session `DialogManager` and pass `dialog_manager=mgr` to `Session`.

Module-level state additions:
```python
_persona_registry: PersonaRegistry | None = None
_dispatcher: LLMBackedDispatcher | None = None
_multi_voice_tts: MultiVoiceTTS | None = None
```

The `llm_factory` for the DialogManager: a function that takes `(persona, model_id)` and returns a fresh `ClaudeLLM` or `OpenAILLM` instance. Reuse the existing per-persona system prompts. Sketch:

```python
def _build_llm_factory(
    anthropic_client: anthropic.AsyncAnthropic,
    openai_client: openai.AsyncOpenAI,
) -> LLMFactory:
    def factory(persona: Persona, model_id: str) -> LLM:
        if persona.provider == "anthropic":
            return ClaudeLLM(
                default_model=model_id,
                max_tokens=settings.llm_max_tokens,
                system_prompt=persona.system_prompt,
                client=anthropic_client,
            )
        return OpenAILLM(
            default_model=model_id,
            max_tokens=settings.llm_max_tokens,
            system_prompt=persona.system_prompt,
            client=openai_client,
        )
    return factory
```

When `personas_enabled` is false, none of this runs (the existing factories `_build_llm`, `_build_tts` are used).

- [ ] **Step 5: Verify dormancy regression guard still passes**

```bash
cd server && python -m pytest tests/test_phase1_smoke.py::test_phase1_dormant_when_flag_off -v
```

The test asserts that with `JARVIS_PERSONAS_ENABLED=false`, `server.dialog.dispatcher`, `server.dialog.types`, `server.personas.registry`, `server.pipelines.openai_llm` are NOT auto-imported by `server.main`. Update the test if Phase 2's main.py legitimately needs to import `server.dialog.manager` or `server.pipelines.multi_voice_tts` even at flag-off (it shouldn't — defer those imports inside the `if settings.personas_enabled:` branch).

- [ ] **Step 6: Full suite + lint**

```bash
cd server && python -m pytest -q && ruff check . && mypy
```

Expected: existing `test_session.py` and `test_ws_integration.py` still green (flag-off path). New tests green.

- [ ] **Step 7: Commit**

```bash
git add server/server/session.py server/server/main.py server/tests/test_session_phase2.py
git commit -m "feat(session): delegate to DialogManager when personas_enabled

Session takes an optional dialog_manager kwarg. When set (Phase 2
path), text turns route to manager.handle_turn — speaker-tagged
llm.token, dispatch.plan, voice-swap TTS. When None (default),
behaviour is byte-for-byte unchanged.

main.py lifespan constructs the registry + dispatcher + MultiVoiceTTS
+ llm_factory ONCE when personas_enabled, and a per-session
DialogManager when the WS connects. Imports are lazy so the dormancy
regression guard keeps passing."
```

---

## Task 6: Phase 2 smoke + README update

**Files:**
- Create: `server/tests/test_phase2_smoke.py`
- Modify: `server/README.md`

- [ ] **Step 1: Write the Phase 2 smoke test**

Create `server/tests/test_phase2_smoke.py`:

```python
"""Phase 2 smoke — DialogManager + Session compose end-to-end with mocks.

Doesn't touch the network; uses fake clients. Confirms the WS message
sequence for a single-segment turn and a multi-segment handoff turn.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from server.dialog.manager import DialogManager
from server.dialog.types import Plan, Segment
from server.personas.registry import PersonaRegistry


class _FakeWS:
    def __init__(self) -> None:
        import json
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
```

- [ ] **Step 2: Run the smoke test**

```bash
cd server && python -m pytest tests/test_phase2_smoke.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 3: Full suite + lint**

```bash
cd server && python -m pytest -q && ruff check . && mypy
```

Expected: green / clean.

- [ ] **Step 4: Update `server/README.md`**

Edit `server/README.md`. Replace the existing "Multi-model support (Phase 1 — foundations, behind a flag)" section header to "Multi-model support (Phase 2 — dialog manager + chat, behind a flag)" and append after the existing Phase 1 quick check:

```markdown
### Phase 2 — multi-persona chat

With `JARVIS_PERSONAS_ENABLED=true` and both API keys set, the Session
delegates each turn to a `DialogManager`. Jarvis (Claude) and Pepper
(OpenAI) take turns within a single utterance via Dispatcher-planned
segments; each segment streams in its persona's voice.

Quick manual check:

```bash
ANTHROPIC_API_KEY=sk-ant-... \
OPENAI_API_KEY=sk-... \
JARVIS_PERSONAS_ENABLED=true \
JARVIS_TTS_ENGINE=edge \
uvicorn server.main:app --port 8000

# In another terminal:
python -m server.cli_test --text "Pepper, add a test for parse_prefix"
# Expect: dispatch.plan in the WS log; llm.token events with speaker=pepper;
# tts.sentence events with speaker=pepper; voice = en-US-AriaNeural.

python -m server.cli_test --text "Design and then implement a CSV exporter"
# Expect: 2-segment plan (Jarvis design, Pepper implement); voice swaps
# between Christopher and Aria mid-turn.
```

Phase 2 ships chat-only — `mode=codex_agent` segments degrade to chat
with a warning. The Codex CLI agent lands in Phase 3.
```

- [ ] **Step 5: Commit**

```bash
git add server/tests/test_phase2_smoke.py server/README.md
git commit -m "docs(personas): Phase 2 smoke + README update

Smoke confirms single-segment and 2-segment handoff flows end-to-end
with fake backends, and that the new Phase 2 modules stay dormant
when the flag is off. README adds the Phase 2 quick-check recipe."
```

- [ ] **Step 6: Push the branch + open PR**

```bash
git push -u origin claude/multi-model-support-phase-2
```

Then open a PR titled "Phase 2: dialog manager + chat-only multi-persona" against `main`.

---

## Phase 2 acceptance checklist

Before merge:

- [ ] `python -m pytest -q` from `server/` green.
- [ ] `ruff check .` clean.
- [ ] `mypy` no NEW errors.
- [ ] `JARVIS_PERSONAS_ENABLED=false` (the default) preserves today's behaviour. No existing test was modified.
- [ ] `test_phase2_dormant_when_flag_off` passes — `server.dialog.manager`, `server.pipelines.multi_voice_tts` are NOT auto-imported with the flag off.
- [ ] Both CI checks (`server`, `web`) pass on the PR.
- [ ] Codex review (if any P1/P2 comments fired) addressed.
- [ ] PR description references this plan + spec.

---

## Phase 2 → Phase 3 decision log

To be filled in as Phase 2 lands. Suggested format:

```
- Task N (<file>): <decision worth carrying forward>
```

Initial entries (populated by the implementer):

- _(empty — fill in during execution)_

---

*End of Phase 2 implementation plan.*

"""Rule-based Dispatcher — Phase 1 (no LLM call).

This is the fallback path even after the LLM-backed Dispatcher lands in
Phase 2: when the Anthropic Haiku call fails or the JSON is malformed,
the system falls back here (spec §5.7). Functional, just dumber.

Decision rules (in priority order) — spec §5.3:
  1. Slash prefix wins (pins speaker + tier + mode for that segment).
  2. Name-at-start wins (pins speaker for that segment).
  3. Sticky speaker (last_speaker, reset after 5-minute gap).
  4. Default → Jarvis at the `fast` tier in `chat` mode.

Phase 1 never emits a multi-segment plan — handoffs require the LLM-backed
dispatcher introduced in Phase 2.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import anthropic
from pydantic import ValidationError

from server.dialog.types import (
    DialogState,
    HandoffStyle,
    PersonaId,
    Plan,
    Segment,
    SegmentMode,
    Tier,
)

logger = logging.getLogger(__name__)

# ── Slash prefix maps ─────────────────────────────────────────────────

# Jarvis-controlled prefixes (within the Anthropic family).
_JARVIS_PREFIX_TIER: dict[str, Tier] = {
    "/haiku": "fast",
    "/sonnet": "balanced",
    "/opus": "deep",
}

# Pepper-controlled prefixes (within the OpenAI family).
# `/codex` additionally promotes to mode=codex_agent.
_PEPPER_PREFIX_TIER: dict[str, tuple[Tier, SegmentMode]] = {
    "/gpt": ("balanced", "chat"),
    "/codex": ("deep", "codex_agent"),
}

# Name-at-start detection: name followed by space, comma, or end-of-utterance.
_NAME_RE = re.compile(r"^\s*(jarvis|pepper)\b\s*[,:]?\s*", re.IGNORECASE)


# 5-minute stickiness window.
_STICKY_WINDOW_SECONDS = 300.0


@dataclass(frozen=True)
class _SlashMatch:
    speaker: PersonaId
    tier: Tier
    mode: SegmentMode
    stripped_content: str


def _detect_slash(text: str) -> _SlashMatch | None:
    head, _, rest = text.partition(" ")
    head = head.lower()
    if head in _JARVIS_PREFIX_TIER:
        return _SlashMatch(
            speaker="jarvis",
            tier=_JARVIS_PREFIX_TIER[head],
            mode="chat",
            stripped_content=rest.lstrip(),
        )
    if head in _PEPPER_PREFIX_TIER:
        tier, mode = _PEPPER_PREFIX_TIER[head]
        return _SlashMatch(
            speaker="pepper",
            tier=tier,
            mode=mode,
            stripped_content=rest.lstrip(),
        )
    return None


def _detect_name(text: str) -> tuple[PersonaId, str] | None:
    m = _NAME_RE.match(text)
    if not m:
        return None
    name = m.group(1).lower()
    speaker: PersonaId = "jarvis" if name == "jarvis" else "pepper"
    stripped = text[m.end():].lstrip()
    return speaker, stripped


def _sticky_active(state: DialogState, now_ts: float) -> bool:
    return (
        state.last_speaker is not None
        and state.last_turn_ts is not None
        and (now_ts - state.last_turn_ts) <= _STICKY_WINDOW_SECONDS
    )


def _truncate_intent(content: str, max_len: int = 200) -> str:
    content = content.strip()
    if not content:
        return "(empty utterance)"
    if len(content) <= max_len:
        return content
    return content[: max_len - 1] + "…"


class RuleBasedDispatcher:
    """Deterministic Dispatcher — no LLM calls.

    Always emits a single-segment Plan in Phase 1. Multi-segment handoffs
    require the LLM-backed Dispatcher introduced in Phase 2.
    """

    def __init__(self, *, default_speaker: PersonaId = "jarvis") -> None:
        self._default_speaker = default_speaker

    def dispatch(
        self,
        text: str,
        state: DialogState,
        *,
        now_ts: float | None = None,
        handoff_style: HandoffStyle | None = None,
    ) -> Plan:
        """Return a Plan for the given utterance + state.

        `now_ts` overrides `time.time()` for sticky-speaker tests.
        `handoff_style` is ignored in Phase 1 (no multi-segment plans).
        """
        now = now_ts if now_ts is not None else time.time()
        rationale_parts: list[str] = []
        speaker: PersonaId
        tier: Tier = "fast"
        mode: SegmentMode = "chat"
        content: str = text

        slash = _detect_slash(text)
        name_match = _detect_name(text)

        if slash is not None:
            speaker = slash.speaker
            tier = slash.tier
            mode = slash.mode
            # The slash prefix's stripped content becomes the intent; the
            # full original utterance still flows through to the LLM (it
            # sees the slash). Intent is the human-readable summary.
            content = slash.stripped_content if slash.stripped_content else text
            rationale_parts.append(f"slash-prefix dispatch to {speaker}")
        elif name_match is not None:
            speaker, content = name_match
            rationale_parts.append(f"name-at-start dispatch to {speaker}")
        elif _sticky_active(state, now):
            assert state.last_speaker is not None
            speaker = state.last_speaker
            rationale_parts.append(f"sticky to {speaker} within {int(_STICKY_WINDOW_SECONDS)}s")
        else:
            speaker = self._default_speaker
            rationale_parts.append(f"default to {speaker}")

        segment = Segment(
            speaker=speaker,
            tier=tier,
            mode=mode,
            intent=_truncate_intent(content),
            handoff_style=None,
        )
        return Plan(
            segments=[segment],
            rationale="; ".join(rationale_parts),
        )


# ── LLM-backed dispatcher (Phase 2) ────────────────────────────────────

# Domain-crossing keywords that disable the fast path (spec §5.4).
_DOMAIN_KEYWORDS = frozenset(
    {
        "but also",
        "and then",
        "code",
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

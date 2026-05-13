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

import re
import time
from dataclasses import dataclass

from server.dialog.types import (
    DialogState,
    HandoffStyle,
    PersonaId,
    Plan,
    Segment,
    SegmentMode,
    Tier,
)

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

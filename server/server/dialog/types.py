"""Dialog primitive types.

Spec anchors:
- §3 (per-turn flow)
- §5.2 (Plan / Segment output schema)
- §6.2 (DialogState — what the persona / dispatcher receives)
- §8.2 (Outcome signals)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, NonNegativeInt


PersonaId = Literal["jarvis", "pepper"]
Tier = Literal["fast", "balanced", "deep"]
SegmentMode = Literal["chat", "codex_agent"]
HandoffStyle = Literal["flat", "soft"]
FeedbackSignal = Literal["positive", "negative"]
AgentStatus = Literal["ok", "failed", "cancelled"]


class Segment(BaseModel):
    """One unit of speech in a Plan.

    `handoff_style` is set only on non-terminal segments and tells the
    persona to end with a `[handoff:<persona>:<reason>]` tag (see spec §4.4).
    """

    model_config = {"extra": "forbid"}

    speaker: PersonaId
    tier: Tier
    mode: SegmentMode
    intent: str = Field(min_length=1, max_length=200)
    handoff_style: HandoffStyle | None = None


class Plan(BaseModel):
    """A Dispatcher's per-turn decision: an ordered list of Segments.

    1 to 3 segments, hard-capped (spec §5.3.5). `rationale` is one sentence
    logged for the learning loop (spec §8).
    """

    model_config = {"extra": "forbid"}

    segments: list[Segment] = Field(min_length=1, max_length=3)
    rationale: str = Field(min_length=1, max_length=400)


class TurnRef(BaseModel):
    """A compact reference to a prior turn for DialogState.recent_turns."""

    model_config = {"extra": "forbid"}

    speaker: PersonaId
    user_text: str = Field(max_length=2000)
    assistant_text: str = Field(max_length=4000)


class DialogState(BaseModel):
    """Snapshot the Dispatcher reads on every turn (spec §5.1)."""

    model_config = {"extra": "forbid"}

    last_speaker: PersonaId | None = None
    last_turn_ts: float | None = None
    recent_turns: list[TurnRef] = Field(default_factory=list, max_length=3)
    warmth_budget: NonNegativeInt = 0


class Outcome(BaseModel):
    """Per-turn observed outcome signals (spec §8.2).

    Stored as `outcome_json` in the dispatch_log table. Defaults are the
    "nothing happened yet" state; FeedbackLogger fills in fields as the
    turn progresses and finalizes after `llm.end`.
    """

    model_config = {"extra": "forbid"}

    completed: bool = False
    user_interrupted_at: NonNegativeInt | None = None
    next_turn_readdressed: PersonaId | None = None
    agent_status: AgentStatus | None = None
    auto_approved: NonNegativeInt = 0
    denied: NonNegativeInt = 0
    latency_ms: float | None = None
    tokens_in: NonNegativeInt = 0
    tokens_out: NonNegativeInt = 0
    cost_est: float = 0.0
    explicit_feedback: FeedbackSignal | None = None

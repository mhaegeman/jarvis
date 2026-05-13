"""Tests for server.dialog.types — Segment / Plan / Outcome / DialogState."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from server.dialog.types import DialogState, Outcome, Plan, Segment, TurnRef


# ─── Segment ──────────────────────────────────────────────────────────


def test_segment_minimal() -> None:
    s = Segment(
        speaker="jarvis",
        tier="fast",
        mode="chat",
        intent="say hello",
    )
    assert s.speaker == "jarvis"
    assert s.tier == "fast"
    assert s.mode == "chat"
    assert s.handoff_style is None


def test_segment_rejects_unknown_speaker() -> None:
    with pytest.raises(ValidationError):
        Segment(speaker="bob", tier="fast", mode="chat", intent="x")


def test_segment_rejects_unknown_tier() -> None:
    with pytest.raises(ValidationError):
        Segment(speaker="jarvis", tier="ultra", mode="chat", intent="x")


def test_segment_rejects_unknown_mode() -> None:
    with pytest.raises(ValidationError):
        Segment(speaker="pepper", tier="fast", mode="rpc", intent="x")


def test_segment_handoff_style_accepted() -> None:
    s = Segment(
        speaker="jarvis", tier="balanced", mode="chat", intent="plan",
        handoff_style="soft",
    )
    assert s.handoff_style == "soft"


def test_segment_codex_agent_mode_requires_pepper() -> None:
    # Soft check: codex_agent mode is only meaningful for pepper. The model
    # does not enforce this at the pydantic level (Dispatcher does), but the
    # type itself accepts it for jarvis so we can roundtrip historical plans.
    s = Segment(speaker="jarvis", tier="fast", mode="codex_agent", intent="x")
    assert s.mode == "codex_agent"


# ─── Plan ─────────────────────────────────────────────────────────────


def test_plan_one_segment() -> None:
    p = Plan(
        segments=[Segment(speaker="jarvis", tier="fast", mode="chat", intent="hi")],
        rationale="trivial greeting",
    )
    assert len(p.segments) == 1


def test_plan_caps_at_three_segments() -> None:
    s = Segment(speaker="jarvis", tier="fast", mode="chat", intent="x")
    with pytest.raises(ValidationError):
        Plan(segments=[s, s, s, s], rationale="too many")


def test_plan_rejects_empty_segments() -> None:
    with pytest.raises(ValidationError):
        Plan(segments=[], rationale="empty")


def test_plan_json_roundtrip() -> None:
    p = Plan(
        segments=[
            Segment(speaker="jarvis", tier="balanced", mode="chat", intent="design",
                    handoff_style="soft"),
            Segment(speaker="pepper", tier="deep", mode="codex_agent", intent="implement"),
        ],
        rationale="design then implement",
    )
    data = json.loads(p.model_dump_json())
    p2 = Plan.model_validate(data)
    assert p2 == p


# ─── Outcome ──────────────────────────────────────────────────────────


def test_outcome_defaults() -> None:
    o = Outcome()
    assert o.completed is False
    assert o.user_interrupted_at is None
    assert o.next_turn_readdressed is None
    assert o.agent_status is None
    assert o.latency_ms is None
    assert o.tokens_in == 0
    assert o.tokens_out == 0
    assert o.cost_est == 0.0
    assert o.explicit_feedback is None


def test_outcome_explicit_feedback_constrained() -> None:
    with pytest.raises(ValidationError):
        Outcome(explicit_feedback="meh")  # type: ignore[arg-type]
    Outcome(explicit_feedback="positive")
    Outcome(explicit_feedback="negative")


def test_outcome_user_interrupted_segment_idx() -> None:
    o = Outcome(user_interrupted_at=1)
    assert o.user_interrupted_at == 1
    with pytest.raises(ValidationError):
        Outcome(user_interrupted_at=-1)


# ─── DialogState ──────────────────────────────────────────────────────


def test_dialog_state_defaults() -> None:
    d = DialogState()
    assert d.last_speaker is None
    assert d.last_turn_ts is None
    assert d.recent_turns == []
    assert d.warmth_budget == 0


def test_dialog_state_turn_ref_shape() -> None:
    d = DialogState(
        last_speaker="pepper",
        last_turn_ts=1700000000.0,
        recent_turns=[
            TurnRef(speaker="pepper", user_text="add a test", assistant_text="done."),
        ],
        warmth_budget=1,
    )
    assert d.last_speaker == "pepper"
    assert len(d.recent_turns) == 1
    assert d.recent_turns[0].speaker == "pepper"


def test_dialog_state_recent_turns_capped() -> None:
    refs = [
        TurnRef(speaker="jarvis", user_text=f"q{i}", assistant_text=f"a{i}")
        for i in range(10)
    ]
    with pytest.raises(ValidationError):
        DialogState(recent_turns=refs)  # cap is 3 per spec §5.1

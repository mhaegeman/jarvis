"""Tests for server.dialog.dispatcher — RuleBasedDispatcher."""

from __future__ import annotations

from server.dialog.dispatcher import RuleBasedDispatcher
from server.dialog.types import DialogState

# ─── Name-at-start (spec §5.3.1) ──────────────────────────────────────


def test_name_at_start_jarvis_routes_to_jarvis() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("Jarvis, what's on today?", DialogState())
    assert len(plan.segments) == 1
    assert plan.segments[0].speaker == "jarvis"
    assert plan.segments[0].intent.startswith("what's on today")


def test_name_at_start_pepper_routes_to_pepper() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("Pepper, refactor X.", DialogState())
    assert plan.segments[0].speaker == "pepper"


def test_name_at_start_case_insensitive() -> None:
    d = RuleBasedDispatcher()
    assert d.dispatch("pepper, ok", DialogState()).segments[0].speaker == "pepper"
    assert d.dispatch("PEPPER ok", DialogState()).segments[0].speaker == "pepper"


def test_name_at_start_requires_punctuation_or_space() -> None:
    # "Peppermint" should NOT route to Pepper.
    d = RuleBasedDispatcher()
    plan = d.dispatch("peppermint candy", DialogState(last_speaker="jarvis"))
    assert plan.segments[0].speaker == "jarvis"


# ─── Slash prefix (spec §5.3.2) ───────────────────────────────────────


def test_slash_opus_pins_jarvis_deep() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/opus design the schema", DialogState())
    seg = plan.segments[0]
    assert seg.speaker == "jarvis"
    assert seg.tier == "deep"


def test_slash_sonnet_pins_jarvis_balanced() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/sonnet compare A and B", DialogState())
    seg = plan.segments[0]
    assert seg.speaker == "jarvis"
    assert seg.tier == "balanced"


def test_slash_haiku_pins_jarvis_fast() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/haiku quick question", DialogState())
    assert plan.segments[0].tier == "fast"


def test_slash_codex_pins_pepper_codex_agent_deep() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/codex add a test for parse_prefix", DialogState())
    seg = plan.segments[0]
    assert seg.speaker == "pepper"
    assert seg.tier == "deep"
    assert seg.mode == "codex_agent"


def test_slash_gpt_pins_pepper_chat_balanced() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/gpt explain async", DialogState())
    seg = plan.segments[0]
    assert seg.speaker == "pepper"
    assert seg.tier == "balanced"
    assert seg.mode == "chat"


def test_unknown_slash_passes_through_to_default() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/banana split", DialogState(last_speaker="jarvis"))
    assert plan.segments[0].speaker == "jarvis"
    # Intent preserves the raw slash for the LLM to react to literally.
    assert "/banana" in plan.segments[0].intent


# ─── Sticky speaker (spec §5.5) ───────────────────────────────────────


def test_sticky_speaker_carries_when_unnamed() -> None:
    d = RuleBasedDispatcher()
    state = DialogState(last_speaker="pepper", last_turn_ts=1000.0)
    # 60s after the prior turn — well inside the 5-minute window.
    plan = d.dispatch("now run the tests", state, now_ts=1000.0 + 60.0)
    assert plan.segments[0].speaker == "pepper"


def test_sticky_resets_after_five_minute_gap() -> None:
    d = RuleBasedDispatcher()
    state = DialogState(last_speaker="pepper", last_turn_ts=1000.0)
    plan = d.dispatch("hello", state, now_ts=1000.0 + 301.0)  # 5min 1s gap
    # Falls back to the default (Jarvis is host).
    assert plan.segments[0].speaker == "jarvis"


def test_sticky_overridden_by_name_at_start() -> None:
    d = RuleBasedDispatcher()
    state = DialogState(last_speaker="pepper", last_turn_ts=1000.0)
    plan = d.dispatch("Jarvis, summary please", state, now_ts=1000.0 + 30.0)
    assert plan.segments[0].speaker == "jarvis"


def test_sticky_overridden_by_slash_prefix() -> None:
    d = RuleBasedDispatcher()
    state = DialogState(last_speaker="pepper", last_turn_ts=1000.0)
    plan = d.dispatch("/opus design X", state, now_ts=1000.0 + 30.0)
    assert plan.segments[0].speaker == "jarvis"


# ─── Default (no name, no slash, no sticky) ───────────────────────────


def test_default_routes_to_jarvis() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("hi there", DialogState())
    assert plan.segments[0].speaker == "jarvis"


def test_default_tier_fast() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("hi", DialogState())
    assert plan.segments[0].tier == "fast"


# ─── Plan invariants ──────────────────────────────────────────────────


def test_plan_always_has_at_least_one_segment() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("hi", DialogState())
    assert len(plan.segments) >= 1


def test_plan_capped_at_three_segments() -> None:
    # The rule-based dispatcher never emits >1 segment in Phase 1 — it has
    # no LLM to decide handoffs. This is documented behaviour; the LLM-backed
    # Dispatcher in Phase 2 will introduce multi-segment plans.
    d = RuleBasedDispatcher()
    plan = d.dispatch("design and then implement everything", DialogState())
    assert len(plan.segments) == 1


def test_rationale_non_empty() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("hi", DialogState())
    assert plan.rationale.strip() != ""


# ─── Empty / whitespace input ─────────────────────────────────────────


def test_empty_utterance_routes_to_default_speaker() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("   ", DialogState())
    assert plan.segments[0].speaker == "jarvis"
    # Intent falls back to a non-empty placeholder so Plan validation passes.
    assert plan.segments[0].intent.strip() != ""

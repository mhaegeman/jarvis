"""Sanity checks on the memory dataclasses."""

from server.memory.types import Fact, RecentSummaryMeta, SessionSummary, Turn


def test_turn_is_frozen() -> None:
    t = Turn(id=1, session_id="s1", ts="2026-05-08T10:00:00Z", role="user", content="hi")
    assert t.role == "user"
    try:
        t.content = "nope"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Turn should be frozen")


def test_fact_construction() -> None:
    f = Fact(key="lang", value="TypeScript")
    assert (f.key, f.value) == ("lang", "TypeScript")


def test_session_summary_optional_ended_at() -> None:
    s = SessionSummary(
        session_id="s1",
        started_at="2026-05-08T10:00:00Z",
        ended_at=None,
        summary="Discussed deploys.",
    )
    assert s.ended_at is None


def test_recent_summary_meta() -> None:
    m = RecentSummaryMeta(summary="hi", refreshed_at="2026-05-08T10:00:00Z", last_turn_id=42)
    assert m.last_turn_id == 42

"""Canned conversation scenarios for Phase 1 mock pipelines.

The mock LLM picks one based on coarse keyword matching of the user's text;
falls back to a default on no match.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Scenario:
    keywords: tuple[str, ...]
    transcription: str
    reply: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        keywords=("brief", "today", "agenda"),
        transcription="Brief me on today.",
        reply=(
            "Two interviews on your calendar. "
            "The playtesting deck is ready for review. "
            "Three slides flagged for your attention. "
            "Otherwise, your morning is clear."
        ),
    ),
    Scenario(
        keywords=("research", "notes", "summarize", "summary"),
        transcription="Summarize yesterday's research notes.",
        reply=(
            "Eight key insights synthesized. "
            "The strongest pattern: testers consistently abandon at the second tutorial gate. "
            "I drafted a one-paragraph summary in your inbox."
        ),
    ),
    Scenario(
        keywords=("playtest", "review", "deck"),
        transcription="What's the status of the playtest review?",
        reply=(
            "Slides ready. "
            "Three need your review before sending. "
            "The remaining content is approved by Harsh."
        ),
    ),
    Scenario(
        keywords=("cancel", "meeting"),
        transcription="Cancel my eleven o'clock.",
        reply="Done. Apologies sent. Calendar slot reopened. Your morning is now fully clear.",
    ),
    Scenario(
        keywords=("inbox", "email", "urgent"),
        transcription="Anything urgent in my inbox?",
        reply=(
            "One. The grant deadline moved up by a week. "
            "I drafted a response asking for clarification. "
            "Want me to send it?"
        ),
    ),
)


DEFAULT_REPLY = "I'm not sure I understood, but I'm listening."


def pick_scenario(user_text: str) -> Scenario | None:
    """Return the first scenario whose keyword appears in user_text (case-insensitive)."""
    needle = user_text.lower()
    for s in SCENARIOS:
        if any(kw in needle for kw in s.keywords):
            return s
    return None

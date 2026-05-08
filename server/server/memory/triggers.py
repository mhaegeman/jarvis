"""Phrase-level detection of 'user is asking JARVIS to consult memory'.

Phrase-level (not single-word) by design — bare 'remember' would catch
'I'll remember to call mom'. Trailing-space patterns ('recall ') keep
'recalled' from matching. Tweak the constant; tests in
test_memory_triggers.py lock the behaviour.
"""

from __future__ import annotations

_TRIGGER_PHRASES: tuple[str, ...] = (
    "do you remember",
    "did i mention",
    "did i tell you",
    "you said",
    "you mentioned",
    "you told me",
    "we discussed",
    "we covered",
    "we talked about",
    "did we discuss",
    "earlier you",
    "last time we",
    "last time you",
    "what do you know about",
    "what's my",
    "whats my",
    "what are my",
    "what did i",
    "what did we",
    "recall ",
    "remember when",
)


def is_memory_query(text: str) -> bool:
    """True iff `text` looks like a request to consult memory."""
    s = text.lower()
    return any(p in s for p in _TRIGGER_PHRASES)

"""Phrase matrix for is_memory_query.

True positives must match. False positives marked 'accepted' may match
(documented trade-off). False positives marked 'must NOT match' are
regression locks against naively expanding _TRIGGER_PHRASES.
"""

import pytest

from server.memory.triggers import is_memory_query


@pytest.mark.parametrize(
    "text",
    [
        "Do you remember when we discussed the deploy?",
        "did i mention the friday rule?",
        "Did I tell you about Wednesday's meeting?",
        "You said TypeScript was preferred.",
        "you mentioned a rollback last week",
        "you told me to prefer Vite",
        "we discussed this on Tuesday",
        "we covered the API design earlier",
        "we talked about deployments",
        "did we discuss the gate timeline?",
        "Earlier you said something about caching.",
        "last time we talked about this",
        "last time you suggested a redo",
        "What do you know about my project?",
        "what's my preferred language?",
        "whats my timezone again",
        "what are my open tasks",
        "what did i say about Friday?",
        "what did we decide on the schema?",
        "Recall the last release notes.",
        "remember when we shipped α?",
    ],
)
def test_true_positives(text: str) -> None:
    assert is_memory_query(text), f"should trigger: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "I'll remember to call mom",
        "I recalled it later",
        "Remember me to your mother",
        "I want to remember this",
        "Remind me later",
        "Tell me a joke",
        "What's the weather?",
    ],
)
def test_must_not_match(text: str) -> None:
    assert not is_memory_query(text), f"should NOT trigger: {text!r}"

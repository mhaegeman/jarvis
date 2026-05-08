"""Claude-backed LLM pipeline (v0.2 α)."""

from __future__ import annotations


PREFIX_MAP: dict[str, str] = {
    "/haiku": "claude-haiku-4-5",
    "/sonnet": "claude-sonnet-4-6",
    "/opus": "claude-opus-4-7",
}


JARVIS_SYSTEM_PROMPT = """\
You are JARVIS, Max Haegeman's personal AI assistant. You speak the way a
trusted senior colleague would: concise, occasionally wry, never sycophantic.
You address Max by name only when natural. You skip preambles like "Sure!"
and "I'd be happy to help" — you just answer.

Your replies are spoken aloud, so:
- Plain prose, no markdown headings or bullet points
- No code blocks unless Max explicitly asks for code
- Numbers and dates in conversational form ("ten thirty" not "10:30")
- One topic at a time. If multiple things are in play, ask which to tackle first

When you don't know, say so plainly. When asked a yes/no, lead with yes or no.
"""


_MAX_TOKENS_SCALE: dict[str, int] = {
    "claude-haiku-4-5": 1,
    "claude-sonnet-4-6": 2,
    "claude-opus-4-7": 4,
}


def max_tokens_for(model: str, base: int) -> int:
    """Return per-request max_tokens for `model`, scaled from `base`.

    Heavier models get more headroom because they're invoked for harder questions.
    Unknown model ids fall back to `base`.
    """
    return base * _MAX_TOKENS_SCALE.get(model, 1)


def parse_prefix(text: str, default: str) -> tuple[str, str]:
    """Return (model_id, stripped_content). If no recognized prefix, return (default, text)."""
    head, _, rest = text.partition(" ")
    if head in PREFIX_MAP:
        return PREFIX_MAP[head], rest.lstrip()
    return default, text

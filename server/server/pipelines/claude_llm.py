"""Claude-backed LLM pipeline (v0.2 α)."""

from __future__ import annotations


PREFIX_MAP: dict[str, str] = {
    "/haiku": "claude-haiku-4-5",
    "/sonnet": "claude-sonnet-4-6",
    "/opus": "claude-opus-4-7",
}


def parse_prefix(text: str, default: str) -> tuple[str, str]:
    """Return (model_id, stripped_content). If no recognized prefix, return (default, text)."""
    head, _, rest = text.partition(" ")
    if head in PREFIX_MAP:
        return PREFIX_MAP[head], rest.lstrip()
    return default, text

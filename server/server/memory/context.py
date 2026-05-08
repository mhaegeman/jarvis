"""Builds the per-turn extra_context blob fed to the LLM.

Two paths:
- default(store)         — small "Background: <recent_summary>" only
- full(store, user_text) — full blob: background + facts + recent sessions + matched turns

Section caps are enforced here, not in the store.
"""

from __future__ import annotations

import re

from .store import MemoryStore
from .types import Turn

FACTS_CAP_DEFAULT = 50
DIGEST_SESSIONS_DEFAULT = 10
SEARCH_CAP_DEFAULT = 5


def _query_tokens(user_text: str) -> list[str]:
    s = re.sub(r"[^\w\s]", " ", user_text.lower())
    tokens = [t for t in s.split() if len(t) > 3]
    tokens.sort(key=len, reverse=True)
    return tokens[:3]


class MemoryContext:
    @staticmethod
    async def default(store: MemoryStore) -> str:
        summary = await store.get_recent_summary()
        if not summary:
            return ""
        return f"Background (recent conversation summary):\n{summary}"

    @staticmethod
    async def full(
        store: MemoryStore,
        user_text: str,
        *,
        facts_cap: int = FACTS_CAP_DEFAULT,
        digest_sessions: int = DIGEST_SESSIONS_DEFAULT,
        search_cap: int = SEARCH_CAP_DEFAULT,
    ) -> str:
        sections: list[str] = []

        recent = await store.get_recent_summary()
        if recent:
            sections.append(f"Background (recent conversation summary):\n{recent}")

        facts = await store.get_facts()
        if facts:
            shown = list(facts.items())[:facts_cap]
            lines = "\n".join(f"- {k}: {v}" for k, v in shown)
            sections.append(f"What I know about you (from prior conversations):\n{lines}")

        summaries = await store.list_recent_summaries(limit=digest_sessions)
        if summaries:
            lines = "\n".join(f"- {s.started_at}: {s.summary}" for s in summaries)
            sections.append(f"Recent sessions (most recent first):\n{lines}")

        # Verbatim search across all turns.
        matches: list[Turn] = []
        for tok in _query_tokens(user_text):
            matches = await store.search_turns(tok, limit=search_cap)
            if matches:
                break
        if matches:
            lines = "\n".join(
                f"- [{t.role}, {t.ts[:10]}] \"{t.content}\"" for t in matches[:search_cap]
            )
            sections.append(f"Possibly relevant past exchanges:\n{lines}")

        return "\n\n".join(sections)

"""ProfileRefresher — the learning loop.

Spec anchors: §8.3 (refresher), §8.4 (safety rails).

Trigger: every N turns OR explicit invocation.
Steps:
  1. Read recent dispatch_log rows + current profiles.
  2. Build structured prompt (haiku tool-use) with profiles + log.
  3. Validate output (~250-word cap, min_length guard).
  4. Apply bounded-change rule: token-similarity to old profile;
     if <60% similarity, blend at 50/50 instead.
  5. Call PersonaRegistry.update_profile (re-validates via pydantic).
  6. Update personas table: profile, last_refresh, refresh_count++.
"""

from __future__ import annotations

import difflib
import json
import logging
import time
from typing import Any

import aiosqlite
from pydantic import BaseModel, Field, ValidationError

from server.dialog.feedback import FeedbackLogger
from server.personas.registry import PersonaRegistry
from server.personas.seed import Warmth, build_jarvis_seed, build_pepper_seed

log = logging.getLogger(__name__)


# ── Structured output schema ──────────────────────────────────────────────


class _RefreshOutput(BaseModel):
    jarvis_profile: str = Field(min_length=10, max_length=1800)
    pepper_profile: str = Field(min_length=10, max_length=1800)
    summary: str = Field(min_length=1, max_length=400)


_REFRESH_TOOL = {
    "name": "emit_refresh",
    "description": (
        "Emit updated specialty profiles for Jarvis and Pepper based on "
        "the recent conversation log. Keep profiles concise (~200 words). "
        "Preserve the core role of each persona. Include a one-sentence summary "
        "of what changed and why."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "jarvis_profile": {
                "type": "string",
                "minLength": 10,
                "maxLength": 1800,
                "description": "Updated specialty profile for Jarvis (strategy/conversational).",
            },
            "pepper_profile": {
                "type": "string",
                "minLength": 10,
                "maxLength": 1800,
                "description": "Updated specialty profile for Pepper (code/dev).",
            },
            "summary": {
                "type": "string",
                "minLength": 1,
                "maxLength": 400,
                "description": "One sentence explaining what changed and why.",
            },
        },
        "required": ["jarvis_profile", "pepper_profile", "summary"],
        "additionalProperties": False,
    },
}


_REFRESHER_SYSTEM_PROMPT = """\
You are the learning-loop refresher for a two-persona AI system.
You receive:
  1. The current specialty profiles for Jarvis and Pepper.
  2. The last 100 turns of dispatch log showing what questions were asked,
     which persona answered, and the outcomes (completion, interruptions,
     re-addresses to the other persona).

Your job is to rewrite each specialty profile to better reflect what the user
actually uses each persona for, based on the evidence in the log.

Rules:
- Keep each profile short (~200 words max).
- Do NOT change the fundamental role of each persona (Jarvis = strategy/conversation,
  Pepper = code/dev). Only adjust the emphasis and specifics.
- If there is very little log data, keep profiles close to the originals.
- Respond ONLY by invoking the emit_refresh tool.
"""


def _blend_profiles(old_text: str, new_text: str, max_chars: int = 1800) -> str:
    """50/50 blend for bounded-change safety rail (spec §8.4).

    Concatenates old + new separated by a blank line, then trims to max_chars.
    The result preserves the old content verbatim in the first half, which is
    the safety guarantee: the persona can't drift completely in one refresh.
    """
    blended = f"{old_text}\n\n{new_text}"
    return blended[:max_chars]


def _similarity(a: str, b: str) -> float:
    """SequenceMatcher-based similarity ratio (0.0 – 1.0)."""
    return difflib.SequenceMatcher(None, a, b).ratio()


class ProfileRefresher:
    """Scheduled async task: refreshes persona specialty profiles every N turns.

    Usage:
        refresher = ProfileRefresher(registry=..., feedback=..., client=..., db_path=...)
        result = await refresher.refresh()   # run one refresh cycle
        await refresher.reset()              # restore seed profiles
    """

    def __init__(
        self,
        *,
        registry: PersonaRegistry,
        feedback: FeedbackLogger,
        client: Any,
        db_path: str,
        model: str = "claude-haiku-4-5",
        max_tokens: int = 1024,
        bounded_change_threshold: float = 0.40,  # >40% drift → blend
        warmth: Warmth = "subtle",
    ) -> None:
        self._registry = registry
        self._feedback = feedback
        self._client = client
        self._db_path = db_path
        self._model = model
        self._max_tokens = max_tokens
        self._threshold = bounded_change_threshold
        self._warmth: Warmth = warmth
        # In-memory tracking for the GET /personas endpoint and state.snapshot.
        # Keyed by persona id ("jarvis", "pepper").
        self._last_refresh_ts: dict[str, float] = {}
        self._refresh_count: dict[str, int] = {}

    async def refresh(self) -> dict[str, Any]:
        """Run one refresh cycle. Returns a status dict."""
        recent_rows = await self._feedback.recent(limit=100)
        if not recent_rows:
            return {"status": "skipped", "reason": "no turns"}

        jarvis_current = self._registry.get("jarvis").specialty_profile
        pepper_current = self._registry.get("pepper").specialty_profile

        # Build the user message with log + current profiles.
        log_text = json.dumps(recent_rows, indent=None)
        user_msg = (
            f"Current Jarvis profile:\n{jarvis_current}\n\n"
            f"Current Pepper profile:\n{pepper_current}\n\n"
            f"Recent dispatch log ({len(recent_rows)} rows):\n{log_text}"
        )

        # Call LLM with structured output.
        try:
            parsed = await self._call_llm(user_msg)
        except _RefreshOutputError as exc:
            log.warning("ProfileRefresher LLM output invalid: %s", exc)
            return {"status": "error", "reason": str(exc)}

        # Apply bounded-change safety rail (spec §8.4).
        j_blended = self._apply_bounded_change(jarvis_current, parsed.jarvis_profile)
        p_blended = self._apply_bounded_change(pepper_current, parsed.pepper_profile)

        # Write back via registry (re-validates via pydantic).
        self._registry.update_profile("jarvis", j_blended)
        self._registry.update_profile("pepper", p_blended)

        # Persist to personas table.
        await self._persist("jarvis", j_blended)
        await self._persist("pepper", p_blended)

        return {"status": "ok", "summary": parsed.summary}

    async def reset(self) -> None:
        """Restore seed profiles — wipes any learned drift."""
        jarvis = build_jarvis_seed(warmth=self._warmth)
        pepper = build_pepper_seed(warmth=self._warmth)
        self._registry.update_profile("jarvis", jarvis.specialty_profile)
        self._registry.update_profile("pepper", pepper.specialty_profile)
        await self._persist("jarvis", jarvis.specialty_profile)
        await self._persist("pepper", pepper.specialty_profile)

    # ── private ───────────────────────────────────────────────────────────

    async def _call_llm(self, user_msg: str) -> _RefreshOutput:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=_REFRESHER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            tools=[_REFRESH_TOOL],
            tool_choice={"type": "tool", "name": "emit_refresh"},
        )
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                try:
                    return _RefreshOutput.model_validate(block.input)
                except ValidationError as exc:
                    raise _RefreshOutputError(f"schema violation: {exc}") from exc
        raise _RefreshOutputError("no tool_use block in LLM response")

    def _apply_bounded_change(self, old_text: str, new_text: str) -> str:
        """Return new_text as-is, or a blend if drift exceeds the threshold."""
        ratio = _similarity(old_text, new_text)
        # ratio < (1 - threshold) means >threshold fraction changed.
        if ratio < (1.0 - self._threshold):
            log.info(
                "ProfileRefresher: bounded-change rule triggered (ratio=%.2f < %.2f), blending",
                ratio,
                1.0 - self._threshold,
            )
            return _blend_profiles(old_text, new_text)
        return new_text

    async def _persist(self, persona_id: str, profile: str) -> None:
        """Upsert a row in the personas table, incrementing refresh_count."""
        ts = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO personas (id, profile, last_refresh, refresh_count) "
                "VALUES (?, ?, ?, 1) "
                "ON CONFLICT(id) DO UPDATE SET "
                "  profile = excluded.profile, "
                "  last_refresh = excluded.last_refresh, "
                "  refresh_count = personas.refresh_count + 1",
                (persona_id, profile, ts),
            )
            await db.commit()
        # Update in-memory tracking for GET /personas + state.snapshot.
        self._last_refresh_ts[persona_id] = ts
        self._refresh_count[persona_id] = self._refresh_count.get(persona_id, 0) + 1


class _RefreshOutputError(Exception):
    """Raised when the LLM output can't be parsed into a valid _RefreshOutput."""

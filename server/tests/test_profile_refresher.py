"""Tests for server.dialog.profile_refresher.ProfileRefresher."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiosqlite
import pytest

from server.dialog.feedback import FeedbackLogger
from server.dialog.types import Outcome, Plan, Segment
from server.memory.store import MemoryStore
from server.personas.registry import PersonaRegistry
from server.personas.seed import build_jarvis_seed, build_pepper_seed

# ── Fake Anthropic client ──────────────────────────────────────────────


class _FakeBlock:
    def __init__(self, *, btype: str, input: dict[str, Any] | None = None) -> None:
        self.type = btype
        self.input = input or {}


class _FakeMessage:
    def __init__(self, content: list[_FakeBlock]) -> None:
        self.content = content


class _FakeMessages:
    def __init__(
        self,
        *,
        return_msg: _FakeMessage | None = None,
        raise_on_create: Exception | None = None,
    ) -> None:
        self.return_msg = return_msg
        self.raise_on_create = raise_on_create
        self.captured_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> _FakeMessage:
        self.captured_kwargs = kwargs
        if self.raise_on_create:
            raise self.raise_on_create
        assert self.return_msg is not None
        return self.return_msg


class _FakeClient:
    def __init__(
        self,
        *,
        return_msg: _FakeMessage | None = None,
        raise_on_create: Exception | None = None,
    ) -> None:
        self.messages = _FakeMessages(
            return_msg=return_msg, raise_on_create=raise_on_create,
        )


def _refresh_tool_use(
    jarvis_profile: str,
    pepper_profile: str,
    summary: str = "test summary",
) -> _FakeMessage:
    return _FakeMessage(
        content=[
            _FakeBlock(
                btype="tool_use",
                input={
                    "jarvis_profile": jarvis_profile,
                    "pepper_profile": pepper_profile,
                    "summary": summary,
                },
            ),
        ],
    )


# ── helpers ──────────────────────────────────────────────────────────────

_WARMTH = "off"  # keep seed profiles short + deterministic

JARVIS_SEED = build_jarvis_seed(warmth=_WARMTH).specialty_profile
PEPPER_SEED = build_pepper_seed(warmth=_WARMTH).specialty_profile


def _make_plan(speaker: str = "jarvis") -> Plan:
    return Plan(
        segments=[Segment(speaker=speaker, tier="fast", mode="chat", intent="intent")],  # type: ignore[arg-type]
        rationale="rationale",
    )


def _make_outcome() -> Outcome:
    return Outcome(completed=True, latency_ms=100.0)


async def _setup(tmp_path: Path) -> tuple[MemoryStore, FeedbackLogger, PersonaRegistry, str]:
    db_path = str(tmp_path / "memory.db")
    store = await MemoryStore.open(db_path)
    logger = FeedbackLogger(db_path)

    registry = PersonaRegistry(
        {
            "jarvis": build_jarvis_seed(warmth=_WARMTH),
            "pepper": build_pepper_seed(warmth=_WARMTH),
        }
    )
    return store, logger, registry, db_path


async def _seed_one_turn(logger: FeedbackLogger) -> None:
    await logger.record_turn(
        turn_id="t1",
        utterance="hello",
        explicit=None,
        plan=_make_plan(),
        outcome=_make_outcome(),
    )


# ── refresh returns skipped when no turns ─────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_skipped_when_no_turns(tmp_path: Path) -> None:
    from server.dialog.profile_refresher import ProfileRefresher

    store, logger, registry, db_path = await _setup(tmp_path)
    try:
        refresher = ProfileRefresher(
            registry=registry,
            feedback=logger,
            client=_FakeClient(),
            db_path=db_path,
        )
        result = await refresher.refresh()
        assert result["status"] == "skipped"
    finally:
        await store.close()


# ── refresh calls LLM and updates registry ────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_updates_registry_profiles(tmp_path: Path) -> None:
    from server.dialog.profile_refresher import ProfileRefresher

    store, logger, registry, db_path = await _setup(tmp_path)
    try:
        await _seed_one_turn(logger)

        # Use profiles that are close enough to seed to NOT trigger the blending rule.
        # They share most words with the seed profiles; only minor wording differences.
        new_jarvis = (
            "Briefings, calendar, planning, prose, architecture discussion, decision "
            "support, strategy, anything conversational. Hands code-heavy work to Pepper. "
            "Also helps Max think through complex decisions."
        )
        new_pepper = (
            "Code, tests, refactors, dev-environment ops, debugging, build systems, "
            "anything the Codex CLI can act on. Hands soft / strategic questions to Jarvis. "
            "Particularly strong on Python and TypeScript projects."
        )
        client = _FakeClient(return_msg=_refresh_tool_use(new_jarvis, new_pepper))
        refresher = ProfileRefresher(
            registry=registry,
            feedback=logger,
            client=client,
            db_path=db_path,
        )
        result = await refresher.refresh()

        assert result["status"] == "ok"
        assert registry.get("jarvis").specialty_profile == new_jarvis
        assert registry.get("pepper").specialty_profile == new_pepper
    finally:
        await store.close()


# ── refresh persists to personas table ────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_persists_to_db(tmp_path: Path) -> None:
    from server.dialog.profile_refresher import ProfileRefresher

    store, logger, registry, db_path = await _setup(tmp_path)
    try:
        await _seed_one_turn(logger)

        # Profiles similar enough to seed to NOT trigger blending.
        new_j = (
            "Briefings, calendar, planning, prose, architecture discussion, decision "
            "support, strategy, anything conversational. Hands code-heavy work to Pepper."
        )
        new_p = (
            "Code, tests, refactors, dev-environment ops, debugging, build systems, "
            "anything the Codex CLI can act on. Hands soft questions to Jarvis."
        )
        client = _FakeClient(return_msg=_refresh_tool_use(new_j, new_p))
        refresher = ProfileRefresher(
            registry=registry,
            feedback=logger,
            client=client,
            db_path=db_path,
        )
        await refresher.refresh()

        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute("SELECT id, profile, refresh_count FROM personas ORDER BY id")
            rows = {r[0]: (r[1], r[2]) for r in await cur.fetchall()}

        assert "jarvis" in rows
        assert "pepper" in rows
        assert rows["jarvis"][0] == new_j
        assert rows["pepper"][0] == new_p
        assert rows["jarvis"][1] >= 1
        assert rows["pepper"][1] >= 1
    finally:
        await store.close()


# ── refresh_count increments on successive calls ──────────────────────────


@pytest.mark.asyncio
async def test_refresh_count_increments(tmp_path: Path) -> None:
    from server.dialog.profile_refresher import ProfileRefresher

    store, logger, registry, db_path = await _setup(tmp_path)
    try:
        await _seed_one_turn(logger)

        new_j = "Jarvis handles briefings and planning."
        new_p = "Pepper handles code tasks."
        client = _FakeClient(return_msg=_refresh_tool_use(new_j, new_p))
        refresher = ProfileRefresher(
            registry=registry,
            feedback=logger,
            client=client,
            db_path=db_path,
        )
        await refresher.refresh()
        # refresh again with same fake client (returns same message)
        await refresher.refresh()

        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute("SELECT refresh_count FROM personas WHERE id='jarvis'")
            row = await cur.fetchone()
            assert row is not None
            assert row[0] == 2
    finally:
        await store.close()


# ── bounded-change rule: >40% drift → blend ───────────────────────────────


@pytest.mark.asyncio
async def test_bounded_change_rule_blends_on_high_drift(tmp_path: Path) -> None:
    """When LLM output has <60% similarity to old profile, the stored profile
    should be the blended text (not the raw LLM output verbatim)."""
    from server.dialog.profile_refresher import ProfileRefresher

    store, logger, registry, db_path = await _setup(tmp_path)
    try:
        await _seed_one_turn(logger)

        # Completely unrelated text → high drift, should trigger blending
        totally_different_j = "AAAAAAAAAA BBBBBBBBBB CCCCCCCCCC DDDDDDDDDD EEEEEEEEEE"
        totally_different_p = "ZZZZZZZZZZ YYYYYYYYYY XXXXXXXXXX WWWWWWWWWW VVVVVVVVVV"

        client = _FakeClient(
            return_msg=_refresh_tool_use(totally_different_j, totally_different_p)
        )
        refresher = ProfileRefresher(
            registry=registry,
            feedback=logger,
            client=client,
            db_path=db_path,
        )
        await refresher.refresh()

        jarvis_profile = registry.get("jarvis").specialty_profile
        # The blended text must NOT be the verbatim LLM output
        assert jarvis_profile != totally_different_j
        # It must contain content from the old seed profile (blend includes old)
        assert JARVIS_SEED[:20] in jarvis_profile or len(jarvis_profile) > len(totally_different_j)
    finally:
        await store.close()


# ── malformed / invalid LLM output is rejected ────────────────────────────


@pytest.mark.asyncio
async def test_refresh_rejects_malformed_llm_output(tmp_path: Path) -> None:
    """If the LLM emits a tool_use with invalid schema, refresh should fail gracefully."""
    from server.dialog.profile_refresher import ProfileRefresher

    store, logger, registry, db_path = await _setup(tmp_path)
    try:
        await _seed_one_turn(logger)

        original_j = registry.get("jarvis").specialty_profile
        # Malformed: jarvis_profile is empty (violates min_length=10)
        malformed_msg = _FakeMessage(
            content=[
                _FakeBlock(
                    btype="tool_use",
                    input={
                        "jarvis_profile": "",
                        "pepper_profile": "",
                        "summary": "bad",
                    },
                ),
            ],
        )
        client = _FakeClient(return_msg=malformed_msg)
        refresher = ProfileRefresher(
            registry=registry,
            feedback=logger,
            client=client,
            db_path=db_path,
        )
        result = await refresher.refresh()

        # Should return error status and NOT update the profiles
        assert result["status"] == "error"
        assert registry.get("jarvis").specialty_profile == original_j
    finally:
        await store.close()


# ── reset() restores seed profiles ────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_restores_seed_profiles(tmp_path: Path) -> None:
    from server.dialog.profile_refresher import ProfileRefresher

    store, logger, registry, db_path = await _setup(tmp_path)
    try:
        await _seed_one_turn(logger)

        # First update the profiles (use text close to seed to avoid blending)
        new_j = (
            "Briefings, calendar, planning, prose, architecture discussion, decision "
            "support, strategy, anything conversational. Hands code-heavy work to Pepper."
        )
        new_p = (
            "Code, tests, refactors, dev-environment ops, debugging, build systems, "
            "anything the Codex CLI can act on. Hands soft questions to Jarvis."
        )
        client = _FakeClient(return_msg=_refresh_tool_use(new_j, new_p))
        refresher = ProfileRefresher(
            registry=registry,
            feedback=logger,
            client=client,
            db_path=db_path,
            warmth="off",
        )
        await refresher.refresh()
        assert registry.get("jarvis").specialty_profile == new_j

        # Now reset
        await refresher.reset()

        # Should be back to seed
        assert registry.get("jarvis").specialty_profile == JARVIS_SEED
        assert registry.get("pepper").specialty_profile == PEPPER_SEED
    finally:
        await store.close()


# ── reset() persists seed profiles to DB ──────────────────────────────────


@pytest.mark.asyncio
async def test_reset_persists_to_db(tmp_path: Path) -> None:
    from server.dialog.profile_refresher import ProfileRefresher

    store, logger, registry, db_path = await _setup(tmp_path)
    try:
        refresher = ProfileRefresher(
            registry=registry,
            feedback=logger,
            client=_FakeClient(),
            db_path=db_path,
            warmth="off",
        )
        await refresher.reset()

        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute("SELECT id, profile FROM personas ORDER BY id")
            rows = {r[0]: r[1] for r in await cur.fetchall()}

        assert rows.get("jarvis") == JARVIS_SEED
        assert rows.get("pepper") == PEPPER_SEED
    finally:
        await store.close()


# ── LLM tool call sends correct model + tool ──────────────────────────────


@pytest.mark.asyncio
async def test_refresh_uses_haiku_model(tmp_path: Path) -> None:
    from server.dialog.profile_refresher import ProfileRefresher

    store, logger, registry, db_path = await _setup(tmp_path)
    try:
        await _seed_one_turn(logger)

        new_j = "Jarvis handles briefings and planning for Max."
        new_p = "Pepper handles code and dev-environment tasks."
        client = _FakeClient(return_msg=_refresh_tool_use(new_j, new_p))
        refresher = ProfileRefresher(
            registry=registry,
            feedback=logger,
            client=client,
            db_path=db_path,
            model="claude-haiku-4-5",
        )
        await refresher.refresh()

        assert client.messages.captured_kwargs.get("model") == "claude-haiku-4-5"
        # Verify it uses tool_choice for structured output
        tc = client.messages.captured_kwargs.get("tool_choice", {})
        assert tc.get("type") == "tool"
        assert tc.get("name") == "emit_refresh"
    finally:
        await store.close()

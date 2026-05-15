# Multi-model support — Phase 5 (Learning loop + default flag flip) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persona specialties adapt over time. Every turn's dispatch + outcome is logged to SQLite. Every N turns a cheap LLM summariser reads the recent log and rewrites each persona's `specialty_profile` in place. Seed-floor + bounded-change safety rails. `/reset personas` voice command + HUD button restore seeds. `GET /personas` exposes current profiles. **At the end of Phase 5, the `JARVIS_PERSONAS_ENABLED` default flips from `false` to `true` — the feature is live by default.**

**Architecture:** Two new SQLite tables (`dispatch_log`, `personas`) in the existing `memory.db`. A `FeedbackLogger` writes one row per turn after outcome resolution. A `ProfileRefresher` schedules a refresh task after every N turns, runs `claude-haiku-4-5` with the recent log + current profiles + seed floor, validates the output, and writes back via `PersonaRegistry.update_profile`. `GET /personas` (auth-gated) returns the current profiles. `/reset personas` is a server-side text trigger that resets profiles to seed.

**Tech Stack:** Python 3.12, `aiosqlite>=0.20` (already in deps), `anthropic` (existing summariser pattern from `memory/summarizer.py`), pydantic v2 for output validation.

**Spec:** `docs/superpowers/specs/2026-05-13-multi-model-support-design.md` — §8 (learning loop), §8.4 (safety rails), §8.5 (inspection endpoint).

**Branch:** `claude/multi-model-support-phase-5` (already checked out off `main` @ `3095fd3`).

**Working directory:** `server/` for all `pytest` commands. **Run tests via `python -m pytest`** (bare `pytest` lacks fastapi).

---

## Phase 4 → Phase 5 decision log

| # | Decision | Implication for Phase 5 |
|---|---|---|
| 1 | `python -m pytest` is the only pytest that sees the deps. | All test commands use `python -m pytest`. |
| 2 | PlaybackQueue clears speaker on natural completion (`onended` when `active.length === 0`). | Pattern: client-side state that should clear on idle uses an explicit "is the queue empty?" check rather than waiting for a sentinel event. Apply if Phase 5 adds any client-driven timers. |
| 3 | `CommandHistory.tagLastSpeaker(text, speaker)` retroactively tags entries with refusal-to-overwrite. Tagging happens from the `dispatch.plan` handler in `main.ts`. | If Phase 5 wants to attach outcome data to the same entries (e.g. ✓/✗ marker after `llm.end`), use the same retroactive-tag pattern. Not in scope; just noting. |
| 4 | `events.currentSpeaker()` exposes playback-derived speaker. The visual layer reads it directly; the store no longer participates. | Phase 5's `/reset personas` is a server-side text trigger — no frontend voice-recognition needed. STT delivers the text; the server pattern-matches. |
| 5 | `state.snapshot.system.personas` flows through the existing `state_snapshot` factory without protocol changes (it accepts `dict[str, Any]`). | Phase 5 extends `system.personas` with `last_refresh_ts` + `refresh_count` so the HUD can show "last refresh: N turns ago" (no new protocol message needed). |
| 6 | The existing `memory/` module pattern: `MemoryStore.open(path)` for SQLite, `ClaudeSummarizer` for LLM-based summaries, `Settings.memory_db_path`. | Phase 5 reuses these: the new tables go in the same DB, the refresher reuses the summariser pattern. |
| 7 | `Outcome` from `dialog/types.py` already has all 11 fields from spec §8.2. | Phase 5 doesn't re-define Outcome; it persists it. `DialogManager` already records `Outcome` in-memory; Phase 5's FeedbackLogger reads from there + signals from session-level events (interrupt, next-turn re-address). |
| 8 | `PersonaRegistry.update_profile(persona_id, new_profile)` re-validates via `model_validate({…model_dump, …})` — pydantic v2's `model_copy(update=)` skips validators (Phase 1 fix). | ProfileRefresher's writeback must use `update_profile`. The bounded-change rule applies before the call so the validate happens on the already-blended profile. |
| 9 | `personas/seed.py::build_jarvis_seed` / `build_pepper_seed` are idempotent. | `/reset personas` rebuilds from `seed.py` and calls `update_profile` with the seed text. |
| 10 | Phase 1-4 all kept `JARVIS_PERSONAS_ENABLED=false` as the default with a dormancy regression test. | Phase 5's last task flips the default to `true`. The dormancy regression test gets repurposed: with the flag *implicitly* off via `JARVIS_PERSONAS_ENABLED=false`, the regression check still passes. A new check confirms the *new* default boots the full path. |
| 11 | The "warmth budget" counter in `DialogState` (spec §4.3) is a `NonNegativeInt = 0` field that the Dispatcher reads but nothing currently increments. | Phase 5 increments it on each "soft" handoff and rate-limits via `max one beat per turn`. Out of scope as a separate task; absorbed into the Dispatcher prompt seed in §4.3, no code change here. |

---

## File map

| Path | Status | Purpose |
|---|---|---|
| `server/server/memory/store.py` | modify | Add migration to create `dispatch_log` + `personas` tables (idempotent CREATE TABLE IF NOT EXISTS) |
| `server/server/dialog/feedback.py` | create | `FeedbackLogger`: writes one `dispatch_log` row per turn after `llm.end`; collects implicit signals (interrupt, re-address) |
| `server/server/dialog/profile_refresher.py` | create | `ProfileRefresher`: scheduled async task, calls `claude-haiku-4-5` summariser, applies safety rails, writes back via `update_profile` |
| `server/server/personas/registry.py` | modify | Add `reset_to_seed()` method; add `last_refresh_ts` / `refresh_count` to in-memory state |
| `server/server/dialog/manager.py` | modify | After `handle_turn` completes, append a row to `FeedbackLogger`; expose `next_turn_readdressed` signal for the prior turn |
| `server/server/main.py` | modify | Lifespan constructs `_feedback_logger` + `_profile_refresher`; ws_endpoint passes them through; handle `/reset personas` text trigger; add `GET /personas` endpoint |
| `server/server/session.py` | modify | Detect `/reset personas` in user text BEFORE dispatch; if matched, run reset + send a spoken confirmation; skip the rest of the turn |
| `server/server/state.py` *(or equivalent)* | modify | `state.snapshot.system.personas` grows `lastRefreshTs` + `refreshCount` |
| `server/server/config.py` | modify | Flip `personas_enabled` default from `False` to `True` (last task only) |
| `server/server/protocol.py` | unchanged | (No new messages — reset reply rides on existing `llm.token` / `tts.sentence` path; profile data exposed via REST.) |
| `server/tests/test_feedback_logger.py` | create | Tests for `FeedbackLogger` (row shape, signal collection) |
| `server/tests/test_profile_refresher.py` | create | Tests for `ProfileRefresher` (refresh writes profile, seed-floor preserved, bounded-change blends, malformed output rejected, `/reset` restores seeds) |
| `server/tests/test_reset_personas.py` | create | Tests for the `/reset personas` text trigger path through Session |
| `server/tests/test_personas_endpoint.py` | create | Tests for `GET /personas` (auth-gated; returns current profiles + last-refresh) |
| `server/tests/test_phase5_smoke.py` | create | End-to-end smoke: dispatch → log row → trigger refresh → profile updates → `/personas` reflects it |
| `server/tests/test_flag_default_flip.py` | create | Asserts the new default is `personas_enabled=True`; documents that the old dormancy regression guard is now scoped to `JARVIS_PERSONAS_ENABLED=false` explicitly |
| `server/README.md` | modify | Document the learning loop + `/reset personas` + `GET /personas`; flip the env-var table default |

---

## Task 1: Schema migration in `memory/store.py`

**Files:**
- Modify: `server/server/memory/store.py`
- Create: `server/tests/test_dispatch_log_schema.py`

The existing `MemoryStore` opens `memory.db` and runs migrations on open. Add idempotent `CREATE TABLE IF NOT EXISTS` for `dispatch_log` and `personas`.

- [ ] **Step 1: Read existing `memory/store.py`** to see the migration pattern.

- [ ] **Step 2: Write failing tests**

Create `server/tests/test_dispatch_log_schema.py`:

```python
"""Phase 5 schema migration tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest

from server.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_dispatch_log_table_created(tmp_path: Path) -> None:
    store = await MemoryStore.open(str(tmp_path / "memory.db"))
    try:
        async with aiosqlite.connect(str(tmp_path / "memory.db")) as db:
            cur = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='dispatch_log'"
            )
            row = await cur.fetchone()
            assert row is not None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_personas_table_created(tmp_path: Path) -> None:
    store = await MemoryStore.open(str(tmp_path / "memory.db"))
    try:
        async with aiosqlite.connect(str(tmp_path / "memory.db")) as db:
            cur = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='personas'"
            )
            assert await cur.fetchone() is not None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_migrations_idempotent(tmp_path: Path) -> None:
    """Re-opening the same DB doesn't error or duplicate tables."""
    path = str(tmp_path / "memory.db")
    s1 = await MemoryStore.open(path)
    await s1.close()
    s2 = await MemoryStore.open(path)
    try:
        async with aiosqlite.connect(path) as db:
            cur = await db.execute(
                "SELECT count(*) FROM sqlite_master "
                "WHERE type='table' AND name IN ('dispatch_log','personas')"
            )
            count_row = await cur.fetchone()
            assert count_row is not None
            assert count_row[0] == 2
    finally:
        await s2.close()


@pytest.mark.asyncio
async def test_dispatch_log_columns(tmp_path: Path) -> None:
    """Spec §8.1: turn_id, ts, utterance, explicit, plan_json, rationale, outcome_json."""
    path = str(tmp_path / "memory.db")
    store = await MemoryStore.open(path)
    try:
        async with aiosqlite.connect(path) as db:
            cur = await db.execute("PRAGMA table_info(dispatch_log)")
            cols = {row[1] for row in await cur.fetchall()}
            assert {
                "turn_id", "ts", "utterance", "explicit",
                "plan_json", "rationale", "outcome_json",
            }.issubset(cols)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_personas_columns(tmp_path: Path) -> None:
    """Spec §8.1: id, profile, last_refresh, refresh_count."""
    path = str(tmp_path / "memory.db")
    store = await MemoryStore.open(path)
    try:
        async with aiosqlite.connect(path) as db:
            cur = await db.execute("PRAGMA table_info(personas)")
            cols = {row[1] for row in await cur.fetchall()}
            assert {"id", "profile", "last_refresh", "refresh_count"}.issubset(cols)
    finally:
        await store.close()
```

- [ ] **Step 3: Run tests (RED)**

```bash
cd server && python -m pytest tests/test_dispatch_log_schema.py -v
```

- [ ] **Step 4: Add migrations to `MemoryStore.open()` (or wherever the existing migrations live)**

Locate the existing CREATE TABLE statements in `memory/store.py`. Append:

```python
# Phase 5: dispatch_log + personas
await db.execute("""
    CREATE TABLE IF NOT EXISTS dispatch_log (
        turn_id      TEXT PRIMARY KEY,
        ts           REAL NOT NULL,
        utterance    TEXT NOT NULL,
        explicit     TEXT,
        plan_json    TEXT NOT NULL,
        rationale    TEXT,
        outcome_json TEXT NOT NULL
    )
""")
await db.execute("""
    CREATE TABLE IF NOT EXISTS personas (
        id            TEXT PRIMARY KEY,
        profile       TEXT NOT NULL,
        last_refresh  REAL NOT NULL,
        refresh_count INTEGER NOT NULL DEFAULT 0
    )
""")
await db.commit()
```

- [ ] **Step 5: Run tests (GREEN) + full suite**

```bash
cd server && python -m pytest -q
```

- [ ] **Step 6: Commit**

```bash
git add server/server/memory/store.py server/tests/test_dispatch_log_schema.py
git commit -m "feat(memory): add dispatch_log + personas tables (Phase 5 schema)

Idempotent CREATE TABLE IF NOT EXISTS for the learning loop's two
tables. Spec §8.1 columns: dispatch_log (turn_id, ts, utterance,
explicit, plan_json, rationale, outcome_json) + personas (id,
profile, last_refresh, refresh_count). Five round-trip tests cover
table creation, column shape, and migration idempotency."
```

---

## Task 2: `FeedbackLogger`

**Files:**
- Create: `server/server/dialog/feedback.py`
- Create: `server/tests/test_feedback_logger.py`

Records one `dispatch_log` row per turn. Reads the `Plan` + `Outcome` from the `DialogManager` after `llm.end`, plus session-level signals (was there a barge-in? did the next turn re-address?).

- [ ] **Step 1: Tests** (Create `server/tests/test_feedback_logger.py` covering: row written on `record_turn`, outcome fields persisted as JSON, `next_turn_readdressed` linked to prior row when re-addressing happens, `recent(N)` returns rows newest-first, `feedback.signal` updates the most recent row in place.)

- [ ] **Step 2: Implementation sketch** (`server/server/dialog/feedback.py`):

```python
"""FeedbackLogger — persists one dispatch_log row per turn.

Spec anchor: §8 (learning loop).

After DialogManager.handle_turn finishes:
  1. Session calls feedback.record_turn(turn_id, utterance, explicit,
     plan, rationale, outcome).
  2. Logger writes a dispatch_log row.
  3. Next turn arrives: Session calls feedback.tag_readdress(prior_turn_id,
     other_speaker) if the new turn explicitly addressed the OTHER persona —
     strong negative signal recorded retroactively in the prior row's
     outcome_json.
"""

from __future__ import annotations

import json
import time
from typing import Any

import aiosqlite

from server.dialog.types import Outcome, PersonaId, Plan


class FeedbackLogger:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def record_turn(
        self,
        *,
        turn_id: str,
        utterance: str,
        explicit: PersonaId | None,
        plan: Plan,
        outcome: Outcome,
    ) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO dispatch_log "
                "(turn_id, ts, utterance, explicit, plan_json, rationale, outcome_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    turn_id, time.time(), utterance, explicit,
                    plan.model_dump_json(), plan.rationale,
                    outcome.model_dump_json(),
                ),
            )
            await db.commit()

    async def tag_readdress(
        self,
        *,
        prior_turn_id: str,
        other_speaker: PersonaId,
    ) -> None:
        """Retroactively flag the prior turn as 'user re-addressed the other persona'."""
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                "SELECT outcome_json FROM dispatch_log WHERE turn_id = ?",
                (prior_turn_id,),
            )
            row = await cur.fetchone()
            if row is None:
                return
            outcome = Outcome.model_validate_json(row[0])
            updated = outcome.model_copy(update={"next_turn_readdressed": other_speaker})
            await db.execute(
                "UPDATE dispatch_log SET outcome_json = ? WHERE turn_id = ?",
                (updated.model_dump_json(), prior_turn_id),
            )
            await db.commit()

    async def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                "SELECT turn_id, ts, utterance, explicit, plan_json, rationale, outcome_json "
                "FROM dispatch_log ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
        return [
            {
                "turn_id": r[0], "ts": r[1], "utterance": r[2],
                "explicit": r[3], "plan": json.loads(r[4]),
                "rationale": r[5], "outcome": json.loads(r[6]),
            }
            for r in rows
        ]
```

- [ ] **Step 3: Commit**

```bash
git add server/server/dialog/feedback.py server/tests/test_feedback_logger.py
git commit -m "feat(dialog): add FeedbackLogger (persists turn outcomes)

One row per turn in dispatch_log: turn_id, utterance, explicit
speaker (name-at-start), Plan JSON, rationale, Outcome JSON.
tag_readdress retroactively flags the prior turn when the user
re-addressed the other persona — strong negative signal for the
learning loop. recent(N) returns rows newest-first for the
ProfileRefresher to summarise."
```

---

## Task 3: `ProfileRefresher`

**Files:**
- Create: `server/server/dialog/profile_refresher.py`
- Create: `server/tests/test_profile_refresher.py`

Scheduled async task. Every N turns (config: `JARVIS_PERSONA_REFRESH_TURNS=20`), reads the last ~100 dispatch_log rows + current profiles + seed floor (from `seed.py`), calls `claude-haiku-4-5` with a structured-output prompt, validates the response, applies the bounded-change rule (>40% drift → half-weight blend), writes back via `PersonaRegistry.update_profile`.

- [ ] **Step 1: Tests** — cover: structured output parsing, seed-floor preservation, bounded-change blending, validation rejection, `/reset` restores seeds, refresh increments `refresh_count` and updates `last_refresh`.

- [ ] **Step 2: Implementation sketch** (key parts):

```python
"""ProfileRefresher — the learning loop.

Spec anchors: §8.3 (refresher), §8.4 (safety rails).

Trigger: every N turns OR explicit invocation.
Steps:
  1. Read recent dispatch_log rows + current profiles.
  2. Build structured prompt (haiku tool-use) with profiles + log.
  3. Validate output (~250-word cap, mentions of seed traits).
  4. Apply bounded-change rule: token-similarity to old profile;
     if <60% similarity, blend at 50/50 instead.
  5. Call PersonaRegistry.update_profile (re-validates via pydantic).
  6. Update personas table: profile, last_refresh, refresh_count++.
  7. Emit telemetry: persona_refresh with diff summary.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Literal

import aiosqlite
from pydantic import BaseModel, Field, ValidationError

from server.dialog.feedback import FeedbackLogger
from server.personas.registry import PersonaRegistry
from server.personas.seed import build_jarvis_seed, build_pepper_seed

log = logging.getLogger(__name__)


class _RefreshOutput(BaseModel):
    jarvis_profile: str = Field(min_length=10, max_length=1800)
    pepper_profile: str = Field(min_length=10, max_length=1800)
    summary: str = Field(min_length=1, max_length=400)


class ProfileRefresher:
    def __init__(
        self,
        *,
        registry: PersonaRegistry,
        feedback: FeedbackLogger,
        client: Any,
        db_path: str,
        model: str = "claude-haiku-4-5",
        bounded_change_threshold: float = 0.40,  # >40% drift → blend
        warmth: Literal["subtle", "off"] = "subtle",
    ) -> None:
        self._registry = registry
        self._feedback = feedback
        self._client = client
        self._db_path = db_path
        self._model = model
        self._threshold = bounded_change_threshold
        self._warmth = warmth
        self._refresh_count: dict[str, int] = {}
        self._last_refresh_ts: dict[str, float] = {}

    async def refresh(self) -> dict[str, Any]:
        """Run one refresh cycle. Returns a summary dict (also useful for tests)."""
        recent_rows = await self._feedback.recent(limit=100)
        if not recent_rows:
            return {"status": "skipped", "reason": "no turns"}

        # Build prompt; call LLM; validate output; apply safety rails.
        # … (see plan for full prompt + parsing)

        # Update registry + DB
        for pid, blended in [("jarvis", j_blended), ("pepper", p_blended)]:
            self._registry.update_profile(pid, blended)
            await self._persist(pid, blended)
        return {"status": "ok", "summary": parsed.summary}

    async def reset(self) -> None:
        """Restore seeds — wipes any learned drift."""
        jarvis = build_jarvis_seed(warmth=self._warmth)
        pepper = build_pepper_seed(warmth=self._warmth)
        self._registry.update_profile("jarvis", jarvis.specialty_profile)
        self._registry.update_profile("pepper", pepper.specialty_profile)
        for pid, persona in [("jarvis", jarvis), ("pepper", pepper)]:
            await self._persist(pid, persona.specialty_profile)

    async def _persist(self, persona_id: str, profile: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO personas "
                "(id, profile, last_refresh, refresh_count) "
                "VALUES (?, ?, ?, COALESCE("
                "  (SELECT refresh_count + 1 FROM personas WHERE id = ?), 1))",
                (persona_id, profile, time.time(), persona_id),
            )
            await db.commit()
```

The token-similarity check can be a simple `difflib.SequenceMatcher.ratio()` — good enough for the bounded-change rule.

- [ ] **Step 3: Commit**

```bash
git add server/server/dialog/profile_refresher.py server/tests/test_profile_refresher.py
git commit -m "feat(dialog): add ProfileRefresher (the learning loop)

Scheduled async task: every N turns reads the recent dispatch_log
+ current profiles, calls claude-haiku-4-5 with a structured-output
prompt, validates, applies the bounded-change rule (>40% drift →
50/50 blend with prior), writes back via PersonaRegistry.update_profile
+ persists to the personas table. reset() restores seed profiles."
```

---

## Task 4: `/reset personas` voice command + `GET /personas` endpoint

**Files:**
- Modify: `server/server/session.py`
- Modify: `server/server/main.py`
- Create: `server/tests/test_reset_personas.py`
- Create: `server/tests/test_personas_endpoint.py`

`/reset personas` is detected in `Session._do_llm_and_tts` BEFORE dispatch. If matched, run `refresher.reset()` and respond with a one-sentence spoken confirmation through the normal `tts.sentence` path. Don't run the dispatcher / LLM.

`GET /personas` (auth-gated via the existing `require_token` dependency) returns the current profiles + last refresh ts + refresh_count.

- [ ] **Step 1: Tests** — `test_reset_personas.py` covers: `/reset personas` text triggers `refresher.reset()`, emits a spoken confirmation, skips dispatch. `test_personas_endpoint.py` covers: GET returns 401 without token; returns the live registry state with token.

- [ ] **Step 2: Implementation in Session**

In `_do_llm_and_tts`, add a guard before the dialog manager branch:

```python
if self._refresher is not None and user_text.strip().lower() == "/reset personas":
    await self._refresher.reset()
    confirmation = "Personas reset to seed."
    await self._tts_say(confirmation, speaker="jarvis")
    return
```

Where `_tts_say` is a small helper that emits one `tts.sentence` + audio chunks through the standard pipeline.

- [ ] **Step 3: Implementation of `GET /personas`** in `main.py`:

```python
@app.get("/personas", response_model=...)
async def personas(_: None = Depends(require_token)) -> dict[str, Any]:
    if _persona_registry is None:
        raise HTTPException(503, "personas not enabled")
    out = {}
    for pid in _persona_registry.available_ids():
        p = _persona_registry.get(pid)
        out[pid] = {
            "displayName": p.display_name,
            "provider": p.provider,
            "voice": p.voice,
            "specialtyProfile": p.specialty_profile,
            "lastRefreshTs": _refresher._last_refresh_ts.get(pid) if _refresher else None,
            "refreshCount": _refresher._refresh_count.get(pid, 0) if _refresher else 0,
        }
    return out
```

- [ ] **Step 4: Commit**

```bash
git add server/server/session.py server/server/main.py server/tests/test_reset_personas.py server/tests/test_personas_endpoint.py
git commit -m "feat(server): /reset personas command + GET /personas endpoint

Session intercepts '/reset personas' as text and runs refresher.reset()
before the dispatcher, replying with a spoken confirmation. Bypass
ensures the reset can't deadlock against a broken dispatcher.

GET /personas (auth-gated) returns the current persona profiles +
last-refresh timestamp + refresh-count for inspection / debugging."
```

---

## Task 5: Wire FeedbackLogger + ProfileRefresher through main.py + DialogManager

**Files:**
- Modify: `server/server/dialog/manager.py`
- Modify: `server/server/main.py`
- Modify: `server/server/state.py` (or wherever `state.snapshot.system.personas` is assembled)
- Create: `server/tests/test_phase5_smoke.py`

`DialogManager` accepts a `feedback: FeedbackLogger | None` kwarg. After `handle_turn` finishes, calls `feedback.record_turn(...)`. The refresher's scheduling logic increments an internal counter; when it reaches `JARVIS_PERSONA_REFRESH_TURNS`, it spawns a task to run `refresher.refresh()`.

Main.py lifespan:
```python
_feedback_logger = FeedbackLogger(settings.memory_db_path)
_profile_refresher = ProfileRefresher(
    registry=_persona_registry,
    feedback=_feedback_logger,
    client=_anthropic_client,
    db_path=settings.memory_db_path,
    model=settings.dispatcher_model,
    warmth=settings.persona_warmth,
)
```

State snapshot extension:
```python
personas["lastRefreshTs"] = _profile_refresher.most_recent_refresh_ts()
personas["refreshCount"] = _profile_refresher.refresh_count_total()
```

- [ ] **Step 1: Tests** — `test_phase5_smoke.py`: run a fake turn end-to-end → row appears in dispatch_log → trigger refresh manually → profile changes → `/personas` reflects the change.

- [ ] **Step 2: Implementation + commit**

```bash
git add server/server/dialog/manager.py server/server/main.py server/server/state.py server/tests/test_phase5_smoke.py
git commit -m "feat(dialog): wire FeedbackLogger + ProfileRefresher into the turn loop

DialogManager.handle_turn appends a dispatch_log row via FeedbackLogger
after llm.end. ProfileRefresher tracks a turn counter; when it hits
JARVIS_PERSONA_REFRESH_TURNS (default 20), it spawns a refresh task
async (doesn't block the next turn). state.snapshot.system.personas
grows lastRefreshTs + refreshCount so the HUD can show 'last refresh:
N turns ago'."
```

---

## Task 6: Flip the default flag + README + final smoke + push

**Files:**
- Modify: `server/server/config.py`
- Modify: `server/tests/test_config_personas.py`
- Modify: `server/tests/test_phase1_smoke.py` (the dormancy regression — repurpose with explicit env)
- Modify: `server/README.md`
- Create: `server/tests/test_flag_default_flip.py`

This is the **big switch**. `JARVIS_PERSONAS_ENABLED` default becomes `True`. The full multi-persona path is live by default.

- [ ] **Step 1: Update the dormancy regression test**

The existing `test_phase1_dormant_when_flag_off` (extended through phases 2-4) currently expects that with no explicit env, the flag is `false`. After this task, the flag's *default* is `true`, but `false` still works when explicitly set. Update the test to set `JARVIS_PERSONAS_ENABLED=false` explicitly before importing, then assert dormancy.

- [ ] **Step 2: New test asserting the new default**

Create `server/tests/test_flag_default_flip.py`:

```python
"""Phase 5: assert the multi-persona path is the new default."""

from __future__ import annotations

import importlib

import pytest


def test_personas_enabled_defaults_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_PERSONAS_ENABLED", raising=False)
    import server.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.personas_enabled is True


def test_personas_enabled_false_when_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_PERSONAS_ENABLED", "false")
    import server.config as cfg
    importlib.reload(cfg)
    assert cfg.settings.personas_enabled is False
```

- [ ] **Step 3: Flip the default in `config.py`**

```python
# Phase 5: default is now true. Set JARVIS_PERSONAS_ENABLED=false to fall
# back to the single-Jarvis path (kept for offline dev, CI, demos, and
# any deploys that don't have OPENAI_API_KEY).
personas_enabled: bool = True
```

Update the existing test fixture `test_personas_enabled_defaults_false` to either delete (replaced by `test_flag_default_flip.test_personas_enabled_defaults_true`) or rename to assert the explicit-false case.

- [ ] **Step 4: Update README**

Change the heading from "Phase 4 — UI surface" to "Phase 5 — live by default". Note the new default. Flip the `JARVIS_PERSONAS_ENABLED` row in the env-var table from `false` to `true`. Document `/reset personas` and `GET /personas`.

- [ ] **Step 5: Full suite + lint**

```bash
cd server && python -m pytest -q && ruff check . && python -m mypy
```

- [ ] **Step 6: Commit + push**

```bash
git add server/server/config.py server/tests/test_config_personas.py server/tests/test_phase1_smoke.py server/tests/test_flag_default_flip.py server/README.md
git commit -m "feat(personas): flip JARVIS_PERSONAS_ENABLED default to true

Phase 5 closeout. The multi-persona path is now live by default;
set JARVIS_PERSONAS_ENABLED=false to fall back to single-Jarvis
(offline dev / CI / demos / deploys without OPENAI_API_KEY). The
old dormancy regression guard is rescoped to the explicit-false
case; a new test_flag_default_flip asserts the new default."

git push -u origin claude/multi-model-support-phase-5
```

---

## Phase 5 acceptance checklist

- [ ] `python -m pytest -q` green.
- [ ] `ruff check .` clean.
- [ ] `python -m mypy` clean.
- [ ] `JARVIS_PERSONAS_ENABLED=false` still works — single-Jarvis fallback intact, existing tests pass.
- [ ] `JARVIS_PERSONAS_ENABLED` (unset) → defaults to `true`.
- [ ] dispatch_log + personas tables created; rows accumulate per turn.
- [ ] Manual: trigger 20+ turns → ProfileRefresher fires; `/personas` shows updated profiles + non-null `lastRefreshTs`.
- [ ] Manual: `/reset personas` returns profiles to seed; `lastRefreshTs` updates.
- [ ] Both CI checks (`server`, `web`) green on the PR.
- [ ] Codex P1/P2 review comments addressed.

---

*End of Phase 5 implementation plan.*

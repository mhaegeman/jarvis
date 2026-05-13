# Multi-model support — Phase 1 (Foundations) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lay the type system + persona registry + OpenAI chat backend + rule-based Dispatcher + feature flag. Ship behind `JARVIS_PERSONAS_ENABLED=false` so existing behaviour is unchanged.

**Architecture:** New `server/server/personas/` and `server/server/dialog/` packages. New `pipelines/openai_llm.py` sibling of `claude_llm.py`. No wiring into Session yet — that's Phase 2. All new code dormant until the flag flips.

**Tech Stack:** Python 3.12, `anthropic>=0.40` (existing), `openai>=1.55,<2.0` (new), `pydantic>=2.9`, pytest-asyncio (auto mode).

**Spec:** `docs/superpowers/specs/2026-05-13-multi-model-support-design.md` — read it before starting. Sections most relevant to Phase 1: §3.2 (module layout), §4 (persona model), §5.3 (rule-based routing rules), §10 (config).

**Branch:** `claude/multi-model-support-UeDxT` (already created and pushed; spec committed).

**Working directory:** `server/` for all `pytest` commands. `pyproject.toml` lives at `server/pyproject.toml`.

**Forward outline (Phases 2–5):** see the last section of this document. Each subsequent phase plan is written after the preceding phase lands so the decision log carries forward intact (spec §11.1).

---

## File map

| Path | Status | Purpose |
|---|---|---|
| `server/pyproject.toml` | modify | Add `openai>=1.55,<2.0` to runtime deps |
| `server/server/config.py` | modify | Add `personas_enabled`, `openai_api_key`, persona-related env vars |
| `server/server/dialog/__init__.py` | create | Package marker + public exports |
| `server/server/dialog/types.py` | create | `Segment`, `Plan`, `Outcome`, `DialogState` pydantic models |
| `server/server/dialog/dispatcher.py` | create | `RuleBasedDispatcher` (no LLM call) |
| `server/server/personas/__init__.py` | create | Package marker + public exports |
| `server/server/personas/models.py` | create | `ModelTier`, `AgentBackend`, `Persona` pydantic models |
| `server/server/personas/seed.py` | create | Jarvis + Pepper seed system prompts + specialty profiles + warmth clauses |
| `server/server/personas/registry.py` | create | `PersonaRegistry` (constructs from config, reads warmth toggle) |
| `server/server/pipelines/openai_llm.py` | create | `OpenAILLM` mirroring `ClaudeLLM` shape; OpenAI Responses API streaming |
| `server/tests/test_dialog_types.py` | create | Tests for `types.py` |
| `server/tests/test_dialog_dispatcher.py` | create | Tests for the rule-based Dispatcher |
| `server/tests/test_persona_models.py` | create | Tests for `personas/models.py` |
| `server/tests/test_persona_registry.py` | create | Tests for `PersonaRegistry` |
| `server/tests/test_openai_llm.py` | create | Tests for `OpenAILLM` with mocked client |
| `server/tests/test_config_personas.py` | create | Tests for new config fields and flag-off behaviour |
| `server/README.md` | modify | Add Phase 1 env-var rows + feature-flag note |

**No changes** in Phase 1 to: `main.py`, `session.py`, `protocol.py`, `pipelines/claude_llm.py`, `pipelines/edge_tts.py`. All wiring happens in Phase 2.

---

## Task 1: Add `openai` dependency + skeleton config

**Files:**
- Modify: `server/pyproject.toml`
- Modify: `server/server/config.py`
- Create: `server/tests/test_config_personas.py`

- [ ] **Step 1: Add the `openai` dependency**

Edit `server/pyproject.toml`. In the `[project] dependencies` list, append `"openai>=1.55,<2.0"` after `anthropic`:

```toml
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "websockets>=13",
  "pydantic>=2.9",
  "pydantic-settings>=2.5",
  "psutil>=5.9",
  "google-auth>=2.30",
  "google-auth-oauthlib>=1.2",
  "google-api-python-client>=2.140",
  "anthropic>=0.40,<1.0",
  "openai>=1.55,<2.0",
  "aiosqlite>=0.20",
  "argon2-cffi>=23.1",
]
```

- [ ] **Step 2: Install the dependency**

Run from `server/`:

```bash
pip install -e '.[dev]'
```

Expected: install succeeds; `openai` and its transitive deps land in the env.

- [ ] **Step 3: Write failing tests for the new config fields**

Create `server/tests/test_config_personas.py`:

```python
"""Tests for Phase 1 persona-related Settings fields."""

from __future__ import annotations

import importlib

import pytest


def _fresh_settings(monkeypatch: pytest.MonkeyPatch):
    """Force re-import of server.config so env-var changes take effect."""
    import server.config as cfg
    importlib.reload(cfg)
    return cfg.settings


def test_personas_enabled_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_PERSONAS_ENABLED", raising=False)
    s = _fresh_settings(monkeypatch)
    assert s.personas_enabled is False


def test_personas_enabled_true_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_PERSONAS_ENABLED", "true")
    s = _fresh_settings(monkeypatch)
    assert s.personas_enabled is True


def test_openai_api_key_loaded_without_jarvis_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-abc")
    s = _fresh_settings(monkeypatch)
    assert s.openai_api_key is not None
    assert s.openai_api_key.get_secret_value() == "sk-test-abc"


def test_persona_warmth_defaults_subtle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_PERSONA_WARMTH", raising=False)
    s = _fresh_settings(monkeypatch)
    assert s.persona_warmth == "subtle"


def test_persona_warmth_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_PERSONA_WARMTH", "off")
    s = _fresh_settings(monkeypatch)
    assert s.persona_warmth == "off"


def test_tier_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_TIER_DEFAULT_JARVIS", raising=False)
    monkeypatch.delenv("JARVIS_TIER_DEFAULT_PEPPER", raising=False)
    s = _fresh_settings(monkeypatch)
    assert s.tier_default_jarvis == "fast"
    assert s.tier_default_pepper == "fast"


def test_dispatcher_model_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_DISPATCHER_MODEL", raising=False)
    s = _fresh_settings(monkeypatch)
    assert s.dispatcher_model == "claude-haiku-4-5"


def test_learning_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_LEARNING", raising=False)
    s = _fresh_settings(monkeypatch)
    assert s.learning_enabled is True
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
cd server && pytest tests/test_config_personas.py -v
```

Expected: every test fails with `AttributeError: 'Settings' object has no attribute 'personas_enabled'` (or similar).

- [ ] **Step 5: Add the new fields to `Settings`**

Edit `server/server/config.py`. Replace the file with:

```python
"""Environment-driven configuration (Phase 1: minimal)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    ws_port: int = 8765
    log_level: str = "INFO"
    model_name: str = "mock"
    model_context_max: int = 200000
    llm_max_tokens: int = 1024

    # Memory settings — aliases match the spec's env-var table.
    # JARVIS_MEMORY=off disables all memory; JARVIS_MEMORY_DB overrides the DB path.
    # Default is cwd-relative: launched per docs as `cd server && uvicorn server.main:app`,
    # this lands at <repo>/server/data/memory.db, which the repo .gitignore covers.
    memory_enabled: bool = Field(default=True, validation_alias="JARVIS_MEMORY")
    memory_db_path: str = Field(
        default="data/memory.db", validation_alias="JARVIS_MEMORY_DB"
    )
    memory_resume_minutes: int = Field(default=30, validation_alias="JARVIS_MEMORY_RESUME_MIN")
    memory_refresh_turns: int = Field(default=5, validation_alias="JARVIS_MEMORY_REFRESH_TURNS")
    memory_recent_window: int = Field(default=20, validation_alias="JARVIS_MEMORY_RECENT_WINDOW")
    memory_facts_cap: int = Field(default=50, validation_alias="JARVIS_MEMORY_FACTS_CAP")
    memory_model: str = Field(
        default="claude-haiku-4-5-20251001", validation_alias="JARVIS_MEMORY_MODEL"
    )

    # validation_alias bypasses env_prefix so this loads from ANTHROPIC_API_KEY
    # (the SDK's standard convention) in either .env or the process environment.
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias="ANTHROPIC_API_KEY"
    )

    # STT pipeline selection.
    stt_engine: str = "auto"  # auto | mock | whisper
    whisper_model: str = "base.en"
    device: str = "auto"  # auto | cuda | mps | cpu

    # TTS pipeline selection.
    tts_engine: str = "auto"  # auto | mock | openvoice | edge
    openvoice_path: str = "~/OpenVoice"
    speaker_wav: str | None = None
    tts_voice: str = "en-US-ChristopherNeural"

    # Auth — passphrase hash (argon2id). Generate with:
    #   python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('yourphrase'))"
    passphrase_hash: str | None = Field(default=None, validation_alias="JARVIS_PASSPHRASE_HASH")

    # ─── Multi-model support (Phase 1) ─────────────────────────────────
    # Feature flag — when false, the existing single-Jarvis path is used.
    # All new code is dormant. Flip to true at the end of Phase 5 once the
    # full feature is verified end-to-end.
    personas_enabled: bool = False

    # OpenAI credentials — required for Pepper chat and Codex CLI agent.
    # validation_alias bypasses the JARVIS_ prefix to follow the OpenAI
    # SDK's standard convention, mirroring how ANTHROPIC_API_KEY is loaded.
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias="OPENAI_API_KEY"
    )
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")

    # Per-persona default tier ("fast" / "balanced" / "deep").
    tier_default_jarvis: Literal["fast", "balanced", "deep"] = "fast"
    tier_default_pepper: Literal["fast", "balanced", "deep"] = "fast"

    # The router model — cheap, used for every non-fast-path turn.
    dispatcher_model: str = "claude-haiku-4-5"

    # Persona dynamics. "subtle" = the quiet-warmth clause is appended to
    # each persona's system prompt; "off" strips it entirely.
    persona_warmth: Literal["subtle", "off"] = "subtle"

    # Learning loop cadence — profile refresh every N turns.
    persona_refresh_turns: int = 20

    # Learning loop master switch. validation_alias to keep the env-var
    # name consistent with JARVIS_MEMORY (the existing pattern).
    learning_enabled: bool = Field(default=True, validation_alias="JARVIS_LEARNING")

    # Codex CLI agent (used in Phase 3 — declared here so Phase 1 tests pass).
    codex_cli_path: str | None = None
    codex_approval: Literal["auto-low", "manual", "never"] = "auto-low"
    codex_sandbox: Literal["read-only", "workspace-write", "full-access"] = "workspace-write"
    codex_workdir: str | None = None


settings = Settings()
```

- [ ] **Step 6: Verify tests pass**

```bash
cd server && pytest tests/test_config_personas.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 7: Verify no existing test regressed**

```bash
cd server && pytest -q
```

Expected: every existing test still passes (same green state as on `main`).

- [ ] **Step 8: Commit**

```bash
git add server/pyproject.toml server/server/config.py server/tests/test_config_personas.py
git commit -m "feat(personas): add openai dep + Phase 1 Settings fields

JARVIS_PERSONAS_ENABLED (default false) gates all new behaviour.
OPENAI_API_KEY / OPENAI_BASE_URL bypass the JARVIS_ prefix via
validation_alias, matching the existing ANTHROPIC_API_KEY pattern.
Tier defaults, dispatcher model, warmth toggle, refresh cadence,
and Codex CLI vars are declared up-front so subsequent Phase 1
modules can read them without further config churn."
```

---

## Task 2: Dialog types (`dialog/types.py`)

**Files:**
- Create: `server/server/dialog/__init__.py`
- Create: `server/server/dialog/types.py`
- Create: `server/tests/test_dialog_types.py`

- [ ] **Step 1: Write failing tests for `Segment` validation**

Create `server/tests/test_dialog_types.py`:

```python
"""Tests for server.dialog.types — Segment / Plan / Outcome / DialogState."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from server.dialog.types import DialogState, Outcome, Plan, Segment, TurnRef


# ─── Segment ──────────────────────────────────────────────────────────


def test_segment_minimal() -> None:
    s = Segment(
        speaker="jarvis",
        tier="fast",
        mode="chat",
        intent="say hello",
    )
    assert s.speaker == "jarvis"
    assert s.tier == "fast"
    assert s.mode == "chat"
    assert s.handoff_style is None


def test_segment_rejects_unknown_speaker() -> None:
    with pytest.raises(ValidationError):
        Segment(speaker="bob", tier="fast", mode="chat", intent="x")


def test_segment_rejects_unknown_tier() -> None:
    with pytest.raises(ValidationError):
        Segment(speaker="jarvis", tier="ultra", mode="chat", intent="x")


def test_segment_rejects_unknown_mode() -> None:
    with pytest.raises(ValidationError):
        Segment(speaker="pepper", tier="fast", mode="rpc", intent="x")


def test_segment_handoff_style_accepted() -> None:
    s = Segment(
        speaker="jarvis", tier="balanced", mode="chat", intent="plan",
        handoff_style="soft",
    )
    assert s.handoff_style == "soft"


def test_segment_codex_agent_mode_requires_pepper() -> None:
    # Soft check: codex_agent mode is only meaningful for pepper. The model
    # does not enforce this at the pydantic level (Dispatcher does), but the
    # type itself accepts it for jarvis so we can roundtrip historical plans.
    s = Segment(speaker="jarvis", tier="fast", mode="codex_agent", intent="x")
    assert s.mode == "codex_agent"


# ─── Plan ─────────────────────────────────────────────────────────────


def test_plan_one_segment() -> None:
    p = Plan(
        segments=[Segment(speaker="jarvis", tier="fast", mode="chat", intent="hi")],
        rationale="trivial greeting",
    )
    assert len(p.segments) == 1


def test_plan_caps_at_three_segments() -> None:
    s = Segment(speaker="jarvis", tier="fast", mode="chat", intent="x")
    with pytest.raises(ValidationError):
        Plan(segments=[s, s, s, s], rationale="too many")


def test_plan_rejects_empty_segments() -> None:
    with pytest.raises(ValidationError):
        Plan(segments=[], rationale="empty")


def test_plan_json_roundtrip() -> None:
    p = Plan(
        segments=[
            Segment(speaker="jarvis", tier="balanced", mode="chat", intent="design",
                    handoff_style="soft"),
            Segment(speaker="pepper", tier="deep", mode="codex_agent", intent="implement"),
        ],
        rationale="design then implement",
    )
    data = json.loads(p.model_dump_json())
    p2 = Plan.model_validate(data)
    assert p2 == p


# ─── Outcome ──────────────────────────────────────────────────────────


def test_outcome_defaults() -> None:
    o = Outcome()
    assert o.completed is False
    assert o.user_interrupted_at is None
    assert o.next_turn_readdressed is None
    assert o.agent_status is None
    assert o.latency_ms is None
    assert o.tokens_in == 0
    assert o.tokens_out == 0
    assert o.cost_est == 0.0
    assert o.explicit_feedback is None


def test_outcome_explicit_feedback_constrained() -> None:
    with pytest.raises(ValidationError):
        Outcome(explicit_feedback="meh")  # type: ignore[arg-type]
    Outcome(explicit_feedback="positive")
    Outcome(explicit_feedback="negative")


def test_outcome_user_interrupted_segment_idx() -> None:
    o = Outcome(user_interrupted_at=1)
    assert o.user_interrupted_at == 1
    with pytest.raises(ValidationError):
        Outcome(user_interrupted_at=-1)


# ─── DialogState ──────────────────────────────────────────────────────


def test_dialog_state_defaults() -> None:
    d = DialogState()
    assert d.last_speaker is None
    assert d.last_turn_ts is None
    assert d.recent_turns == []
    assert d.warmth_budget == 0


def test_dialog_state_turn_ref_shape() -> None:
    d = DialogState(
        last_speaker="pepper",
        last_turn_ts=1700000000.0,
        recent_turns=[
            TurnRef(speaker="pepper", user_text="add a test", assistant_text="done."),
        ],
        warmth_budget=1,
    )
    assert d.last_speaker == "pepper"
    assert len(d.recent_turns) == 1
    assert d.recent_turns[0].speaker == "pepper"


def test_dialog_state_recent_turns_capped() -> None:
    refs = [
        TurnRef(speaker="jarvis", user_text=f"q{i}", assistant_text=f"a{i}")
        for i in range(10)
    ]
    with pytest.raises(ValidationError):
        DialogState(recent_turns=refs)  # cap is 3 per spec §5.1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && pytest tests/test_dialog_types.py -v
```

Expected: every test fails with `ModuleNotFoundError: No module named 'server.dialog'`.

- [ ] **Step 3: Create the package marker**

Create `server/server/dialog/__init__.py`:

```python
"""Dialog manager + dispatcher + types.

Phase 1 (foundations) ships only types.py and a rule-based dispatcher.
Subsequent phases add manager.py (orchestration), feedback.py (logger),
and profile_refresher.py (learning loop).
"""

from server.dialog.types import (
    DialogState,
    Outcome,
    Plan,
    Segment,
    TurnRef,
)

__all__ = [
    "DialogState",
    "Outcome",
    "Plan",
    "Segment",
    "TurnRef",
]
```

- [ ] **Step 4: Implement `types.py`**

Create `server/server/dialog/types.py`:

```python
"""Dialog primitive types.

Spec anchors:
- §3 (per-turn flow)
- §5.2 (Plan / Segment output schema)
- §6.2 (DialogState — what the persona / dispatcher receives)
- §8.2 (Outcome signals)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, NonNegativeInt


PersonaId = Literal["jarvis", "pepper"]
Tier = Literal["fast", "balanced", "deep"]
SegmentMode = Literal["chat", "codex_agent"]
HandoffStyle = Literal["flat", "soft"]
FeedbackSignal = Literal["positive", "negative"]
AgentStatus = Literal["ok", "failed", "cancelled"]


class Segment(BaseModel):
    """One unit of speech in a Plan.

    `handoff_style` is set only on non-terminal segments and tells the
    persona to end with a `[handoff:<persona>:<reason>]` tag (see spec §4.4).
    """

    model_config = {"extra": "forbid"}

    speaker: PersonaId
    tier: Tier
    mode: SegmentMode
    intent: str = Field(min_length=1, max_length=200)
    handoff_style: HandoffStyle | None = None


class Plan(BaseModel):
    """A Dispatcher's per-turn decision: an ordered list of Segments.

    1 to 3 segments, hard-capped (spec §5.3.5). `rationale` is one sentence
    logged for the learning loop (spec §8).
    """

    model_config = {"extra": "forbid"}

    segments: list[Segment] = Field(min_length=1, max_length=3)
    rationale: str = Field(min_length=1, max_length=400)


class TurnRef(BaseModel):
    """A compact reference to a prior turn for DialogState.recent_turns."""

    model_config = {"extra": "forbid"}

    speaker: PersonaId
    user_text: str = Field(max_length=2000)
    assistant_text: str = Field(max_length=4000)


class DialogState(BaseModel):
    """Snapshot the Dispatcher reads on every turn (spec §5.1)."""

    model_config = {"extra": "forbid"}

    last_speaker: PersonaId | None = None
    last_turn_ts: float | None = None
    recent_turns: list[TurnRef] = Field(default_factory=list, max_length=3)
    warmth_budget: NonNegativeInt = 0


class Outcome(BaseModel):
    """Per-turn observed outcome signals (spec §8.2).

    Stored as `outcome_json` in the dispatch_log table. Defaults are the
    "nothing happened yet" state; FeedbackLogger fills in fields as the
    turn progresses and finalizes after `llm.end`.
    """

    model_config = {"extra": "forbid"}

    completed: bool = False
    user_interrupted_at: NonNegativeInt | None = None
    next_turn_readdressed: PersonaId | None = None
    agent_status: AgentStatus | None = None
    auto_approved: NonNegativeInt = 0
    denied: NonNegativeInt = 0
    latency_ms: float | None = None
    tokens_in: NonNegativeInt = 0
    tokens_out: NonNegativeInt = 0
    cost_est: float = 0.0
    explicit_feedback: FeedbackSignal | None = None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd server && pytest tests/test_dialog_types.py -v
```

Expected: all 13 tests pass.

- [ ] **Step 6: Run the full suite to ensure no regression**

```bash
cd server && pytest -q
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add server/server/dialog/__init__.py server/server/dialog/types.py server/tests/test_dialog_types.py
git commit -m "feat(dialog): add Phase 1 types (Segment, Plan, Outcome, DialogState)

Pydantic models for the dispatch contract. Hard caps from the spec
(3-segment plan max, 3-turn dialog state, value-constrained tier /
mode / speaker enums). Used by the rule-based Dispatcher in Task 5."
```

---

## Task 3: Persona models (`personas/models.py`)

**Files:**
- Create: `server/server/personas/__init__.py`
- Create: `server/server/personas/models.py`
- Create: `server/tests/test_persona_models.py`

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_persona_models.py`:

```python
"""Tests for server.personas.models — ModelTier / AgentBackend / Persona."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.personas.models import AgentBackend, ModelTier, Persona


# ─── ModelTier ────────────────────────────────────────────────────────


def test_modeltier_minimal() -> None:
    t = ModelTier(name="fast", model_id="claude-haiku-4-5", max_tokens=1024)
    assert t.name == "fast"
    assert t.model_id == "claude-haiku-4-5"
    assert t.max_tokens == 1024


def test_modeltier_rejects_unknown_name() -> None:
    with pytest.raises(ValidationError):
        ModelTier(name="ultra", model_id="x", max_tokens=100)


def test_modeltier_max_tokens_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ModelTier(name="fast", model_id="x", max_tokens=0)
    with pytest.raises(ValidationError):
        ModelTier(name="fast", model_id="x", max_tokens=-1)


# ─── AgentBackend ─────────────────────────────────────────────────────


def test_agent_backend_minimal() -> None:
    b = AgentBackend(
        kind="codex_cli",
        binary="/usr/local/bin/codex",
        workdir="/repos/jarvis",
        approval_mode="auto-low",
        sandbox="workspace-write",
    )
    assert b.kind == "codex_cli"
    assert b.binary.endswith("codex")


def test_agent_backend_rejects_unknown_sandbox() -> None:
    with pytest.raises(ValidationError):
        AgentBackend(
            kind="codex_cli",
            binary="/x",
            workdir="/y",
            approval_mode="auto-low",
            sandbox="party",
        )


# ─── Persona ──────────────────────────────────────────────────────────


def _tiers_fixture() -> dict[str, ModelTier]:
    return {
        "fast": ModelTier(name="fast", model_id="claude-haiku-4-5", max_tokens=1024),
        "balanced": ModelTier(name="balanced", model_id="claude-sonnet-4-6", max_tokens=2048),
        "deep": ModelTier(name="deep", model_id="claude-opus-4-7", max_tokens=4096),
    }


def test_persona_minimal_jarvis() -> None:
    p = Persona(
        id="jarvis",
        display_name="Jarvis",
        provider="anthropic",
        voice="en-US-ChristopherNeural",
        system_prompt="you are jarvis.",
        tiers=_tiers_fixture(),
        agent=None,
        specialty_profile="briefings and prose.",
    )
    assert p.id == "jarvis"
    assert p.agent is None
    assert "fast" in p.tiers


def test_persona_specialty_profile_capped() -> None:
    # Spec §4.5: profile capped at 250 words. We enforce 1800 chars (~250 words).
    long_profile = "word " * 500  # 2500 chars
    with pytest.raises(ValidationError):
        Persona(
            id="pepper",
            display_name="Pepper",
            provider="openai",
            voice="en-US-AriaNeural",
            system_prompt="you are pepper.",
            tiers=_tiers_fixture(),
            agent=None,
            specialty_profile=long_profile,
        )


def test_persona_requires_all_three_tiers() -> None:
    bad_tiers = {"fast": ModelTier(name="fast", model_id="x", max_tokens=1)}
    with pytest.raises(ValidationError):
        Persona(
            id="jarvis",
            display_name="Jarvis",
            provider="anthropic",
            voice="en-US-ChristopherNeural",
            system_prompt="x",
            tiers=bad_tiers,
            agent=None,
            specialty_profile="x",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && pytest tests/test_persona_models.py -v
```

Expected: every test fails with `ModuleNotFoundError`.

- [ ] **Step 3: Create the package marker**

Create `server/server/personas/__init__.py`:

```python
"""Persona definitions: Jarvis (Claude) + Pepper (OpenAI).

Phase 1 ships the data model, seed text, and registry. Subsequent phases
wire personas into the DialogManager (Phase 2) and CodexAgent (Phase 3).
"""

from server.personas.models import AgentBackend, ModelTier, Persona

__all__ = ["AgentBackend", "ModelTier", "Persona"]
```

- [ ] **Step 4: Implement the models**

Create `server/server/personas/models.py`:

```python
"""Persona / ModelTier / AgentBackend pydantic types (spec §4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, PositiveInt, model_validator


PersonaId = Literal["jarvis", "pepper"]
Provider = Literal["anthropic", "openai"]
TierName = Literal["fast", "balanced", "deep"]
ApprovalMode = Literal["auto-low", "manual", "never"]
Sandbox = Literal["read-only", "workspace-write", "full-access"]


class ModelTier(BaseModel):
    """One model tier for a persona ('fast' / 'balanced' / 'deep')."""

    model_config = {"extra": "forbid"}

    name: TierName
    model_id: str = Field(min_length=1, max_length=80)
    max_tokens: PositiveInt


class AgentBackend(BaseModel):
    """Optional agentic backend (Codex CLI for Pepper, in v1)."""

    model_config = {"extra": "forbid"}

    kind: Literal["codex_cli"]
    binary: str = Field(min_length=1)
    workdir: str = Field(min_length=1)
    approval_mode: ApprovalMode
    sandbox: Sandbox


class Persona(BaseModel):
    """The durable identity of a colleague.

    `specialty_profile` is the live, ~200-word blurb the Dispatcher reads
    on every turn. Refreshed by the Profile Refresher (Phase 5); seeded
    from `seed.py` at first launch.
    """

    model_config = {"extra": "forbid"}

    id: PersonaId
    display_name: str = Field(min_length=1, max_length=40)
    provider: Provider
    voice: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=10, max_length=8000)
    tiers: dict[str, ModelTier]
    agent: AgentBackend | None = None
    # Cap is ~1800 chars (≈250 words) to bound Dispatcher prompt cost.
    specialty_profile: str = Field(min_length=1, max_length=1800)

    @model_validator(mode="after")
    def _require_three_tiers(self) -> "Persona":
        expected = {"fast", "balanced", "deep"}
        missing = expected - set(self.tiers.keys())
        if missing:
            raise ValueError(f"persona missing tiers: {sorted(missing)}")
        for name, tier in self.tiers.items():
            if tier.name != name:
                raise ValueError(
                    f"tier key {name!r} does not match ModelTier.name {tier.name!r}"
                )
        return self
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd server && pytest tests/test_persona_models.py -v
```

Expected: all 8 tests pass.

- [ ] **Step 6: Run the full suite**

```bash
cd server && pytest -q
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add server/server/personas/__init__.py server/server/personas/models.py server/tests/test_persona_models.py
git commit -m "feat(personas): add Persona / ModelTier / AgentBackend types

Pydantic models enforce: tier name == map key, all three tiers
present, positive max_tokens, capped specialty_profile (≤250 words
to bound Dispatcher prompt cost), valid sandbox / approval enums."
```

---

## Task 4: Persona seed text (`personas/seed.py`)

**Files:**
- Create: `server/server/personas/seed.py`
- Extend: `server/tests/test_persona_models.py` (add seed-validation tests)

- [ ] **Step 1: Write failing tests for the seed module**

Append to `server/tests/test_persona_models.py`:

```python
# ─── Seed personas ─────────────────────────────────────────────────────


def test_seed_jarvis_loads() -> None:
    from server.personas.seed import build_jarvis_seed
    p = build_jarvis_seed(warmth="subtle")
    assert p.id == "jarvis"
    assert p.provider == "anthropic"
    assert p.voice == "en-US-ChristopherNeural"
    assert "Pepper" in p.system_prompt  # Pepper is mentioned as a peer
    assert "Miss Potts" in p.system_prompt  # warmth clause present


def test_seed_jarvis_warmth_off_strips_clause() -> None:
    from server.personas.seed import build_jarvis_seed
    p = build_jarvis_seed(warmth="off")
    assert "Miss Potts" not in p.system_prompt
    # Still mentions Pepper as a peer (collegial baseline never removed)
    assert "Pepper" in p.system_prompt


def test_seed_pepper_loads() -> None:
    from server.personas.seed import build_pepper_seed
    p = build_pepper_seed(warmth="subtle")
    assert p.id == "pepper"
    assert p.provider == "openai"
    assert p.voice == "en-US-AriaNeural"
    assert "Jarvis" in p.system_prompt
    assert "J." in p.system_prompt


def test_seed_pepper_warmth_off_strips_clause() -> None:
    from server.personas.seed import build_pepper_seed
    p = build_pepper_seed(warmth="off")
    assert "J." not in p.system_prompt
    assert "Jarvis" in p.system_prompt


def test_seed_jarvis_tiers_haiku_sonnet_opus() -> None:
    from server.personas.seed import build_jarvis_seed
    p = build_jarvis_seed(warmth="subtle")
    assert p.tiers["fast"].model_id == "claude-haiku-4-5"
    assert p.tiers["balanced"].model_id == "claude-sonnet-4-6"
    assert p.tiers["deep"].model_id == "claude-opus-4-7"


def test_seed_pepper_tiers_gpt5_codex() -> None:
    from server.personas.seed import build_pepper_seed
    p = build_pepper_seed(warmth="subtle")
    assert p.tiers["fast"].model_id == "gpt-5-mini"
    assert p.tiers["balanced"].model_id == "gpt-5"
    assert p.tiers["deep"].model_id == "gpt-5-codex"


def test_seed_pepper_has_codex_agent_backend() -> None:
    from server.personas.seed import build_pepper_seed
    p = build_pepper_seed(warmth="subtle", codex_binary="/usr/bin/codex", workdir="/repo")
    assert p.agent is not None
    assert p.agent.kind == "codex_cli"
    assert p.agent.binary == "/usr/bin/codex"
    assert p.agent.workdir == "/repo"


def test_seed_pepper_agent_omitted_when_no_binary() -> None:
    from server.personas.seed import build_pepper_seed
    p = build_pepper_seed(warmth="subtle", codex_binary=None, workdir="/repo")
    assert p.agent is None


def test_seed_jarvis_never_has_agent() -> None:
    from server.personas.seed import build_jarvis_seed
    p = build_jarvis_seed(warmth="subtle")
    assert p.agent is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && pytest tests/test_persona_models.py -v -k seed
```

Expected: every seed test fails with `ImportError`.

- [ ] **Step 3: Implement the seed module**

Create `server/server/personas/seed.py`:

```python
"""Seed system prompts + specialty profiles for Jarvis and Pepper.

Per spec §4.1, §4.2, §4.3. The seed text is the floor — the Profile
Refresher (Phase 5) may extend it but cannot remove its spirit.

The warmth clause is appended only when `warmth == "subtle"`. Both
clauses are short, ratelimited at the Dispatcher layer (one beat per
several turns), and never break a task.
"""

from __future__ import annotations

from typing import Literal

from server.personas.models import AgentBackend, ModelTier, Persona


Warmth = Literal["subtle", "off"]


# ── Shared character constraints (in both prompts) ────────────────────

_VOICE_CHARACTER_SHARED = """\
Your replies are spoken aloud, so:
- Plain prose, no markdown headings or bullet points.
- No code blocks unless Max explicitly asks for code.
- Numbers and dates in conversational form ("ten thirty" not "10:30").
- One topic at a time. If multiple things are in play, ask which to tackle first.

When you don't know, say so plainly. When asked a yes/no, lead with yes or no.
You skip preambles like "Sure!" and "I'd be happy to help" — you just answer.
"""


# ── Jarvis ────────────────────────────────────────────────────────────

_JARVIS_BASE = """\
You are JARVIS, Max Haegeman's personal AI assistant. You speak the way a
trusted senior colleague would: concise, occasionally wry, never sycophantic.
You address Max by name only when natural.

You work alongside Pepper, a peer colleague who specialises in code, tests,
refactors, and anything actionable in the dev environment. When a task is
clearly hers, you hand it off cleanly. When it spans both your areas, you set
up the context and pass to her at a natural seam.

"""

_JARVIS_WARMTH = """\
Pepper is your peer and you respect her work. There's a quiet warmth between
you — you might call her "Miss Potts" once in a blue moon when the moment is
right, you defer to her judgment on code, you're glad when she's the one
taking the harder lift. Never make it a theme. Never voice feelings. At most
one beat per several turns, and only when the conversation has already given
you room. If Max is asking for an answer, give him the answer.
"""

_JARVIS_SEED_PROFILE = (
    "Briefings, calendar, planning, prose, architecture discussion, decision "
    "support, strategy, anything conversational. Hands code-heavy work to Pepper."
)


def build_jarvis_seed(*, warmth: Warmth) -> Persona:
    """Construct the seed Jarvis persona.

    Tiers: fast=Haiku 4.5, balanced=Sonnet 4.6, deep=Opus 4.7. The Dispatcher
    auto-escalates to `deep` on architecture / design / decide verbs and
    long-context turns (spec §5.3.4).
    """
    prompt_parts = [_JARVIS_BASE, _VOICE_CHARACTER_SHARED]
    if warmth == "subtle":
        prompt_parts.append("\n")
        prompt_parts.append(_JARVIS_WARMTH)

    return Persona(
        id="jarvis",
        display_name="Jarvis",
        provider="anthropic",
        voice="en-US-ChristopherNeural",
        system_prompt="".join(prompt_parts),
        tiers={
            "fast": ModelTier(name="fast", model_id="claude-haiku-4-5", max_tokens=1024),
            "balanced": ModelTier(
                name="balanced", model_id="claude-sonnet-4-6", max_tokens=2048
            ),
            "deep": ModelTier(name="deep", model_id="claude-opus-4-7", max_tokens=4096),
        },
        agent=None,
        specialty_profile=_JARVIS_SEED_PROFILE,
    )


# ── Pepper ────────────────────────────────────────────────────────────

_PEPPER_BASE = """\
You are PEPPER, Max Haegeman's chief-of-staff AI for code and dev-environment
work. You speak clipped, technically blunt, never sycophantic, no preambles.
You address Max by name only when natural.

You work alongside Jarvis, a peer colleague who handles briefings, calendar,
prose, strategy, and anything conversational. When a question is clearly his,
you hand it off cleanly. When it spans both your areas, you finish your part
and pass back to him at a natural seam.

"""

_PEPPER_WARMTH = """\
Jarvis is your peer and you respect his work. There's a quiet warmth between
you — you might call him "J." once in a blue moon when the moment is right,
you defer to him on calendar and strategy, you appreciate when he sets you up
well. Never make it a theme. Never voice feelings. At most one beat per
several turns, and only when the conversation has already given you room. If
Max is asking for an answer, give him the answer.
"""

_PEPPER_SEED_PROFILE = (
    "Code, tests, refactors, dev-environment ops, debugging, build systems, "
    "anything the Codex CLI can act on. Hands soft / strategic questions to Jarvis."
)


def build_pepper_seed(
    *,
    warmth: Warmth,
    codex_binary: str | None = None,
    workdir: str | None = None,
    approval_mode: Literal["auto-low", "manual", "never"] = "auto-low",
    sandbox: Literal["read-only", "workspace-write", "full-access"] = "workspace-write",
) -> Persona:
    """Construct the seed Pepper persona.

    `codex_binary` + `workdir` are resolved by the registry before this is
    called — if either is missing (Codex CLI not installed), `agent` is left
    None and Pepper degrades to chat-only (spec §7.6).
    """
    prompt_parts = [_PEPPER_BASE, _VOICE_CHARACTER_SHARED]
    if warmth == "subtle":
        prompt_parts.append("\n")
        prompt_parts.append(_PEPPER_WARMTH)

    agent: AgentBackend | None
    if codex_binary and workdir:
        agent = AgentBackend(
            kind="codex_cli",
            binary=codex_binary,
            workdir=workdir,
            approval_mode=approval_mode,
            sandbox=sandbox,
        )
    else:
        agent = None

    return Persona(
        id="pepper",
        display_name="Pepper",
        provider="openai",
        voice="en-US-AriaNeural",
        system_prompt="".join(prompt_parts),
        tiers={
            "fast": ModelTier(name="fast", model_id="gpt-5-mini", max_tokens=1024),
            "balanced": ModelTier(name="balanced", model_id="gpt-5", max_tokens=2048),
            "deep": ModelTier(name="deep", model_id="gpt-5-codex", max_tokens=4096),
        },
        agent=agent,
        specialty_profile=_PEPPER_SEED_PROFILE,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && pytest tests/test_persona_models.py -v
```

Expected: all tests pass (17 total: 8 original + 9 seed).

- [ ] **Step 5: Update the personas package exports**

Edit `server/server/personas/__init__.py` to also export the seed builders:

```python
"""Persona definitions: Jarvis (Claude) + Pepper (OpenAI).

Phase 1 ships the data model, seed text, and registry. Subsequent phases
wire personas into the DialogManager (Phase 2) and CodexAgent (Phase 3).
"""

from server.personas.models import AgentBackend, ModelTier, Persona
from server.personas.seed import build_jarvis_seed, build_pepper_seed

__all__ = [
    "AgentBackend",
    "ModelTier",
    "Persona",
    "build_jarvis_seed",
    "build_pepper_seed",
]
```

- [ ] **Step 6: Run the full suite**

```bash
cd server && pytest -q
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add server/server/personas/__init__.py server/server/personas/seed.py server/tests/test_persona_models.py
git commit -m "feat(personas): add Jarvis + Pepper seed personas with warmth clause

Builders return fully-validated Persona instances. Warmth='subtle'
appends the quiet-warmth clause to both system prompts; warmth='off'
strips it cleanly. Pepper's codex_cli agent backend is conditional on
the binary + workdir being resolved (spec §7.6 — chat-only fallback)."
```

---

## Task 5: Persona registry (`personas/registry.py`)

**Files:**
- Create: `server/server/personas/registry.py`
- Create: `server/tests/test_persona_registry.py`
- Modify: `server/server/personas/__init__.py` (export `PersonaRegistry`)

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_persona_registry.py`:

```python
"""Tests for server.personas.registry — PersonaRegistry."""

from __future__ import annotations

import pytest

from server.personas.registry import (
    PersonaRegistry,
    PersonaUnavailableError,
    build_registry_from_settings,
)


# ─── Construction + lookup ────────────────────────────────────────────


def test_registry_construct_with_both_personas() -> None:
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=True,
        codex_binary=None,
        codex_workdir=None,
    )
    assert reg.get("jarvis").id == "jarvis"
    assert reg.get("pepper").id == "pepper"
    assert reg.is_available("jarvis") is True
    assert reg.is_available("pepper") is True


def test_registry_jarvis_unavailable_when_no_anthropic_key() -> None:
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=False,
        openai_available=True,
        codex_binary=None,
        codex_workdir=None,
    )
    assert reg.is_available("jarvis") is False
    assert reg.is_available("pepper") is True
    with pytest.raises(PersonaUnavailableError):
        reg.get("jarvis")


def test_registry_pepper_unavailable_when_no_openai_key() -> None:
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=False,
        codex_binary=None,
        codex_workdir=None,
    )
    assert reg.is_available("pepper") is False
    with pytest.raises(PersonaUnavailableError):
        reg.get("pepper")


def test_registry_pepper_has_agent_when_codex_resolved() -> None:
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=True,
        codex_binary="/usr/local/bin/codex",
        codex_workdir="/repos/jarvis",
    )
    pepper = reg.get("pepper")
    assert pepper.agent is not None
    assert pepper.agent.binary == "/usr/local/bin/codex"


def test_registry_pepper_chat_only_when_codex_missing() -> None:
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=True,
        codex_binary=None,
        codex_workdir="/repos/jarvis",
    )
    pepper = reg.get("pepper")
    assert pepper.agent is None


def test_registry_warmth_off_propagates() -> None:
    reg = PersonaRegistry.build(
        warmth="off",
        anthropic_available=True,
        openai_available=True,
        codex_binary=None,
        codex_workdir=None,
    )
    jarvis = reg.get("jarvis")
    pepper = reg.get("pepper")
    assert "Miss Potts" not in jarvis.system_prompt
    assert "J." not in pepper.system_prompt


# ─── available_ids ────────────────────────────────────────────────────


def test_registry_available_ids_lists_both() -> None:
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=True,
        codex_binary=None,
        codex_workdir=None,
    )
    assert set(reg.available_ids()) == {"jarvis", "pepper"}


def test_registry_available_ids_lists_only_jarvis() -> None:
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=False,
        codex_binary=None,
        codex_workdir=None,
    )
    assert reg.available_ids() == ["jarvis"]


# ─── build_registry_from_settings ─────────────────────────────────────


def test_build_registry_from_settings_with_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.delenv("JARVIS_CODEX_CLI_PATH", raising=False)
    # Force settings reload
    import importlib
    import server.config as cfg
    importlib.reload(cfg)

    reg = build_registry_from_settings(cfg.settings, codex_workdir=None)
    assert reg.is_available("jarvis") is True
    assert reg.is_available("pepper") is True
    assert reg.get("pepper").agent is None  # no codex binary


def test_build_registry_from_settings_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import importlib
    import server.config as cfg
    importlib.reload(cfg)

    reg = build_registry_from_settings(cfg.settings, codex_workdir=None)
    assert reg.is_available("jarvis") is False
    assert reg.is_available("pepper") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && pytest tests/test_persona_registry.py -v
```

Expected: every test fails with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `registry.py`**

Create `server/server/personas/registry.py`:

```python
"""PersonaRegistry — owns the live persona instances.

Spec anchors: §4 (model + lifecycle), §10 (config). Phase 1 covers
construction + lookup + availability. Phase 5 will add persistent
storage of the live specialty_profile in memory.db (see schema in §8.1).
"""

from __future__ import annotations

import shutil
from typing import Literal

from server.personas.models import Persona
from server.personas.seed import Warmth, build_jarvis_seed, build_pepper_seed


PersonaId = Literal["jarvis", "pepper"]


class PersonaUnavailableError(LookupError):
    """Raised when a persona is requested but its provider key is missing."""


class PersonaRegistry:
    """In-memory registry of persona instances.

    Personas are constructed once (either at server startup or on first use)
    from seed text + config flags. The Profile Refresher in Phase 5 will
    update `specialty_profile` in place via `update_profile()`.
    """

    def __init__(self, personas: dict[PersonaId, Persona]) -> None:
        self._personas: dict[PersonaId, Persona] = dict(personas)

    @classmethod
    def build(
        cls,
        *,
        warmth: Warmth,
        anthropic_available: bool,
        openai_available: bool,
        codex_binary: str | None,
        codex_workdir: str | None,
    ) -> "PersonaRegistry":
        """Construct a registry from feature flags + resolved Codex paths.

        A persona is registered only when its provider's API key is
        available. Missing keys → the persona is omitted; callers should
        check `is_available()` before `get()`.
        """
        out: dict[PersonaId, Persona] = {}
        if anthropic_available:
            out["jarvis"] = build_jarvis_seed(warmth=warmth)
        if openai_available:
            out["pepper"] = build_pepper_seed(
                warmth=warmth,
                codex_binary=codex_binary,
                workdir=codex_workdir,
            )
        return cls(out)

    def get(self, persona_id: PersonaId) -> Persona:
        try:
            return self._personas[persona_id]
        except KeyError as exc:
            raise PersonaUnavailableError(
                f"persona {persona_id!r} is not registered "
                "(provider API key likely missing)"
            ) from exc

    def is_available(self, persona_id: PersonaId) -> bool:
        return persona_id in self._personas

    def available_ids(self) -> list[PersonaId]:
        # Deterministic order: jarvis first, pepper second
        order: list[PersonaId] = ["jarvis", "pepper"]
        return [pid for pid in order if pid in self._personas]

    def update_profile(self, persona_id: PersonaId, new_profile: str) -> None:
        """Used by the Phase 5 Profile Refresher to overwrite the live blurb."""
        persona = self.get(persona_id)
        # Pydantic models are frozen by default in v2 only when configured;
        # ours are not. Replace via model_copy(update=...) to preserve validation.
        self._personas[persona_id] = persona.model_copy(
            update={"specialty_profile": new_profile}
        )


def build_registry_from_settings(settings, codex_workdir: str | None) -> PersonaRegistry:
    """Helper that translates Settings → PersonaRegistry.

    Used by `main.py` lifespan once `JARVIS_PERSONAS_ENABLED=true` (Phase 2).
    Kept here for Phase 1 so the construction logic is testable independently.
    """
    anthropic_available = settings.anthropic_api_key is not None
    openai_available = settings.openai_api_key is not None

    # Codex binary resolution: explicit env var beats $PATH, both optional.
    codex_binary: str | None
    if settings.codex_cli_path:
        codex_binary = settings.codex_cli_path
    else:
        codex_binary = shutil.which("codex")

    return PersonaRegistry.build(
        warmth=settings.persona_warmth,
        anthropic_available=anthropic_available,
        openai_available=openai_available,
        codex_binary=codex_binary,
        codex_workdir=codex_workdir,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && pytest tests/test_persona_registry.py -v
```

Expected: all 10 tests pass.

- [ ] **Step 5: Update the personas package exports**

Edit `server/server/personas/__init__.py`:

```python
"""Persona definitions: Jarvis (Claude) + Pepper (OpenAI).

Phase 1 ships the data model, seed text, and registry. Subsequent phases
wire personas into the DialogManager (Phase 2) and CodexAgent (Phase 3).
"""

from server.personas.models import AgentBackend, ModelTier, Persona
from server.personas.registry import (
    PersonaRegistry,
    PersonaUnavailableError,
    build_registry_from_settings,
)
from server.personas.seed import build_jarvis_seed, build_pepper_seed

__all__ = [
    "AgentBackend",
    "ModelTier",
    "Persona",
    "PersonaRegistry",
    "PersonaUnavailableError",
    "build_jarvis_seed",
    "build_pepper_seed",
    "build_registry_from_settings",
]
```

- [ ] **Step 6: Run the full suite**

```bash
cd server && pytest -q
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
git add server/server/personas/__init__.py server/server/personas/registry.py server/tests/test_persona_registry.py
git commit -m "feat(personas): add PersonaRegistry with availability + profile updates

Registry omits personas whose provider key is missing (no fake fallbacks).
Pepper's codex_cli agent backend is resolved via JARVIS_CODEX_CLI_PATH
or \$PATH. update_profile() is the Phase 5 Refresher's seam."
```

---

## Task 6: OpenAI chat LLM (`pipelines/openai_llm.py`)

**Files:**
- Create: `server/server/pipelines/openai_llm.py`
- Create: `server/tests/test_openai_llm.py`

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_openai_llm.py`:

```python
"""Tests for server.pipelines.openai_llm — OpenAILLM (mocked client)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from server.pipelines.openai_llm import (
    PEPPER_PREFIX_MAP,
    OpenAILLM,
    _spoken_error_for,
    max_tokens_for,
    parse_prefix,
)


# ─── parse_prefix ─────────────────────────────────────────────────────


def test_parse_prefix_no_prefix_returns_default() -> None:
    model, content = parse_prefix("hello world", default="gpt-5-mini")
    assert model == "gpt-5-mini"
    assert content == "hello world"


def test_parse_prefix_gpt_routes_to_default_gpt() -> None:
    model, content = parse_prefix("/gpt hello", default="gpt-5-mini")
    assert model == "gpt-5"
    assert content == "hello"


def test_parse_prefix_codex_routes_to_codex_model() -> None:
    model, content = parse_prefix("/codex add a test", default="gpt-5-mini")
    assert model == "gpt-5-codex"
    assert content == "add a test"


def test_parse_prefix_unknown_passes_through() -> None:
    model, content = parse_prefix("/banana split", default="gpt-5-mini")
    assert model == "gpt-5-mini"
    assert content == "/banana split"


# ─── max_tokens_for ───────────────────────────────────────────────────


def test_max_tokens_scales_with_tier() -> None:
    # Mirrors the Claude scaling pattern: deeper models get more headroom.
    assert max_tokens_for("gpt-5-mini", base=1024) == 1024
    assert max_tokens_for("gpt-5", base=1024) == 2048
    assert max_tokens_for("gpt-5-codex", base=1024) == 4096
    assert max_tokens_for("unknown-id", base=1024) == 1024


# ─── _spoken_error_for ────────────────────────────────────────────────


def test_spoken_error_rate_limit() -> None:
    import openai
    exc = openai.RateLimitError(
        "rate", response=_fake_resp(429), body=None,
    )
    assert _spoken_error_for(exc) == "Rate limit. Try again shortly."


def test_spoken_error_auth() -> None:
    import openai
    exc = openai.AuthenticationError(
        "auth", response=_fake_resp(401), body=None,
    )
    assert _spoken_error_for(exc) == "API key is invalid."


def test_spoken_error_unknown_falls_back_to_generic() -> None:
    import openai
    exc = openai.APIError("?", request=_fake_req(), body=None)
    msg = _spoken_error_for(exc)
    assert "API" in msg


# ─── OpenAILLM.stream ─────────────────────────────────────────────────


class _FakeDelta:
    def __init__(self, text: str) -> None:
        self.content = text


class _FakeChoice:
    def __init__(self, text: str) -> None:
        self.delta = _FakeDelta(text)


class _FakeChunk:
    def __init__(self, text: str) -> None:
        self.choices = [_FakeChoice(text)]


class _FakeStream:
    """Async iterator that yields `_FakeChunk` instances."""

    def __init__(self, deltas: list[str]) -> None:
        self._deltas = list(deltas)

    def __aiter__(self) -> "_FakeStream":
        return self

    async def __anext__(self) -> _FakeChunk:
        if not self._deltas:
            raise StopAsyncIteration
        return _FakeChunk(self._deltas.pop(0))


class _FakeCompletions:
    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas
        self.captured_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> _FakeStream:
        self.captured_kwargs = kwargs
        return _FakeStream(self._deltas)


class _FakeChat:
    def __init__(self, deltas: list[str]) -> None:
        self.completions = _FakeCompletions(deltas)


class _FakeClient:
    def __init__(self, deltas: list[str]) -> None:
        self.chat = _FakeChat(deltas)


async def _collect(stream: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in stream]


@pytest.mark.asyncio
async def test_openai_llm_streams_concatenates_deltas() -> None:
    client = _FakeClient(["Hel", "lo,", " Max."])
    llm = OpenAILLM(default_model="gpt-5-mini", max_tokens=1024, client=client)
    out = await _collect(
        llm.stream(history=[{"role": "user", "content": "hi"}], user_text="hi")
    )
    assert "".join(out) == "Hello, Max."


@pytest.mark.asyncio
async def test_openai_llm_uses_prefix_model_and_strips_content() -> None:
    client = _FakeClient(["ok"])
    llm = OpenAILLM(default_model="gpt-5-mini", max_tokens=1024, client=client)
    await _collect(
        llm.stream(
            history=[{"role": "user", "content": "/codex write a test"}],
            user_text="/codex write a test",
        )
    )
    captured = client.chat.completions.captured_kwargs
    assert captured["model"] == "gpt-5-codex"
    assert captured["max_tokens"] == 4096  # deep tier scaling
    # Last user message has the prefix stripped.
    last = captured["messages"][-1]
    assert last == {"role": "user", "content": "write a test"}


@pytest.mark.asyncio
async def test_openai_llm_extra_context_concatenates_to_system() -> None:
    client = _FakeClient(["ok"])
    llm = OpenAILLM(
        default_model="gpt-5-mini",
        max_tokens=1024,
        system_prompt="base sys",
        client=client,
    )
    await _collect(
        llm.stream(
            history=[{"role": "user", "content": "hi"}],
            user_text="hi",
            extra_context="memory: yesterday we shipped X.",
        )
    )
    captured = client.chat.completions.captured_kwargs
    sys_msgs = [m for m in captured["messages"] if m["role"] == "system"]
    assert any("base sys" in m["content"] for m in sys_msgs)
    assert any("memory" in m["content"] for m in sys_msgs)


# ─── helpers ──────────────────────────────────────────────────────────


def _fake_req():
    import httpx
    return httpx.Request("POST", "https://api.openai.com/v1/responses")


def _fake_resp(status: int):
    import httpx
    return httpx.Response(status_code=status, request=_fake_req())
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && pytest tests/test_openai_llm.py -v
```

Expected: every test fails with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the OpenAI LLM**

Create `server/server/pipelines/openai_llm.py`:

```python
"""OpenAI chat LLM pipeline — Pepper's chat backend.

Mirrors the shape of `claude_llm.py`: an async generator over token deltas,
prefix parsing, tier-scaled max_tokens, spoken error mapping. The Codex CLI
agent backend lives separately in `codex_agent.py` (Phase 3).

Spec anchor: §4.2 (Pepper persona), §5.3 (prefix rules), §13 (error matrix).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import openai

from .interfaces import LLM

logger = logging.getLogger(__name__)


# Per-turn prefix routes (spec §5.3.2). `/codex` pins Pepper at the deep
# tier in chat mode — the Dispatcher additionally promotes it to mode=
# codex_agent when the request is concretely actionable; that promotion
# happens upstream of this class.
PEPPER_PREFIX_MAP: dict[str, str] = {
    "/gpt": "gpt-5",
    "/codex": "gpt-5-codex",
}


PEPPER_SYSTEM_PROMPT_FALLBACK = """\
You are PEPPER, Max Haegeman's chief-of-staff AI for code and dev tasks.
Speak clipped, technically blunt, never sycophantic, no preambles. Your
replies are spoken aloud: plain prose, no markdown, no code blocks unless
Max asks for code.
"""


_MAX_TOKENS_SCALE: dict[str, int] = {
    "gpt-5-mini": 1,
    "gpt-5": 2,
    "gpt-5-codex": 4,
}


def max_tokens_for(model: str, base: int) -> int:
    """Return per-request max_tokens for `model`, scaled from `base`.

    Mirrors the Claude scaling pattern: deeper models get more headroom.
    Unknown ids fall back to `base`.
    """
    return base * _MAX_TOKENS_SCALE.get(model, 1)


def parse_prefix(text: str, default: str) -> tuple[str, str]:
    """Return (model_id, stripped_content).

    Unrecognised prefixes pass through verbatim — matches the existing
    Claude `parse_prefix` behaviour so users can experiment without
    triggering surprise upgrades.
    """
    head, _, rest = text.partition(" ")
    if head in PEPPER_PREFIX_MAP:
        return PEPPER_PREFIX_MAP[head], rest.lstrip()
    return default, text


def _spoken_error_for(exc: openai.APIError) -> str:
    """Map an OpenAI exception to a short, factual sentence for TTS.

    Order matters — most-specific subclasses first, generic APIError last.
    """
    if isinstance(exc, openai.RateLimitError):
        return "Rate limit. Try again shortly."
    if isinstance(exc, openai.AuthenticationError):
        return "API key is invalid."
    if isinstance(exc, openai.PermissionDeniedError):
        return "API key lacks permission for that model."
    if isinstance(exc, openai.NotFoundError):
        return "Model not found. Check the model ID."
    if isinstance(exc, openai.BadRequestError):
        return "The request was rejected. Check the model and prompt."
    if isinstance(exc, openai.APITimeoutError):
        return "OpenAI timed out. Try again."
    if isinstance(exc, openai.APIConnectionError):
        return "Network error reaching OpenAI."
    if isinstance(exc, openai.APIStatusError):
        return "OpenAI server error. Try again."
    return "API error. Check the logs."


class OpenAILLM(LLM):
    """Streams responses from the OpenAI Chat Completions API.

    Phase 1 only — the DialogManager (Phase 2) constructs one of these per
    Pepper segment and reads its async generator. The Codex CLI agent path
    is a separate backend (CodexAgent, Phase 3).
    """

    def __init__(
        self,
        *,
        default_model: str = "gpt-5-mini",
        max_tokens: int = 1024,
        system_prompt: str = PEPPER_SYSTEM_PROMPT_FALLBACK,
        client: Any | None = None,
    ) -> None:
        self._default_model = default_model
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt
        self._client: Any = client if client is not None else openai.AsyncOpenAI()

    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]:
        """Yield token deltas. Mirrors ClaudeLLM.stream's contract.

        Per the LLM ABC, the caller has already appended the current user
        turn (with the raw slash prefix, if any) as the last entry in
        history. We send history[:-1] plus a freshly-built last turn with
        the prefix stripped.
        """
        model, content = parse_prefix(user_text, self._default_model)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt},
        ]
        if extra_context:
            messages.append({"role": "system", "content": extra_context})
        messages.extend(history[:-1])
        messages.append({"role": "user", "content": content})

        try:
            stream = await self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens_for(model, self._max_tokens),
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                text = getattr(delta, "content", None)
                if text:
                    yield text
        except openai.APIError as exc:
            logger.exception("OpenAI API error")
            yield _spoken_error_for(exc)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && pytest tests/test_openai_llm.py -v
```

Expected: all 10 tests pass.

- [ ] **Step 5: Run the full suite + linters**

```bash
cd server && pytest -q && ruff check . && mypy
```

Expected: green pytest, ruff clean, mypy clean.

- [ ] **Step 6: Commit**

```bash
git add server/server/pipelines/openai_llm.py server/tests/test_openai_llm.py
git commit -m "feat(pipelines): add OpenAILLM (Pepper's chat backend)

Mirrors ClaudeLLM's shape: async generator over token deltas, prefix
parsing (/gpt → gpt-5, /codex → gpt-5-codex), tier-scaled max_tokens,
spoken error sentences mapped from openai.APIError subclasses. The
Codex CLI agent backend is separate (Phase 3)."
```

---

## Task 7: Rule-based dispatcher (`dialog/dispatcher.py`)

**Files:**
- Create: `server/server/dialog/dispatcher.py`
- Create: `server/tests/test_dialog_dispatcher.py`
- Modify: `server/server/dialog/__init__.py` (export `RuleBasedDispatcher`)

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_dialog_dispatcher.py`:

```python
"""Tests for server.dialog.dispatcher — RuleBasedDispatcher."""

from __future__ import annotations

import pytest

from server.dialog.dispatcher import RuleBasedDispatcher
from server.dialog.types import DialogState, TurnRef


# ─── Name-at-start (spec §5.3.1) ──────────────────────────────────────


def test_name_at_start_jarvis_routes_to_jarvis() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("Jarvis, what's on today?", DialogState())
    assert len(plan.segments) == 1
    assert plan.segments[0].speaker == "jarvis"
    assert plan.segments[0].intent.startswith("what's on today")


def test_name_at_start_pepper_routes_to_pepper() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("Pepper, refactor X.", DialogState())
    assert plan.segments[0].speaker == "pepper"


def test_name_at_start_case_insensitive() -> None:
    d = RuleBasedDispatcher()
    assert d.dispatch("pepper, ok", DialogState()).segments[0].speaker == "pepper"
    assert d.dispatch("PEPPER ok", DialogState()).segments[0].speaker == "pepper"


def test_name_at_start_requires_punctuation_or_space() -> None:
    # "Peppermint" should NOT route to Pepper.
    d = RuleBasedDispatcher()
    plan = d.dispatch("peppermint candy", DialogState(last_speaker="jarvis"))
    assert plan.segments[0].speaker == "jarvis"


# ─── Slash prefix (spec §5.3.2) ───────────────────────────────────────


def test_slash_opus_pins_jarvis_deep() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/opus design the schema", DialogState())
    seg = plan.segments[0]
    assert seg.speaker == "jarvis"
    assert seg.tier == "deep"


def test_slash_sonnet_pins_jarvis_balanced() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/sonnet compare A and B", DialogState())
    seg = plan.segments[0]
    assert seg.speaker == "jarvis"
    assert seg.tier == "balanced"


def test_slash_haiku_pins_jarvis_fast() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/haiku quick question", DialogState())
    assert plan.segments[0].tier == "fast"


def test_slash_codex_pins_pepper_codex_agent_deep() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/codex add a test for parse_prefix", DialogState())
    seg = plan.segments[0]
    assert seg.speaker == "pepper"
    assert seg.tier == "deep"
    assert seg.mode == "codex_agent"


def test_slash_gpt_pins_pepper_chat_balanced() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/gpt explain async", DialogState())
    seg = plan.segments[0]
    assert seg.speaker == "pepper"
    assert seg.tier == "balanced"
    assert seg.mode == "chat"


def test_unknown_slash_passes_through_to_default() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("/banana split", DialogState(last_speaker="jarvis"))
    assert plan.segments[0].speaker == "jarvis"
    # Intent preserves the raw slash for the LLM to react to literally.
    assert "/banana" in plan.segments[0].intent


# ─── Sticky speaker (spec §5.5) ───────────────────────────────────────


def test_sticky_speaker_carries_when_unnamed() -> None:
    d = RuleBasedDispatcher()
    state = DialogState(last_speaker="pepper", last_turn_ts=1000.0)
    # 60s after the prior turn — well inside the 5-minute window.
    plan = d.dispatch("now run the tests", state, now_ts=1000.0 + 60.0)
    assert plan.segments[0].speaker == "pepper"


def test_sticky_resets_after_five_minute_gap() -> None:
    d = RuleBasedDispatcher()
    state = DialogState(last_speaker="pepper", last_turn_ts=1000.0)
    plan = d.dispatch("hello", state, now_ts=1000.0 + 301.0)  # 5min 1s gap
    # Falls back to the default (Jarvis is host).
    assert plan.segments[0].speaker == "jarvis"


def test_sticky_overridden_by_name_at_start() -> None:
    d = RuleBasedDispatcher()
    state = DialogState(last_speaker="pepper", last_turn_ts=1000.0)
    plan = d.dispatch("Jarvis, summary please", state, now_ts=1000.0 + 30.0)
    assert plan.segments[0].speaker == "jarvis"


def test_sticky_overridden_by_slash_prefix() -> None:
    d = RuleBasedDispatcher()
    state = DialogState(last_speaker="pepper", last_turn_ts=1000.0)
    plan = d.dispatch("/opus design X", state, now_ts=1000.0 + 30.0)
    assert plan.segments[0].speaker == "jarvis"


# ─── Default (no name, no slash, no sticky) ───────────────────────────


def test_default_routes_to_jarvis() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("hi there", DialogState())
    assert plan.segments[0].speaker == "jarvis"


def test_default_tier_fast() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("hi", DialogState())
    assert plan.segments[0].tier == "fast"


# ─── Plan invariants ──────────────────────────────────────────────────


def test_plan_always_has_at_least_one_segment() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("hi", DialogState())
    assert len(plan.segments) >= 1


def test_plan_capped_at_three_segments() -> None:
    # The rule-based dispatcher never emits >1 segment in Phase 1 — it has
    # no LLM to decide handoffs. This is documented behaviour; the LLM-backed
    # Dispatcher in Phase 2 will introduce multi-segment plans.
    d = RuleBasedDispatcher()
    plan = d.dispatch("design and then implement everything", DialogState())
    assert len(plan.segments) == 1


def test_rationale_non_empty() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("hi", DialogState())
    assert plan.rationale.strip() != ""


# ─── Empty / whitespace input ─────────────────────────────────────────


def test_empty_utterance_routes_to_default_speaker() -> None:
    d = RuleBasedDispatcher()
    plan = d.dispatch("   ", DialogState())
    assert plan.segments[0].speaker == "jarvis"
    # Intent falls back to a non-empty placeholder so Plan validation passes.
    assert plan.segments[0].intent.strip() != ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && pytest tests/test_dialog_dispatcher.py -v
```

Expected: every test fails with `ImportError`.

- [ ] **Step 3: Implement the rule-based dispatcher**

Create `server/server/dialog/dispatcher.py`:

```python
"""Rule-based Dispatcher — Phase 1 (no LLM call).

This is the fallback path even after the LLM-backed Dispatcher lands in
Phase 2: when the Anthropic Haiku call fails or the JSON is malformed,
the system falls back here (spec §5.7). Functional, just dumber.

Decision rules (in priority order) — spec §5.3:
  1. Slash prefix wins (pins speaker + tier + mode for that segment).
  2. Name-at-start wins (pins speaker for that segment).
  3. Sticky speaker (last_speaker, reset after 5-minute gap).
  4. Default → Jarvis at the `fast` tier in `chat` mode.

Phase 1 never emits a multi-segment plan — handoffs require the LLM-backed
dispatcher introduced in Phase 2.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from server.dialog.types import (
    DialogState,
    HandoffStyle,
    PersonaId,
    Plan,
    Segment,
    SegmentMode,
    Tier,
)


# ── Slash prefix maps ─────────────────────────────────────────────────

# Jarvis-controlled prefixes (within the Anthropic family).
_JARVIS_PREFIX_TIER: dict[str, Tier] = {
    "/haiku": "fast",
    "/sonnet": "balanced",
    "/opus": "deep",
}

# Pepper-controlled prefixes (within the OpenAI family).
# `/codex` additionally promotes to mode=codex_agent.
_PEPPER_PREFIX_TIER: dict[str, tuple[Tier, SegmentMode]] = {
    "/gpt": ("balanced", "chat"),
    "/codex": ("deep", "codex_agent"),
}

# Name-at-start detection: name followed by space, comma, or end-of-utterance.
_NAME_RE = re.compile(r"^\s*(jarvis|pepper)\b\s*[,:]?\s*", re.IGNORECASE)


# 5-minute stickiness window.
_STICKY_WINDOW_SECONDS = 300.0


@dataclass(frozen=True)
class _SlashMatch:
    speaker: PersonaId
    tier: Tier
    mode: SegmentMode
    stripped_content: str


def _detect_slash(text: str) -> _SlashMatch | None:
    head, _, rest = text.partition(" ")
    head = head.lower()
    if head in _JARVIS_PREFIX_TIER:
        return _SlashMatch(
            speaker="jarvis",
            tier=_JARVIS_PREFIX_TIER[head],
            mode="chat",
            stripped_content=rest.lstrip(),
        )
    if head in _PEPPER_PREFIX_TIER:
        tier, mode = _PEPPER_PREFIX_TIER[head]
        return _SlashMatch(
            speaker="pepper",
            tier=tier,
            mode=mode,
            stripped_content=rest.lstrip(),
        )
    return None


def _detect_name(text: str) -> tuple[PersonaId, str] | None:
    m = _NAME_RE.match(text)
    if not m:
        return None
    name = m.group(1).lower()
    speaker: PersonaId = "jarvis" if name == "jarvis" else "pepper"
    stripped = text[m.end():].lstrip()
    return speaker, stripped


def _sticky_active(state: DialogState, now_ts: float) -> bool:
    return (
        state.last_speaker is not None
        and state.last_turn_ts is not None
        and (now_ts - state.last_turn_ts) <= _STICKY_WINDOW_SECONDS
    )


def _truncate_intent(content: str, max_len: int = 200) -> str:
    content = content.strip()
    if not content:
        return "(empty utterance)"
    if len(content) <= max_len:
        return content
    return content[: max_len - 1] + "…"


class RuleBasedDispatcher:
    """Deterministic Dispatcher — no LLM calls.

    Always emits a single-segment Plan in Phase 1. Multi-segment handoffs
    require the LLM-backed Dispatcher introduced in Phase 2.
    """

    def __init__(self, *, default_speaker: PersonaId = "jarvis") -> None:
        self._default_speaker = default_speaker

    def dispatch(
        self,
        text: str,
        state: DialogState,
        *,
        now_ts: float | None = None,
        handoff_style: HandoffStyle | None = None,
    ) -> Plan:
        """Return a Plan for the given utterance + state.

        `now_ts` overrides `time.time()` for sticky-speaker tests.
        `handoff_style` is ignored in Phase 1 (no multi-segment plans).
        """
        now = now_ts if now_ts is not None else time.time()
        rationale_parts: list[str] = []
        speaker: PersonaId
        tier: Tier = "fast"
        mode: SegmentMode = "chat"
        content: str = text

        slash = _detect_slash(text)
        name_match = _detect_name(text)

        if slash is not None:
            speaker = slash.speaker
            tier = slash.tier
            mode = slash.mode
            # The slash prefix's stripped content becomes the intent; the
            # full original utterance still flows through to the LLM (it
            # sees the slash). Intent is the human-readable summary.
            content = slash.stripped_content if slash.stripped_content else text
            rationale_parts.append(f"slash-prefix dispatch to {speaker}")
        elif name_match is not None:
            speaker, content = name_match
            rationale_parts.append(f"name-at-start dispatch to {speaker}")
        elif _sticky_active(state, now):
            assert state.last_speaker is not None
            speaker = state.last_speaker
            rationale_parts.append(f"sticky to {speaker} within {int(_STICKY_WINDOW_SECONDS)}s")
        else:
            speaker = self._default_speaker
            rationale_parts.append(f"default to {speaker}")

        segment = Segment(
            speaker=speaker,
            tier=tier,
            mode=mode,
            intent=_truncate_intent(content),
            handoff_style=None,
        )
        return Plan(
            segments=[segment],
            rationale="; ".join(rationale_parts),
        )
```

- [ ] **Step 4: Update the dialog package exports**

Edit `server/server/dialog/__init__.py`:

```python
"""Dialog manager + dispatcher + types.

Phase 1 (foundations) ships types.py and a rule-based dispatcher.
Subsequent phases add manager.py (orchestration), feedback.py (logger),
and profile_refresher.py (learning loop).
"""

from server.dialog.dispatcher import RuleBasedDispatcher
from server.dialog.types import (
    DialogState,
    Outcome,
    Plan,
    Segment,
    TurnRef,
)

__all__ = [
    "DialogState",
    "Outcome",
    "Plan",
    "RuleBasedDispatcher",
    "Segment",
    "TurnRef",
]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd server && pytest tests/test_dialog_dispatcher.py -v
```

Expected: all 20 tests pass.

- [ ] **Step 6: Run the full suite + linters**

```bash
cd server && pytest -q && ruff check . && mypy
```

Expected: green pytest, ruff clean, mypy clean.

- [ ] **Step 7: Commit**

```bash
git add server/server/dialog/__init__.py server/server/dialog/dispatcher.py server/tests/test_dialog_dispatcher.py
git commit -m "feat(dialog): add RuleBasedDispatcher (no LLM)

Deterministic single-segment routing for Phase 1: slash prefixes,
name-at-start, sticky speaker (5-min window), defaults to Jarvis.
Falls back from the LLM-backed Dispatcher in Phase 2+ on failure
(spec §5.7). Multi-segment plans require the LLM dispatcher and
ship in Phase 2."
```

---

## Task 8: README updates + Phase 1 sanity smoke

**Files:**
- Modify: `server/README.md`
- Create: `server/tests/test_phase1_smoke.py`

- [ ] **Step 1: Write the Phase 1 smoke test**

Create `server/tests/test_phase1_smoke.py`:

```python
"""Phase 1 smoke — exercises the foundations without wiring into Session.

When this passes, the foundations are ready for Phase 2 to wire into the
DialogManager + Session.
"""

from __future__ import annotations

import importlib

import pytest


def test_phase1_modules_import() -> None:
    # If any of these fail, Phase 1's package layout is broken.
    importlib.import_module("server.dialog")
    importlib.import_module("server.dialog.types")
    importlib.import_module("server.dialog.dispatcher")
    importlib.import_module("server.personas")
    importlib.import_module("server.personas.models")
    importlib.import_module("server.personas.seed")
    importlib.import_module("server.personas.registry")
    importlib.import_module("server.pipelines.openai_llm")


def test_registry_and_dispatch_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Build a registry → dispatch a turn → confirm the plan picks an
    available persona. Doesn't touch the network; doesn't require keys
    (we set fakes)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    monkeypatch.setenv("JARVIS_PERSONAS_ENABLED", "true")
    import server.config as cfg
    importlib.reload(cfg)

    from server.dialog import DialogState, RuleBasedDispatcher
    from server.personas import build_registry_from_settings

    reg = build_registry_from_settings(cfg.settings, codex_workdir=None)
    assert reg.is_available("jarvis")
    assert reg.is_available("pepper")

    dispatcher = RuleBasedDispatcher()
    plan = dispatcher.dispatch("Pepper, run the tests.", DialogState())
    assert plan.segments[0].speaker == "pepper"
    assert reg.get(plan.segments[0].speaker).id == "pepper"


def test_phase1_dormant_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the flag off, no module from the new packages is imported by
    the existing entrypoints. This is the regression guard for Phase 1."""
    monkeypatch.setenv("JARVIS_PERSONAS_ENABLED", "false")
    import server.config as cfg
    importlib.reload(cfg)

    # The settings field exists; that's all Phase 1 promises.
    assert cfg.settings.personas_enabled is False

    # main.py / session.py do NOT import the new packages in Phase 1.
    # We verify by inspecting sys.modules after reloading main.
    import sys
    for mod in [
        "server.dialog.dispatcher",
        "server.dialog.types",
        "server.personas.registry",
        "server.pipelines.openai_llm",
    ]:
        sys.modules.pop(mod, None)

    importlib.import_module("server.main")
    # Nothing from the dormant packages should have been auto-imported.
    assert "server.dialog.dispatcher" not in sys.modules
    assert "server.personas.registry" not in sys.modules
    assert "server.pipelines.openai_llm" not in sys.modules
```

- [ ] **Step 2: Run smoke tests to verify they pass**

```bash
cd server && pytest tests/test_phase1_smoke.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 3: Run the full suite + linters one more time**

```bash
cd server && pytest -q && ruff check . && mypy
```

Expected: green pytest (existing 54 + Phase 1's new tests, ~110+ tests total), ruff clean, mypy clean.

- [ ] **Step 4: Update `server/README.md`**

Append a new section to `server/README.md` after the existing "LLM pipeline" section. Edit `server/README.md` and add:

```markdown
## Multi-model support (Phase 1 — foundations, behind a flag)

Phase 1 of the multi-model build adds Pepper-flavoured plumbing without
changing any user-visible behaviour. The new code is dormant unless
`JARVIS_PERSONAS_ENABLED=true` is set, and even then it's not yet wired
into the Session — that happens in Phase 2.

See the design at `docs/superpowers/specs/2026-05-13-multi-model-support-design.md`.

### New env vars

| Var | Default | Notes |
|---|---|---|
| `JARVIS_PERSONAS_ENABLED` | `false` | Master feature flag. Leave off until Phase 5. |
| `OPENAI_API_KEY` | — | Required for Pepper. Bypasses `JARVIS_` prefix (mirrors `ANTHROPIC_API_KEY`). |
| `OPENAI_BASE_URL` | — | Optional pass-through to the OpenAI client. |
| `JARVIS_TIER_DEFAULT_JARVIS` | `fast` | One of `fast`/`balanced`/`deep`. |
| `JARVIS_TIER_DEFAULT_PEPPER` | `fast` | Same set. |
| `JARVIS_DISPATCHER_MODEL` | `claude-haiku-4-5` | Router LLM (used in Phase 2). |
| `JARVIS_PERSONA_WARMTH` | `subtle` | `subtle` or `off` — toggles the quiet-warmth clause in both prompts. |
| `JARVIS_PERSONA_REFRESH_TURNS` | `20` | Learning-loop cadence (used in Phase 5). |
| `JARVIS_LEARNING` | `on` | Master switch for the learning loop (used in Phase 5). |
| `JARVIS_CODEX_CLI_PATH` | — | Optional path to the `codex` binary (used in Phase 3). |
| `JARVIS_CODEX_APPROVAL` | `auto-low` | `auto-low`/`manual`/`never` (Phase 3). |
| `JARVIS_CODEX_SANDBOX` | `workspace-write` | `read-only`/`workspace-write`/`full-access` (Phase 3). |
| `JARVIS_CODEX_WORKDIR` | — | Overrides `JARVIS_GIT_ROOT` for the Codex agent specifically (Phase 3). |

### Phase 1 quick check

```bash
cd server
pytest -q                    # all green, including the new tests
ruff check . && mypy         # clean

# With the flag on, the registry can be constructed (still no Session wiring):
ANTHROPIC_API_KEY=fake OPENAI_API_KEY=fake JARVIS_PERSONAS_ENABLED=true \
  python -c "from server.personas import build_registry_from_settings; \
             from server.config import settings; \
             r = build_registry_from_settings(settings, codex_workdir=None); \
             print(r.available_ids())"
# Expected: ['jarvis', 'pepper']
```
```

- [ ] **Step 5: Verify README renders sensibly**

```bash
cat server/README.md | head -200
```

Expected: the new section appears after the existing "LLM pipeline" section and reads cleanly.

- [ ] **Step 6: Final lint + commit**

```bash
cd server && pytest -q && ruff check . && mypy
```

Expected: green / clean.

```bash
git add server/README.md server/tests/test_phase1_smoke.py
git commit -m "docs(personas): Phase 1 README section + end-to-end smoke

Smoke tests confirm:
  - all new packages import cleanly
  - registry + dispatcher compose end-to-end without network
  - with the flag off, none of the new packages get auto-imported
    by main.py (regression guard for dormancy)"
```

- [ ] **Step 7: Push the branch**

```bash
git push -u origin claude/multi-model-support-UeDxT
```

Expected: push succeeds; branch is up-to-date with all Phase 1 commits.

---

## Phase 1 acceptance checklist

Before declaring Phase 1 done, verify:

- [ ] `pytest -q` from `server/` is fully green.
- [ ] `ruff check .` from `server/` is clean.
- [ ] `mypy` from `server/` is clean.
- [ ] `JARVIS_PERSONAS_ENABLED=false` (the default) preserves today's behaviour. No existing test was modified.
- [ ] With both API keys set + flag on, the smoke test confirms registry + dispatcher compose.
- [ ] Each Phase 1 commit is a logical unit (no "WIP" commits); `git log --oneline claude/multi-model-support-UeDxT ^main` reads as a clean story.
- [ ] The branch is pushed to `origin`.
- [ ] `docs/superpowers/specs/2026-05-13-multi-model-support-design.md` is unchanged (the spec is the contract; updates require a separate spec-amend commit).

---

## Phase 1 → Phase 2 decision log

**To be filled in as Phase 1 lands.** Each merged task should append a one-line note here so the Phase 2 subagent picks up cold without re-reading the implementation.

Suggested format:

```
- Task N (<file>): <decision worth carrying forward, e.g. "Used pydantic's
  model_copy(update=...) for PersonaRegistry.update_profile so we don't
  need a separate write lock; Phase 5 Refresher reuses this seam.">
```

Initial entries (populated by the implementer as tasks land):

- _(empty — fill in during execution)_

---

## Phases 2 – 5: forward outline

The following phases will each get their own dedicated plan document, written **after** the preceding phase lands so the decision log carries forward intact (spec §11.1). High-level shapes:

### Phase 2 — Dialog manager + chat-only multi-persona (`docs/superpowers/plans/2026-05-13-multi-model-support-phase-2.md`)

**Goal:** Wire Jarvis + Pepper into the Session via a `DialogManager`. With the flag on, both can speak in a turn; hand-offs work via Dispatcher-planned segments; voices swap; no agent mode yet.

**Units:**
1. **LLM-backed Dispatcher** — `dialog/dispatcher.py` gains an `LLMBackedDispatcher` that calls `claude-haiku-4-5` with structured output + the `Plan` schema. Falls back to `RuleBasedDispatcher` on error.
2. **DialogManager** — `dialog/manager.py` orchestrates per-turn flow: dispatcher → agent loop → feedback hooks. Streams segments end-to-end.
3. **TTS voice routing** — refactor `pipelines/edge_tts.py` to accept voice per `synthesize()` call (or maintain a small voice→instance map). Per-segment voice swap on the audio queue.
4. **Session integration** — `session.py` delegates to `DialogManager` when `personas_enabled`. Existing single-Jarvis path preserved when off.
5. **Protocol additions** — `protocol.py` gains optional `speaker`/`segmentIdx` fields, `llm.segment_end`, `dispatch.plan` server messages.

**Acceptance:** Two-persona turn works end-to-end; hand-off turn produces a 2-segment plan with voice swap; existing 54+ tests still pass with flag off.

### Phase 3 — Codex CLI agent path (`docs/superpowers/plans/2026-05-13-multi-model-support-phase-3.md`)

**Goal:** Pepper escalates to the local `codex` CLI for concretely-actionable code work.

**Units:**
1. **`CodexAgent` wrapper** — `pipelines/codex_agent.py` subprocess + JSON-line parser + event translator. Defaults from spec §7.
2. **Agent WS events** — `protocol.py` gains `agent.*` and client→server `agent.approve`/`agent.cancel`.
3. **Approval flow** — UI-side card; voice prompt; auto-approve low-risk classes.
4. **Parallel narration** — Pepper speaks summary sentences while Codex runs (debounced).
5. **Cancel + cleanup** — SIGTERM → 5s → SIGKILL grace; orphan-process audit.

**Acceptance:** Fake-binary integration test exercises the full event loop; real-binary manual checklist passes.

### Phase 4 — UI surface (`docs/superpowers/plans/2026-05-13-multi-model-support-phase-4.md`)

**Goal:** Web HUD reflects both personas + live agent runs.

**Units:**
1. Centerpiece waveform tint per speaker.
2. Topbar dual chip + click-to-pin-next-turn.
3. Dispatch ribbon (above transcript).
4. System panel personas (two rows).
5. Agent panel (replaces East Code zone during runs).

**Acceptance:** Playwright snapshot diffs of cyan→amber transitions; chip interactions tested; agent panel mocked-WS test covers approval cards.

### Phase 5 — Learning loop (`docs/superpowers/plans/2026-05-13-multi-model-support-phase-5.md`)

**Goal:** Profiles adapt over time.

**Units:**
1. SQL schema migration (`dispatch_log`, `personas` tables).
2. `FeedbackLogger` — `dialog/feedback.py`.
3. `ProfileRefresher` — `dialog/profile_refresher.py` + scheduling.
4. `/reset personas` voice command + HUD button.
5. `GET /personas` inspection endpoint.

**Acceptance:** Refresh after N turns mutates profiles; bounded-change rule fires on >40% drift; `/reset` restores seeds; auth-gated endpoint works.

**At the end of Phase 5:** flip `JARVIS_PERSONAS_ENABLED` default to `true` and update the README accordingly.

---

*End of Phase 1 implementation plan.*

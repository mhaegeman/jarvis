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

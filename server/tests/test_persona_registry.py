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


# ─── update_profile re-validates ──────────────────────────────────────


def test_update_profile_rejects_empty_string() -> None:
    """Pydantic v2's model_copy(update=...) skips validation. update_profile
    must not: the Phase 5 Profile Refresher will call this seam, and a
    malformed refresh output (empty or oversized) needs to fail fast rather
    than silently poison the Dispatcher prompt.
    """
    from pydantic import ValidationError

    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=False,
        codex_binary=None,
        codex_workdir=None,
    )
    with pytest.raises(ValidationError):
        reg.update_profile("jarvis", "")


def test_update_profile_rejects_oversized_profile() -> None:
    from pydantic import ValidationError

    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=False,
        codex_binary=None,
        codex_workdir=None,
    )
    # Persona caps specialty_profile at 1800 chars.
    too_long = "x" * 1801
    with pytest.raises(ValidationError):
        reg.update_profile("jarvis", too_long)


def test_update_profile_accepts_valid_profile() -> None:
    reg = PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=False,
        codex_binary=None,
        codex_workdir=None,
    )
    reg.update_profile("jarvis", "new specialty: post-Phase-5 evidence-driven blurb.")
    assert reg.get("jarvis").specialty_profile.startswith("new specialty")


# ─── build_registry_from_settings ─────────────────────────────────────


def test_build_registry_from_settings_with_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.delenv("JARVIS_CODEX_CLI_PATH", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
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

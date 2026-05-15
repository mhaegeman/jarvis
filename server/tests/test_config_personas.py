"""Tests for Phase 1 persona-related Settings fields."""

from __future__ import annotations

import importlib

import pytest


def _fresh_settings(monkeypatch: pytest.MonkeyPatch):
    """Force re-import of server.config so env-var changes take effect."""
    import server.config as cfg
    importlib.reload(cfg)
    return cfg.settings


def test_personas_enabled_defaults_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_PERSONAS_ENABLED", raising=False)
    s = _fresh_settings(monkeypatch)
    assert s.personas_enabled is True


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


def test_persona_refresh_turns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_PERSONA_REFRESH_TURNS", raising=False)
    s = _fresh_settings(monkeypatch)
    assert s.persona_refresh_turns == 20

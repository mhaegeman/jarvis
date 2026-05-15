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

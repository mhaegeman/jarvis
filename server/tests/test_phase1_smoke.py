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
        "server.dialog",
        "server.dialog.dispatcher",
        "server.dialog.types",
        "server.personas",
        "server.personas.models",
        "server.personas.registry",
        "server.personas.seed",
        "server.pipelines.openai_llm",
    ]:
        sys.modules.pop(mod, None)

    importlib.import_module("server.main")
    # Nothing from the dormant packages should have been auto-imported.
    assert "server.dialog.dispatcher" not in sys.modules
    assert "server.personas.registry" not in sys.modules
    assert "server.pipelines.openai_llm" not in sys.modules

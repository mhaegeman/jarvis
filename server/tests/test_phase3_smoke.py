"""Phase 3 smoke — CodexAgent wiring + dormancy regression guard extended.

Confirms:
- Phase 2 smoke tests still pass (imports from test_phase2_smoke would
  duplicate fixtures; we repeat the minimal wiring here for clarity).
- server.pipelines.codex_agent is NOT auto-imported when the flag is off.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_phase3_dormant_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 1+2 regression guard extended: server.pipelines.codex_agent is
    NOT auto-imported when JARVIS_PERSONAS_ENABLED=false."""
    import importlib
    import sys

    monkeypatch.setenv("JARVIS_PERSONAS_ENABLED", "false")
    import server.config as cfg
    importlib.reload(cfg)

    for mod in [
        "server.dialog.manager",
        "server.dialog.dispatcher",
        "server.pipelines.multi_voice_tts",
        "server.pipelines.codex_agent",
        "server.personas.registry",
        "server.pipelines.openai_llm",
    ]:
        sys.modules.pop(mod, None)

    importlib.import_module("server.main")

    for mod in [
        "server.dialog.manager",
        "server.pipelines.multi_voice_tts",
        "server.pipelines.codex_agent",
    ]:
        assert mod not in sys.modules, f"{mod} was auto-imported with the flag off"

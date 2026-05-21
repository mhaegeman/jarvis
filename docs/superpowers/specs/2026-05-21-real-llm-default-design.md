# Real LLM Default Design

**Date:** 2026-05-21
**Status:** Draft

## Problem

`JARVIS_MODEL_NAME` defaults to `"mock"` (`server/server/config.py:16`), so a fresh checkout with `ANTHROPIC_API_KEY` set still routes every turn through the keyword-matched `MockLLM`. The user must remember to set `JARVIS_MODEL_NAME=claude-sonnet-4-6` to get a real assistant. Meanwhile `JARVIS_STT_ENGINE` and `JARVIS_TTS_ENGINE` both already default to `"auto"`, where `_build_stt` / `_build_tts` (`server/server/main.py:121-220`) probe for dependencies and silently fall back to mock with a warning. The LLM should behave the same.

## Chosen Approach

Add `"auto"` as the new default value of `model_name`. Resolve it inside `_build_llm` (not inside `Settings`) so the symmetry with `_build_stt` / `_build_tts` is exact:

| Effective value | Picked when | Behaviour |
|---|---|---|
| `auto` (new default) | `ANTHROPIC_API_KEY` set | `ClaudeLLM(default_model="claude-sonnet-4-6")` |
| `auto` | `ANTHROPIC_API_KEY` unset | `MockLLM()` + `log.warning(...)` |
| `mock` (explicit) | always | `MockLLM()`, no warning |
| `claude-*` (explicit) | key present | `ClaudeLLM(default_model=name)` |
| `claude-*` (explicit) | key absent | `RuntimeError` — unchanged |

`claude-sonnet-4-6` is the auto-resolved target because SETUP.md §2 already labels it the "recommended starting default" (better reasoning than haiku, ~5× cheaper than opus). The dispatcher / persona tiers continue to pick haiku/opus per-turn — this only affects the single-persona fallback path (`personas_enabled=false`) and any explicit `_build_llm()` call.

## Components

### `server/server/config.py`
- Change `model_name: str = "mock"` → `model_name: str = "auto"`. No new field.

### `server/server/main.py` — `_build_llm`
Add the `auto` branch at the top:

```python
name = settings.model_name
if name == "auto":
    if settings.anthropic_api_key is None:
        log.warning(
            "LLM auto: ANTHROPIC_API_KEY unset; using MockLLM. "
            "Set ANTHROPIC_API_KEY to enable claude-sonnet-4-6."
        )
        return MockLLM()
    name = "claude-sonnet-4-6"
# fall through to existing mock / claude-* handling
```

The existing `name == "mock"` and `name.startswith("claude-")` branches are unchanged. Unknown-name `ValueError` still fires for typos.

### Tests
- `server/tests/test_config.py`: add `test_model_name_defaults_to_auto`; keep existing memory/STT/TTS default tests intact.
- `server/tests/test_main_factory.py`: add two cases:
  - `auto` with `ANTHROPIC_API_KEY` set → `ClaudeLLM` with `default_model == "claude-sonnet-4-6"`.
  - `auto` with the key unset → `MockLLM` plus a `caplog` assertion on the warning.
- All `monkeypatch.setattr("server.main.settings.model_name", "mock")` lines already in the suite continue to work; flipping the default doesn't disturb them.

### Docs
- `SETUP.md` §11 (env var table): change `JARVIS_MODEL_NAME` default cell from `mock` to `auto`; add an `auto` row to the value list and reword §2 to note that setting `ANTHROPIC_API_KEY` is now sufficient.
- `TODO.md`: move the "MockLLM" entry under **Shipped** with today's date and PR ref TBD.

## Non-goals

- Not changing STT/TTS defaults (already `auto`).
- Not adding a `"claude-auto"` synonym or model-rotation logic.
- Not touching personas/dispatcher tiers — they keep selecting haiku/sonnet/opus per-turn.
- Not adding a way to override the auto-target model via env (YAGNI — explicit `JARVIS_MODEL_NAME=claude-haiku-4-5` already covers that).

## Risk

The `personas_enabled=true` path (default since Phase 5) routes through the dispatcher and rarely instantiates `_build_llm`'s output for normal turns. So the user-visible blast radius is the single-Jarvis fallback path, the smoke test in SETUP.md §2, and CI / offline demos that don't set the key — all of which keep working because of the warning-and-fallback branch.

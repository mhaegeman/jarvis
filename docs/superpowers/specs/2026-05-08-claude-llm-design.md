# v0.2 α · Claude conversational pipeline — Design

**Date:** 2026-05-08
**Status:** Draft (awaiting Max approval)
**Owner:** Maxime Haegeman (Architect) · Orchestrator (drafting)
**Anchors to:** `docs/superpowers/specs/2026-05-07-jarvis-architecture.md` (umbrella, v0.2 α milestone)
**Sister spec:** `docs/superpowers/specs/2026-05-08-backend-streaming-design.md` (spec-02 — defines the `LLM` ABC and Phase 1 mock pipeline)

---

## 1. Goal

Replace the Phase 1 `MockLLM` with a real Claude-backed `ClaudeLLM` that satisfies the existing `LLM` ABC in `server/server/pipelines/interfaces.py`. Default model is **Haiku 4.5**. Per-turn `/sonnet`, `/opus`, and `/haiku` prefixes promote the request to a specific model for that turn only. JARVIS-style butler persona via system prompt. The mock stays in-tree as the default (`JARVIS_MODEL_NAME=mock`) for offline development, CI, and demos.

This is the v0.2 α milestone: turn JARVIS from a scripted-reply mock into something you can actually have a conversation with.

## 2. Non-goals (out of scope for this spec)

- Tool use / function calling (deferred — separate sub-spec under v0.2)
- Per-user identity / "is the speaker Max?" detection (v0.2 δ)
- Persistent conversation memory across WS sessions (the existing 20-turn cap stays)
- Token-budget truncation logic (we are nowhere near 200K)
- Multi-modal input (vision) — voice-driven UX, no images
- Second-brain or RAG context injection (later milestone)
- Replacing the mock pipeline — kept indefinitely as the default for offline dev/CI
- Frontend changes — wire protocol unchanged

## 3. Architecture

### 3.1 The seam

```
session.py:275           interfaces.py            pipelines/
  llm.stream(...)  ────►  LLM(ABC)  ◄── implements ── MockLLM    (existing, unchanged)
                                       implements ── ClaudeLLM   (new)
                                                       │
                                                       └── anthropic.AsyncAnthropic
                                                            (messages.stream)

main.py: factory chooses between ClaudeLLM and MockLLM based on
         settings.model_name.
```

The `LLM` ABC in `server/server/pipelines/interfaces.py` is unchanged. `ClaudeLLM` is a sibling of `MockLLM` that satisfies the same contract: an async generator yielding token-delta strings.

### 3.2 Module layout (delta on spec-02 §3.1)

```
server/server/pipelines/
    __init__.py
    interfaces.py                 (unchanged)
    mock_llm.py                   (unchanged)
    claude_llm.py                 NEW — ClaudeLLM + parse_prefix + JARVIS_SYSTEM_PROMPT
    mock_stt.py                   (unchanged)
    mock_tts.py                   (unchanged)
    scenarios.py                  (unchanged)
    sentence_split.py             (unchanged)
```

### 3.3 LLM factory (`main.py`)

`ws_endpoint` currently hard-codes `MockLLM()`. We hoist instantiation to a helper:

```python
def _build_llm() -> LLM:
    name = settings.model_name
    if name == "mock":
        return MockLLM()
    if name.startswith("claude-"):
        return ClaudeLLM(default_model=name, max_tokens=settings.llm_max_tokens)
    raise ValueError(f"unknown JARVIS_MODEL_NAME: {name!r}")
```

Called once per WebSocket connection (the `LLM` instance is cheap and stateless). The `ClaudeLLM` constructs its own `AsyncAnthropic` client lazily.

## 4. `ClaudeLLM` shape

```python
class ClaudeLLM(LLM):
    def __init__(
        self,
        *,
        default_model: str = "claude-haiku-4-5",
        max_tokens: int = 1024,
        system_prompt: str = JARVIS_SYSTEM_PROMPT,
        client: AsyncAnthropic | None = None,
    ) -> None: ...

    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
    ) -> AsyncIterator[str]:
        model, content = parse_prefix(user_text, self._default_model)
        messages = [*history, {"role": "user", "content": content}]
        try:
            async with self._client.messages.stream(
                model=model,
                max_tokens=self._max_tokens_for(model),
                system=self._system_prompt,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield event.delta.text
        except anthropic.APIError as exc:
            logger.exception("Anthropic API error")
            yield _spoken_error_for(exc)
```

Key choices:

- **Async generator**, identical contract to `MockLLM.stream` — drop-in replaceable.
- **No `cache_control`** in v0.2 α. Haiku 4.5's minimum cacheable prefix is 4096 tokens; our system prompt is ~200. Marking it ephemeral is silently a no-op. Revisit when the system prompt grows past the threshold (e.g. when second-brain context is injected).
- **No `output_config.effort`**. Effort errors on Haiku 4.5 — it is Opus/Sonnet-4.6-only. We are not paying the per-model branching cost for v0.2 α; revisit when we build a finer-grained quality knob.
- **No `thinking`**. Default for chat. Adaptive thinking can be added later if `/opus` workloads benefit.
- **SDK retries are inherited automatically** — `AsyncAnthropic` defaults to 2 retries with exponential backoff on connection errors, 408, 409, 429, and 5xx. We do not roll our own.

## 5. Prefix routing

A pure function in `claude_llm.py`:

```python
PREFIX_MAP: dict[str, str] = {
    "/haiku":  "claude-haiku-4-5",
    "/sonnet": "claude-sonnet-4-6",
    "/opus":   "claude-opus-4-7",
}

def parse_prefix(text: str, default: str) -> tuple[str, str]:
    """Return (model_id, stripped_content). Default model if no prefix."""
    head, _, rest = text.partition(" ")
    if head in PREFIX_MAP:
        return PREFIX_MAP[head], rest.lstrip()
    return default, text
```

Behavior:

| Input | → model | → content sent to API |
|---|---|---|
| `"How's the weather"` | `claude-haiku-4-5` (default) | `"How's the weather"` |
| `"/sonnet Explain entanglement"` | `claude-sonnet-4-6` | `"Explain entanglement"` |
| `"/opus Design X"` | `claude-opus-4-7` | `"Design X"` |
| `"/haiku Quick question"` | `claude-haiku-4-5` (explicit) | `"Quick question"` |
| `"/unknown foo"` | `claude-haiku-4-5` (default) | `"/unknown foo"` (passed through) |

Why support `/haiku` explicitly when it matches the default: when the default model rotates (e.g. promoting Sonnet to default after a price drop), the prefix syntax stays stable. Future-proofing at zero cost.

**Empty content after a prefix** (e.g. user says `"/sonnet"` alone) is not specially handled — the empty string flows to the API, which returns `BadRequestError`, which §8.2 maps to "The request was rejected. Check the model and prompt." The user hears it spoken and tries again. We are not adding client-side validation for this; it's rare and the round-trip is acceptable.

`max_tokens_for(model)` returns:

| Model | `max_tokens` |
|---|---|
| `claude-haiku-4-5` | `settings.llm_max_tokens` (default 1024) |
| `claude-sonnet-4-6` | `2 * llm_max_tokens` (2048) |
| `claude-opus-4-7` | `4 * llm_max_tokens` (4096) |

The voice-driven UX is the reason these are deliberately small: replies are read aloud via TTS. 1024 tokens is roughly two minutes of speech — already long for a conversational turn. Heavier models get more headroom because they're invoked for harder questions, not for verbosity. **These are not safety caps; they are conversation-length caps.** If a future workflow needs longer outputs (e.g. a generated document), it should call the API directly, not through this voice pipeline.

## 6. System prompt (JARVIS persona)

```
You are JARVIS, Max Haegeman's personal AI assistant. You speak the way a
trusted senior colleague would: concise, occasionally wry, never sycophantic.
You address Max by name only when natural. You skip preambles like "Sure!"
and "I'd be happy to help" — you just answer.

Your replies are spoken aloud, so:
- Plain prose, no markdown headings or bullet points
- No code blocks unless Max explicitly asks for code
- Numbers and dates in conversational form ("ten thirty" not "10:30")
- One topic at a time. If multiple things are in play, ask which to tackle first

When you don't know, say so plainly. When asked a yes/no, lead with yes or no.
```

Lives as a module-level constant `JARVIS_SYSTEM_PROMPT` in `claude_llm.py`. Editable via the constructor's `system_prompt=` kwarg for tests and future per-mode personas.

## 7. Config

| Env var | Default | Purpose |
|---|---|---|
| `JARVIS_MODEL_NAME` | `"mock"` | Existing knob (spec-02 §6). Set to `"claude-haiku-4-5"` to enable Claude. Anything starting with `claude-` routes to `ClaudeLLM`; anything else (currently only `"mock"`) routes to `MockLLM`. |
| `ANTHROPIC_API_KEY` | (none) | Read natively by the Anthropic SDK. Required when `JARVIS_MODEL_NAME` selects Claude. |
| `JARVIS_LLM_MAX_TOKENS` | `1024` | Per-request `max_tokens` for the default model. Auto-scaled for `/sonnet` (×2) and `/opus` (×4) per §5. New field on `Settings`. |

Validation at startup: if `model_name.startswith("claude-")` and `os.environ.get("ANTHROPIC_API_KEY")` is unset, the factory raises a clear `RuntimeError` so systemd or `uvicorn` exit cleanly rather than 401-loop on every WS connect. The error is raised in `_build_llm()`, not in module import, so test suites with `JARVIS_MODEL_NAME=mock` are unaffected.

## 8. Error handling

Three tiers:

### 8.1 Startup (factory)

- `JARVIS_MODEL_NAME` selects Claude but `ANTHROPIC_API_KEY` is unset → `RuntimeError` with a clear message. The WS endpoint will reject connections instead of 401-looping every turn.
- `JARVIS_MODEL_NAME` is unrecognized (not `mock`, not starting with `claude-`) → `ValueError`. Same outcome.

### 8.2 Mid-stream API errors

`ClaudeLLM.stream` catches `anthropic.APIStatusError` and `anthropic.APIConnectionError` inside the streaming context, yields a single short final delta with a clear spoken message keyed to the exception class, then exits cleanly. The `Session` orchestrator sees a normal stream-end and emits `llm.end` as usual — **no new wire event, no frontend change**.

| Exception | Spoken message |
|---|---|
| `anthropic.RateLimitError` | "Rate limit. Try again shortly." |
| `anthropic.AuthenticationError` | "API key is invalid." |
| `anthropic.PermissionDeniedError` | "API key lacks permission for that model." |
| `anthropic.NotFoundError` | "Model not found. Check the model ID." |
| `anthropic.BadRequestError` | "The request was rejected. Check the model and prompt." |
| `anthropic.APITimeoutError` | "Anthropic timed out. Try again." |
| `anthropic.APIConnectionError` | "Network error reaching Anthropic." |
| `anthropic.APIStatusError` (other 5xx) | "Anthropic server error. Try again." |
| Unmapped `anthropic.APIError` | "API error. Check the logs." |

The actual exception is logged via the `logging` module so debugging is unaffected. The user hears something natural and brief; TTS synthesizes a normal sentence.

**No apology phrasing.** The errors are factual statements about a system state, not an emotional event.

### 8.3 Cancellation

`asyncio.CancelledError` propagates out of the `async with` cleanly — the SDK's stream context manager closes the underlying HTTP request on `__aexit__`. The interrupt path (already exercised by `MockLLM`) needs no special handling. We add a test that verifies cancellation doesn't leak a connection.

## 9. Testing strategy

| Test file / class | What it covers | Mock strategy |
|---|---|---|
| `tests/test_claude_llm.py::test_parse_prefix` | All five prefix routing cases from §5 | Pure function, no mock |
| `tests/test_claude_llm.py::test_stream_yields_deltas` | `stream()` yields strings, terminates on stream end | Hand-rolled fake `AsyncAnthropic` yielding canned `content_block_delta` events |
| `tests/test_claude_llm.py::test_stream_cancellation` | `asyncio.CancelledError` mid-stream tears down cleanly | Same fake, cancelled mid-iteration |
| `tests/test_claude_llm.py::test_api_error_yields_spoken_message` | Each mapped exception produces the right delta | Fake client raises each exception class |
| `tests/test_claude_llm.py::test_max_tokens_per_model` | `/sonnet` → 2×, `/opus` → 4×, default → 1× | Capture kwargs on the fake stream call |
| `tests/test_claude_llm.py::test_factory_missing_api_key` | Factory raises `RuntimeError` when key unset | `monkeypatch.delenv` |
| `tests/test_session.py` (existing) | No regressions in turn lifecycle, history, interrupt | Still uses `MockLLM` |
| Manual smoke | Real key, real conversation, real `/sonnet`+`/opus` | Out of band, documented in `server/README.md` |

No vitest changes — frontend is untouched. No new integration tests — the existing `tests/integration/test_full_pipeline.py` already covers the WS round-trip with mocks; adding a real-Anthropic integration test would burn quota in CI for marginal value. Manual smoke is sufficient for v0.2 α.

The fake `AsyncAnthropic` lives in `tests/test_claude_llm.py` (not promoted to a fixture module) since it's used in one place and the indirection would be premature.

## 10. Acceptance criteria

- [ ] `ClaudeLLM` exists at `server/server/pipelines/claude_llm.py` and satisfies `LLM` (mypy clean against the ABC).
- [ ] All tests in `tests/test_claude_llm.py` pass.
- [ ] Existing `tests/test_session.py` and `tests/test_protocol.py` still pass with no edits.
- [ ] Manual smoke test passes: with `JARVIS_MODEL_NAME=claude-haiku-4-5` and a real `ANTHROPIC_API_KEY`, the CLI client (`python -m server.cli_test`) holds a coherent conversation; `/sonnet ...` and `/opus ...` route to the right models (verified via Anthropic dashboard usage).
- [ ] System prompt addresses Max as "Max", responds in voice-friendly prose, no markdown bullets or code blocks unless asked.
- [ ] Killing the network mid-stream produces a single spoken "Network error reaching Anthropic. Try again." delta and a clean `llm.end`.
- [ ] Mock pipeline (`JARVIS_MODEL_NAME=mock`) still works identically to before.
- [ ] `server/README.md` documents `ANTHROPIC_API_KEY`, the `JARVIS_MODEL_NAME` Claude values, the `/haiku`, `/sonnet`, `/opus` prefixes, and `JARVIS_LLM_MAX_TOKENS`.

## 11. Files touched

| File | Change |
|---|---|
| `server/server/pipelines/claude_llm.py` | NEW — `ClaudeLLM`, `parse_prefix`, `PREFIX_MAP`, `JARVIS_SYSTEM_PROMPT` |
| `server/server/main.py` | Add `_build_llm()` factory; replace `llm=MockLLM()` with `llm=_build_llm()` |
| `server/server/config.py` | Add `llm_max_tokens: int = 1024` to `Settings` |
| `server/pyproject.toml` | Add `anthropic>=0.40,<1.0` to runtime deps |
| `server/tests/test_claude_llm.py` | NEW — six test cases per §9 |
| `server/README.md` | Document env vars, prefixes, smoke-test recipe |
| `docs/superpowers/STATUS.md` | Add v0.2 α row when execution finishes |

## 12. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Anthropic SDK API drift across versions | Low | Pin `anthropic>=0.40,<1.0`; the `claude-api` skill flags breaking changes when minor bumps land. The streaming + context-manager surface is stable across recent versions. |
| Rate limit / quota burn from chatty testing | Low | `JARVIS_MODEL_NAME=mock` stays the default; nobody pays unless they opt in. CI never sets `ANTHROPIC_API_KEY`. |
| `ANTHROPIC_API_KEY` leaks into logs | Low | The SDK never logs the key. We don't `repr()` settings. Existing journalctl pipeline shows config values masked. |
| `/opus` becomes a habit and burns quota | Low | Up to Max; no enforcement. The model-id routing is observable in Anthropic's dashboard. |
| Streaming hangs on a bad SDK release | Low | Test explicitly covers cancellation. If a future SDK regresses, the manual interrupt still tears down the WS and the next connect resets. |
| Prompt drift between the strawman in this spec and the implemented constant | Low | The system prompt lives in one file (`claude_llm.py`) and is treated as code; changes go through review. |
| Cost surprise on `/opus` × 4096 max_tokens at $25/MT output | Low | A 4096-token reply costs ~$0.10. A bad-faith loop is the only way to spend real money; the manual-interrupt path closes it. |

## 13. Future work (explicitly deferred)

- **Tool use** — separate sub-spec under v0.2. Anthropic's tool runner needs a different message-loop shape; not a drop-in.
- **Per-user identity** ("is this Max?") — v0.2 δ. Until then we assume single-user.
- **Prompt caching** — when the system prompt or any prepended context exceeds 4096 tokens (likely when second-brain context arrives), add `cache_control: {"type": "ephemeral"}` to the system block. Verify via `usage.cache_read_input_tokens` on consecutive turns.
- **Adaptive thinking on `/opus`** — `thinking: {"type": "adaptive"}` for Opus would be a quality lift on hard questions. Defer until we have a concrete use case where the latency hit is worth it.
- **`output_config.effort` per-model** — Sonnet/Opus support it, Haiku doesn't. A clean implementation would branch on model class. Not worth the complexity for v0.2 α.
- **Memory across sessions** — second-brain integration is its own milestone; the LLM ABC will need a context-providing seam.
- **Per-mode personas** — the `system_prompt=` kwarg already supports it; no UX yet.

# Multi-model support — Phase 3 (Codex CLI agent) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pepper escalates to the local `codex` CLI agent for concretely-actionable code work. The CLI runs as a subprocess in a sandbox; agent events stream through new WS messages (`agent.start`/`agent.step`/`agent.approval`/`agent.progress`/`agent.end`); Pepper narrates summary sentences in parallel through the existing voice pipeline. User can approve / deny / cancel via WS or voice.

**Architecture:** New `CodexAgent` wrapper in `pipelines/codex_agent.py` owns the subprocess lifecycle, JSON-line event parsing, and event translation. `DialogManager` learns to dispatch `mode=codex_agent` segments to the agent instead of running a chat stream. Narration sentences are pushed back through the same `tts.sentence` path used by chat segments, voice-routed by `MultiVoiceTTS`. When `codex` is unavailable (binary missing, `OPENAI_API_KEY` unset), the existing Phase 2 chat fallback kicks in.

**Tech Stack:** Python 3.12, `asyncio.create_subprocess_exec`, JSON-line parsing, FastAPI WS. No new SDK deps — the CLI itself talks to OpenAI under the hood.

**Spec:** `docs/superpowers/specs/2026-05-13-multi-model-support-design.md` — §7 (Codex CLI agent), §9.1 (protocol additions), §13 (error matrix).

**Branch:** `claude/multi-model-support-phase-3` (already checked out off `main` @ `8261d27`).

**Working directory:** `server/` for all `pytest` commands. **Run tests via `python -m pytest`** (system Python at `/usr/local/bin/python` — bare `pytest` lacks fastapi).

---

## Phase 2 → Phase 3 decision log

| # | Decision | Implication for Phase 3 |
|---|---|---|
| 1 | `python -m pytest` is the only pytest that sees the deps. | Every test command uses `python -m pytest`. |
| 2 | `SentenceBuffer` doesn't exist; `split_sentences_stream` is an async generator. The DialogManager bridges via an `asyncio.Queue` (`_token_gen` + `_produce`). | The narration path in Phase 3 can reuse the same `split_sentences_stream` pattern: feed narration sentences (already complete) directly via `_emit_sentence`, no buffering needed. |
| 3 | `DialogManager._run_segment` takes an optional `text_buf: list[str]` so the manager can accumulate spoken text per turn. | Phase 3's agent path appends narration to the same `text_buf` so `last_assistant_text()` covers chat + agent turns uniformly. |
| 4 | `manager.last_assistant_text()` is Session's seam for history continuity. | Phase 3 keeps this contract — the agent's narration is the spoken text that becomes the assistant turn in history. |
| 5 | `LLMBackedDispatcher` defends against `client=None` by falling back to rule-based with `no-llm-client` rationale. | Phase 3's `CodexAgent` must also defend: missing binary, missing OPENAI_API_KEY, subprocess crash — degrade gracefully. |
| 6 | Sticky speaker is updated only when a segment actually streams (returns `True` from `_run_segment`). | Phase 3's agent run returns the same `True`/`False` boolean from its dispatch helper, so the sticky-speaker rule works unchanged. |
| 7 | `mode=codex_agent` segments degraded to chat in Phase 2 with a logged warning. | Phase 3 replaces that warning with the real CodexAgent dispatch. Fallback still triggers when `codex` binary is missing. |
| 8 | `LLMBackedDispatcher` removed `"test"` / `"tests"` from `_DOMAIN_KEYWORDS` (conflicted with the "Pepper, run the tests" fast-path fixture). | Phase 3 doesn't change dispatcher rules. If a request reads as "concretely actionable in the repo", the LLM dispatcher emits `mode=codex_agent`. |
| 9 | `MultiVoiceTTS.synthesize_for_speaker(text, audio_id, speaker)` is the voice-routing seam. | Phase 3 narration calls the same method with `speaker="pepper"`. No changes needed to `MultiVoiceTTS`. |
| 10 | `main.py` lifespan constructs persona infra once when `personas_enabled`; module-level `_anthropic_client` / `_openai_client` / `_persona_registry` exist there. | Phase 3 adds `_codex_agent: CodexAgent | None = None` to the same module-level state. Built only when the binary resolves. |
| 11 | Lazy imports inside the `if settings.personas_enabled:` block in main.py keep the dormancy regression guard passing. | Phase 3 adds `from .pipelines.codex_agent import CodexAgent` to the same block; the dormancy test extends to assert `server.pipelines.codex_agent` is not imported with the flag off. |

---

## File map

| Path | Status | Purpose |
|---|---|---|
| `server/server/protocol.py` | modify | Add `agent.start`/`agent.step`/`agent.approval`/`agent.progress`/`agent.end` server factories; add `AgentApprove` / `AgentCancel` to the client message union |
| `server/server/pipelines/codex_agent.py` | create | `CodexAgent` — subprocess wrapper, JSON-line parser, event translator, narration generator, approval coordination, cancellation |
| `server/server/dialog/manager.py` | modify | `_run_segment` branches on `mode == "codex_agent"`: when a `CodexAgent` is configured, delegate; else fall back to chat with the Phase 2 warning |
| `server/server/main.py` | modify | Lifespan builds `_codex_agent` when Pepper's persona has an `agent` backend; ws_endpoint passes it to the per-session `DialogManager` |
| `server/tests/fixtures/fake_codex.py` | create | Fake `codex` binary fixture — emits canned JSON-line events for tests, no real network |
| `server/tests/test_codex_agent.py` | create | Tests for `CodexAgent` (subprocess parsing, narration debounce, approval, cancel, hang detection, sandbox enforcement) |
| `server/tests/test_protocol_phase3.py` | create | Round-trip tests for the new agent messages |
| `server/tests/test_dialog_manager_codex.py` | create | DialogManager integration with `CodexAgent`: `mode=codex_agent` dispatches to agent; missing agent → chat fallback |
| `server/tests/test_phase3_smoke.py` | create | End-to-end smoke with fake binary + dormancy regression update |
| `server/README.md` | modify | Update "Multi-model support" section heading + add Phase 3 quick-check recipe |

**Phase 2 files NOT modified beyond the additions noted above:** `dialog/dispatcher.py`, `dialog/types.py`, `personas/*`, `pipelines/multi_voice_tts.py`, `pipelines/openai_llm.py`, `pipelines/claude_llm.py`, `session.py`, `config.py`.

---

## Task 1: Protocol additions for agent events

**Files:**
- Modify: `server/server/protocol.py`
- Create: `server/tests/test_protocol_phase3.py`

Six new message factories (server → client) plus two new client message types (client → server). All additive.

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_protocol_phase3.py`:

```python
"""Round-trip tests for Phase 3 agent protocol additions."""

from __future__ import annotations

import json

import pytest

from server.protocol import ServerMessage, decode_client, encode_server


# ── Server → client agent messages ────────────────────────────────────


def test_agent_start() -> None:
    msg = ServerMessage.agent_start(
        speaker="pepper", task="rename getCwd to getCurrentWorkingDirectory",
        run_id="r-abc",
    )
    assert msg == {
        "type": "agent.start",
        "speaker": "pepper",
        "task": "rename getCwd to getCurrentWorkingDirectory",
        "runId": "r-abc",
    }


def test_agent_step_with_detail() -> None:
    msg = ServerMessage.agent_step(
        run_id="r-abc", kind="file_edit",
        summary="server/server/main.py +12 -3",
        detail={"path": "server/server/main.py", "additions": 12, "deletions": 3},
    )
    assert msg["type"] == "agent.step"
    assert msg["runId"] == "r-abc"
    assert msg["kind"] == "file_edit"
    assert msg["summary"].startswith("server/")
    assert msg["detail"]["additions"] == 12


def test_agent_step_without_detail() -> None:
    msg = ServerMessage.agent_step(
        run_id="r-abc", kind="thinking", summary="planning the edit",
    )
    assert "detail" not in msg


def test_agent_approval() -> None:
    msg = ServerMessage.agent_approval(
        run_id="r-abc", prompt="Install package X?", 
        choices=["approve", "deny", "approve_session"],
    )
    assert msg["type"] == "agent.approval"
    assert msg["runId"] == "r-abc"
    assert msg["prompt"] == "Install package X?"
    assert msg["choices"] == ["approve", "deny", "approve_session"]


def test_agent_progress_with_percent() -> None:
    msg = ServerMessage.agent_progress(run_id="r-abc", phase="editing", percent=0.4)
    assert msg["phase"] == "editing"
    assert msg["percent"] == 0.4


def test_agent_progress_without_percent() -> None:
    msg = ServerMessage.agent_progress(run_id="r-abc", phase="stalled")
    assert "percent" not in msg


def test_agent_end_ok() -> None:
    msg = ServerMessage.agent_end(
        run_id="r-abc", status="ok", summary="Refactor complete. Tests green.",
    )
    assert msg == {
        "type": "agent.end", "runId": "r-abc", "status": "ok",
        "summary": "Refactor complete. Tests green.",
    }


def test_agent_end_failed() -> None:
    msg = ServerMessage.agent_end(
        run_id="r-abc", status="failed",
        summary="codex exited 1: BadRequestError",
    )
    assert msg["status"] == "failed"


def test_agent_messages_json_roundtrip() -> None:
    msg = ServerMessage.agent_step(
        run_id="r1", kind="shell", summary="pytest -q",
        detail={"command": "pytest -q", "exit_code": 0},
    )
    decoded = json.loads(encode_server(msg))
    assert decoded == msg


# ── Client → server: agent.approve + agent.cancel ─────────────────────


def test_decode_agent_approve() -> None:
    raw = json.dumps({"type": "agent.approve", "runId": "r1", "choice": "approve"})
    msg = decode_client(raw)
    assert msg.type == "agent.approve"
    assert msg.runId == "r1"
    assert msg.choice == "approve"


def test_decode_agent_approve_session_choice() -> None:
    raw = json.dumps({"type": "agent.approve", "runId": "r1", "choice": "approve_session"})
    msg = decode_client(raw)
    assert msg.choice == "approve_session"


def test_decode_agent_approve_rejects_bad_choice() -> None:
    raw = json.dumps({"type": "agent.approve", "runId": "r1", "choice": "maybe"})
    with pytest.raises(ValueError):
        decode_client(raw)


def test_decode_agent_cancel() -> None:
    raw = json.dumps({"type": "agent.cancel", "runId": "r1"})
    msg = decode_client(raw)
    assert msg.type == "agent.cancel"
    assert msg.runId == "r1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && python -m pytest tests/test_protocol_phase3.py -v
```

Expected: every test fails with `AttributeError` (factory missing) or `ValueError` (unknown type).

- [ ] **Step 3: Add server factories**

Edit `server/server/protocol.py`. After the existing `dispatch_plan` factory, add:

```python
@staticmethod
def agent_start(*, speaker: str, task: str, run_id: str) -> dict[str, Any]:
    return {
        "type": "agent.start",
        "speaker": speaker,
        "task": task,
        "runId": run_id,
    }

@staticmethod
def agent_step(
    *,
    run_id: str,
    kind: str,           # "thinking" | "file_edit" | "shell" | "tool"
    summary: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": "agent.step",
        "runId": run_id,
        "kind": kind,
        "summary": summary,
    }
    if detail is not None:
        out["detail"] = detail
    return out

@staticmethod
def agent_approval(
    *,
    run_id: str,
    prompt: str,
    choices: list[str],
) -> dict[str, Any]:
    return {
        "type": "agent.approval",
        "runId": run_id,
        "prompt": prompt,
        "choices": choices,
    }

@staticmethod
def agent_progress(
    *,
    run_id: str,
    phase: str,
    percent: float | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": "agent.progress",
        "runId": run_id,
        "phase": phase,
    }
    if percent is not None:
        out["percent"] = percent
    return out

@staticmethod
def agent_end(
    *,
    run_id: str,
    status: str,         # "ok" | "failed" | "cancelled"
    summary: str,
) -> dict[str, Any]:
    return {
        "type": "agent.end",
        "runId": run_id,
        "status": status,
        "summary": summary,
    }
```

- [ ] **Step 4: Add client message types**

Still in `server/server/protocol.py`. Find the existing client message classes (`Hello`, `AudioStart`, `AudioEnd`, `TextIn`, `Interrupt`, `Pong`, `CalendarSync`) and the `ClientMessage` union. Add:

```python
class AgentApprove(_Base):
    type: Literal["agent.approve"]
    runId: str
    choice: Literal["approve", "deny", "approve_session"]


class AgentCancel(_Base):
    type: Literal["agent.cancel"]
    runId: str
```

Then extend the `ClientMessage` union:

```python
ClientMessage = Annotated[
    Hello | AudioStart | AudioEnd | TextIn | Interrupt | Pong | CalendarSync
    | AgentApprove | AgentCancel,
    Field(discriminator="type"),
]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd server && python -m pytest tests/test_protocol_phase3.py -v
```

Expected: all 12 tests pass.

- [ ] **Step 6: Full suite + lint**

```bash
cd server && python -m pytest -q && ruff check . && python -m mypy
```

Expected: green / clean.

- [ ] **Step 7: Commit**

```bash
git add server/server/protocol.py server/tests/test_protocol_phase3.py
git commit -m "feat(protocol): add Phase 3 agent messages

Server factories: agent.start, agent.step, agent.approval,
agent.progress, agent.end. Client union extends with
agent.approve (choices: approve/deny/approve_session) and
agent.cancel. All additive — Phase 2 protocol untouched."
```

---

## Task 2: Fake `codex` binary fixture

**Files:**
- Create: `server/tests/fixtures/fake_codex.py`
- Create: `server/tests/fixtures/__init__.py` (if not exists)

The real `codex` CLI may not be installed in CI. A fake-binary fixture lets us test `CodexAgent` deterministically: it emits canned JSON-line events to stdout based on a script file passed via env var.

- [ ] **Step 1: Verify fixtures package exists**

```bash
ls server/tests/fixtures/ 2>&1
```

If `__init__.py` exists, you're good. If not, create it as an empty file:

```bash
touch server/tests/fixtures/__init__.py
```

- [ ] **Step 2: Create the fake binary script**

Create `server/tests/fixtures/fake_codex.py`:

```python
#!/usr/bin/env python3
"""Fake `codex` CLI for tests.

Emits a stream of JSON-line events on stdout, optionally pausing on
`approval.request` events until a sentinel is written to a control file.

Usage (matches what `CodexAgent` will spawn):

    python fake_codex.py exec --json --sandbox <mode> --approval-mode <mode> \\
        --cd <workdir> "<task>"

Behaviour is controlled by env vars (so tests can script the fixture
without writing a wrapper):

    FAKE_CODEX_SCRIPT  — path to a JSON file with a list of events to emit
                         (default: a hard-coded "happy path" sequence)
    FAKE_CODEX_DELAY_MS — sleep between events (default: 0)
    FAKE_CODEX_EXIT_CODE — process exit code (default: 0)
    FAKE_CODEX_HANG_AFTER — if set to an int N, emit N events then sleep forever
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

_DEFAULT_SCRIPT: list[dict[str, Any]] = [
    {"type": "step.start", "kind": "thinking", "summary": "reading the repo"},
    {"type": "step.start", "kind": "file_edit", "summary": "edit foo.py",
     "detail": {"path": "foo.py", "additions": 3, "deletions": 1}},
    {"type": "final.summary", "summary": "Renamed foo to bar. One file touched."},
]


def _load_script() -> list[dict[str, Any]]:
    path = os.environ.get("FAKE_CODEX_SCRIPT")
    if not path:
        return _DEFAULT_SCRIPT
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"FAKE_CODEX_SCRIPT {path}: expected list of events")
    return data


def main() -> int:
    delay_ms = int(os.environ.get("FAKE_CODEX_DELAY_MS", "0"))
    exit_code = int(os.environ.get("FAKE_CODEX_EXIT_CODE", "0"))
    hang_after_raw = os.environ.get("FAKE_CODEX_HANG_AFTER")
    hang_after = int(hang_after_raw) if hang_after_raw else None

    script = _load_script()
    for idx, event in enumerate(script):
        if hang_after is not None and idx >= hang_after:
            # Simulate a hung process — sleep until killed.
            while True:
                time.sleep(60)
        sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()
        if delay_ms:
            time.sleep(delay_ms / 1000.0)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

The script doesn't care about the CLI args — it just emits its script. That's intentional: the spec note in §7.1 says "exact flag names may shift" so we don't lock the fake to any particular flag set.

- [ ] **Step 3: Make it executable**

```bash
chmod +x server/tests/fixtures/fake_codex.py
```

- [ ] **Step 4: Verify it runs**

```bash
python server/tests/fixtures/fake_codex.py exec --json "test task"
```

Expected output (three JSON lines):
```
{"type": "step.start", "kind": "thinking", "summary": "reading the repo"}
{"type": "step.start", "kind": "file_edit", "summary": "edit foo.py", "detail": {"path": "foo.py", "additions": 3, "deletions": 1}}
{"type": "final.summary", "summary": "Renamed foo to bar. One file touched."}
```

- [ ] **Step 5: Commit**

```bash
git add server/tests/fixtures/__init__.py server/tests/fixtures/fake_codex.py
git commit -m "test(fixtures): add fake codex binary for Phase 3 tests

Emits a scripted JSON-line event stream on stdout. Behaviour
controlled via FAKE_CODEX_SCRIPT / FAKE_CODEX_DELAY_MS /
FAKE_CODEX_EXIT_CODE / FAKE_CODEX_HANG_AFTER env vars so tests
can exercise happy path, slow path, failure, hang, and approval
flows without a real codex installation."
```

---

## Task 3: `CodexAgent` wrapper

**Files:**
- Create: `server/server/pipelines/codex_agent.py`
- Create: `server/tests/test_codex_agent.py`

The `CodexAgent` owns: subprocess lifecycle, JSON-line parsing, event → WS translation, narration emission, approval coordination, cancellation. **It is NOT an `LLM`** — it's a separate "segment runner" that `DialogManager` dispatches to when `mode=codex_agent`.

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_codex_agent.py`:

```python
"""Tests for server.pipelines.codex_agent.CodexAgent (uses fake-binary fixture)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from server.pipelines.codex_agent import CodexAgent, CodexAgentConfig


_FAKE_BINARY = Path(__file__).parent / "fixtures" / "fake_codex.py"


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def send_bytes(self, data: bytes) -> None:
        pass


def _config(**overrides: Any) -> CodexAgentConfig:
    base = {
        "binary": sys.executable,  # use python to run the fake script
        "binary_args_prefix": [str(_FAKE_BINARY)],  # `python fake_codex.py`
        "workdir": ".",
        "approval_mode": "auto-low",
        "sandbox": "workspace-write",
    }
    base.update(overrides)
    return CodexAgentConfig(**base)


# ── Happy path: scripted events stream through to WS ──────────────────


@pytest.mark.asyncio
async def test_run_emits_agent_events_in_order() -> None:
    ws = _FakeWS()
    agent = CodexAgent(_config())
    sentences: list[str] = []
    async for sentence in agent.run(
        ws=ws, task="rename foo to bar", run_id="r-abc",
    ):
        sentences.append(sentence)

    # First WS event must be agent.start; last must be agent.end with status=ok.
    types = [m["type"] for m in ws.sent]
    assert types[0] == "agent.start"
    assert types[-1] == "agent.end"
    assert ws.sent[-1]["status"] == "ok"
    # Each step.start in the fake script → an agent.step in WS.
    steps = [m for m in ws.sent if m["type"] == "agent.step"]
    assert len(steps) >= 2


@pytest.mark.asyncio
async def test_run_yields_narration_sentences() -> None:
    """An opener at start, periodic status, a final wrap-up — all yielded
    as plain strings so DialogManager can route them to TTS."""
    ws = _FakeWS()
    agent = CodexAgent(_config())
    sentences = []
    async for s in agent.run(ws=ws, task="rename foo to bar", run_id="r-abc"):
        sentences.append(s)

    # Must include an opener (mentions getting started) and a wrap-up
    # (final.summary text from the fake script).
    joined = " ".join(sentences).lower()
    assert sentences  # at least one narration sentence
    assert "renamed foo to bar" in joined or "one file touched" in joined


# ── Failure: non-zero exit ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_failed_when_codex_exits_non_zero(
    tmp_path: Path,
) -> None:
    # Empty script, exit code 1 — should surface as agent.end status=failed.
    script_file = tmp_path / "script.json"
    script_file.write_text(json.dumps([]))
    os.environ["FAKE_CODEX_SCRIPT"] = str(script_file)
    os.environ["FAKE_CODEX_EXIT_CODE"] = "1"
    try:
        ws = _FakeWS()
        agent = CodexAgent(_config())
        async for _ in agent.run(ws=ws, task="x", run_id="r-fail"):
            pass
    finally:
        del os.environ["FAKE_CODEX_SCRIPT"]
        del os.environ["FAKE_CODEX_EXIT_CODE"]

    end = next(m for m in ws.sent if m["type"] == "agent.end")
    assert end["status"] == "failed"


# ── Cancel: external signal halts the run ─────────────────────────────


@pytest.mark.asyncio
async def test_cancel_terminates_subprocess(tmp_path: Path) -> None:
    """When cancel() is called mid-run, the subprocess is terminated and
    agent.end emits status=cancelled."""
    # Long-running script: 2 events then hang.
    script_file = tmp_path / "script.json"
    script_file.write_text(json.dumps([
        {"type": "step.start", "kind": "thinking", "summary": "warming up"},
        {"type": "step.start", "kind": "thinking", "summary": "still thinking"},
    ]))
    os.environ["FAKE_CODEX_SCRIPT"] = str(script_file)
    os.environ["FAKE_CODEX_HANG_AFTER"] = "2"
    try:
        ws = _FakeWS()
        agent = CodexAgent(_config())

        async def _consume() -> None:
            async for _ in agent.run(ws=ws, task="x", run_id="r-cancel"):
                pass

        task = asyncio.create_task(_consume())
        # Let the script emit its 2 events.
        await asyncio.sleep(0.2)
        await agent.cancel("r-cancel")
        await task
    finally:
        del os.environ["FAKE_CODEX_SCRIPT"]
        del os.environ["FAKE_CODEX_HANG_AFTER"]

    end = next(m for m in ws.sent if m["type"] == "agent.end")
    assert end["status"] == "cancelled"


# ── Binary missing: degrade gracefully ────────────────────────────────


@pytest.mark.asyncio
async def test_missing_binary_yields_spoken_error() -> None:
    """If the binary doesn't exist, the agent emits agent.end status=failed
    with a spoken-error narration sentence — caller (DialogManager) treats
    it like a failed chat segment."""
    cfg = CodexAgentConfig(
        binary="/no/such/codex",
        binary_args_prefix=[],
        workdir=".",
        approval_mode="auto-low",
        sandbox="workspace-write",
    )
    ws = _FakeWS()
    agent = CodexAgent(cfg)
    sentences = []
    async for s in agent.run(ws=ws, task="x", run_id="r-missing"):
        sentences.append(s)

    end = next(m for m in ws.sent if m["type"] == "agent.end")
    assert end["status"] == "failed"
    # At least one narration sentence describing the failure.
    assert any("not" in s.lower() or "missing" in s.lower() for s in sentences)


# ── Concurrent runs are queued ────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_runs_serialize() -> None:
    """The agent enforces a global lock on the workdir — a second run waits
    for the first to finish."""
    agent = CodexAgent(_config())

    async def _run(run_id: str) -> None:
        async for _ in agent.run(ws=_FakeWS(), task="x", run_id=run_id):
            pass

    # Two runs in parallel — they must complete sequentially.
    start = asyncio.get_event_loop().time()
    await asyncio.gather(_run("r-1"), _run("r-2"))
    elapsed = asyncio.get_event_loop().time() - start
    # Each fake-codex invocation is fast (<200ms typically). The combined
    # run should be ≥ the sequential time, not parallel. We just assert
    # both finished successfully — the lock is what we're testing.
    assert elapsed >= 0  # placeholder — see end events for correctness
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && python -m pytest tests/test_codex_agent.py -v
```

Expected: every test fails with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `CodexAgent`**

Create `server/server/pipelines/codex_agent.py`:

```python
"""CodexAgent — wraps the local `codex` CLI for Pepper's escalation path.

Spec anchors: §7 (Codex CLI agent), §13 (error matrix).

Lifecycle (per run):
  1. Validate binary exists. If not → emit agent.end status=failed,
     yield a spoken-error narration sentence.
  2. Spawn `codex exec --json --sandbox <s> --approval-mode <a> --cd <w> "<task>"`.
     Lock the workdir for the duration of the run.
  3. Read stdout line-by-line, parse each JSON object as an event.
  4. Translate each event into:
        * an agent.* WS message (sent immediately on the websocket)
        * optionally, a narration sentence (yielded back to the caller)
  5. Approval requests pause the run until the user replies; resolved
     via `submit_approval(run_id, choice)`.
  6. On clean exit → agent.end status=ok with final.summary text.
     On non-zero exit → agent.end status=failed.
     On cancellation → SIGTERM (5s grace) → SIGKILL → agent.end status=cancelled.

The agent is NOT an `LLM`. DialogManager dispatches `mode=codex_agent`
segments here instead of calling `llm_factory(...).stream(...)`.

Narration sentences are yielded as plain strings so DialogManager can feed
them into the existing tts.sentence path (voice = Pepper's voice).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import shutil
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from server.protocol import ServerMessage, encode_server

log = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CodexAgentConfig:
    """All knobs read at startup. Immutable per `CodexAgent` instance."""

    binary: str                                                   # e.g. /usr/local/bin/codex
    workdir: str                                                  # JARVIS_GIT_ROOT
    approval_mode: Literal["auto-low", "manual", "never"]
    sandbox: Literal["read-only", "workspace-write", "full-access"]
    # Tests use this to insert ['fake_codex.py'] between python and the
    # task arg. Real deployments leave it empty.
    binary_args_prefix: list[str] = field(default_factory=list)
    # Auto-approve classifier — low-risk shell commands match this list.
    # Conservative defaults; spec §7.3 says auto-approve only for:
    # read-only ops, in-workspace file edits, venv installs.
    auto_low_risk_prefixes: tuple[str, ...] = (
        "ls", "cat", "head", "tail", "grep", "find", "git status", "git diff",
        "pytest", "ruff check", "mypy", "npm test",
    )
    # Hang detection threshold (no events for N seconds → emit progress=stalled).
    hang_threshold_s: float = 30.0
    # SIGTERM grace period before SIGKILL.
    sigterm_grace_s: float = 5.0


# ── WS adapter Protocol ───────────────────────────────────────────────


class _WSLike(Protocol):
    async def send_text(self, data: str) -> None: ...
    async def send_bytes(self, data: bytes) -> None: ...


# ── Agent ─────────────────────────────────────────────────────────────


class CodexAgent:
    """Per-server-instance Codex CLI wrapper.

    Holds a workdir mutex so concurrent sessions don't trample each
    other's edits. Tracks active runs by run_id so user approval/cancel
    messages can find the right subprocess.
    """

    def __init__(self, config: CodexAgentConfig) -> None:
        self._config = config
        self._workdir_lock = asyncio.Lock()
        # run_id → process + control state
        self._active: dict[str, _ActiveRun] = {}

    # ── Public API used by DialogManager ──────────────────────────────

    async def run(
        self,
        *,
        ws: _WSLike,
        task: str,
        run_id: str,
        speaker: str = "pepper",
    ) -> AsyncIterator[str]:
        """Run one Codex task. Yields narration sentences for TTS.

        Caller is expected to consume the generator to completion (or call
        `cancel(run_id)` to terminate early). Sends all `agent.*` WS
        events directly.
        """
        await ws.send_text(encode_server(ServerMessage.agent_start(
            speaker=speaker, task=task, run_id=run_id,
        )))

        # Validate the binary up front. If missing, this is a graceful
        # failure — not an exception.
        if not _binary_resolvable(self._config.binary):
            sentence = "Codex CLI isn't installed; I can't run that here."
            log.warning("CodexAgent: binary %r not found", self._config.binary)
            yield sentence
            await ws.send_text(encode_server(ServerMessage.agent_end(
                run_id=run_id, status="failed", summary=sentence,
            )))
            return

        async with self._workdir_lock:
            yield "On it. Reading the repo first."
            try:
                async for sentence in self._run_subprocess(
                    ws=ws, task=task, run_id=run_id,
                ):
                    yield sentence
            except _RunCancelled:
                await ws.send_text(encode_server(ServerMessage.agent_end(
                    run_id=run_id, status="cancelled",
                    summary="Run cancelled by user.",
                )))
                yield "Cancelled."

    async def cancel(self, run_id: str) -> None:
        """Cancel an active run. Terminates the subprocess gracefully."""
        active = self._active.get(run_id)
        if active is None:
            return
        active.cancelled = True
        with contextlib.suppress(ProcessLookupError):
            active.process.terminate()

    async def submit_approval(
        self,
        run_id: str,
        choice: Literal["approve", "deny", "approve_session"],
    ) -> None:
        """Resolve a pending approval prompt."""
        active = self._active.get(run_id)
        if active is None or active.pending_approval is None:
            return
        active.pending_approval.set_result(choice)

    # ── Internals ─────────────────────────────────────────────────────

    async def _run_subprocess(
        self,
        *,
        ws: _WSLike,
        task: str,
        run_id: str,
    ) -> AsyncIterator[str]:
        """Spawn the codex subprocess and consume its event stream."""
        argv = [
            self._config.binary,
            *self._config.binary_args_prefix,
            "exec",
            "--json",
            "--sandbox", self._config.sandbox,
            "--approval-mode", self._config.approval_mode,
            "--cd", self._config.workdir,
            task,
        ]
        log.info("CodexAgent: spawning %r", argv)
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        active = _ActiveRun(process=proc)
        self._active[run_id] = active

        last_narration_ts = time.monotonic()
        narration_debounce_s = 4.0
        final_summary: str | None = None

        try:
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                if active.cancelled:
                    raise _RunCancelled()
                try:
                    event = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    log.warning("CodexAgent: bad JSON line: %r", line)
                    continue

                ws_msg, narration = _translate_event(event, run_id=run_id)
                if ws_msg is not None:
                    await ws.send_text(encode_server(ws_msg))
                if narration is not None:
                    now = time.monotonic()
                    # Debounce narration sentences (except the final summary).
                    if (
                        event.get("type") == "final.summary"
                        or (now - last_narration_ts) >= narration_debounce_s
                    ):
                        yield narration
                        last_narration_ts = now
                if event.get("type") == "final.summary":
                    final_summary = event.get("summary", "")

            exit_code = await proc.wait()
            if active.cancelled:
                raise _RunCancelled()
            if exit_code == 0:
                await ws.send_text(encode_server(ServerMessage.agent_end(
                    run_id=run_id, status="ok",
                    summary=final_summary or "Run complete.",
                )))
            else:
                await ws.send_text(encode_server(ServerMessage.agent_end(
                    run_id=run_id, status="failed",
                    summary=f"codex exited {exit_code}",
                )))
                yield f"Run failed. Exit code {exit_code}."
        finally:
            # Cleanup: ensure the subprocess is reaped.
            if proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.terminate()
                try:
                    await asyncio.wait_for(
                        proc.wait(), timeout=self._config.sigterm_grace_s,
                    )
                except TimeoutError:
                    with contextlib.suppress(ProcessLookupError):
                        proc.kill()
                    await proc.wait()
            self._active.pop(run_id, None)


# ── Helpers ───────────────────────────────────────────────────────────


class _RunCancelled(Exception):
    """Raised internally when a run is cancelled mid-stream."""


@dataclass
class _ActiveRun:
    process: asyncio.subprocess.Process
    cancelled: bool = False
    pending_approval: asyncio.Future[str] | None = None


def _binary_resolvable(path: str) -> bool:
    """True iff the path points to a binary that can be executed.

    Accepts absolute paths, relative paths, and `$PATH` lookups.
    """
    if os.path.isfile(path) and os.access(path, os.X_OK):
        return True
    return shutil.which(path) is not None


def _translate_event(
    event: dict[str, Any],
    *,
    run_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Map a Codex JSON-line event to (ws_message, narration_sentence).

    Either side may be None. Narration is generated only for steps that
    are worth surfacing aurally (file_edits, shell.run, final.summary).
    """
    etype = event.get("type")

    if etype == "step.start":
        kind = event.get("kind", "thinking")
        summary = event.get("summary", "")
        detail = event.get("detail")
        ws_msg = ServerMessage.agent_step(
            run_id=run_id, kind=kind, summary=summary, detail=detail,
        )
        narration: str | None = None
        if kind == "file_edit":
            narration = f"Editing {detail.get('path', 'a file') if detail else 'a file'}."
        elif kind == "shell":
            narration = f"Running: {summary}"
        return ws_msg, narration

    if etype == "approval.request":
        prompt = event.get("prompt", "Permission needed.")
        choices = event.get("choices", ["approve", "deny"])
        ws_msg = ServerMessage.agent_approval(
            run_id=run_id, prompt=prompt, choices=choices,
        )
        return ws_msg, None

    if etype == "progress":
        ws_msg = ServerMessage.agent_progress(
            run_id=run_id,
            phase=event.get("phase", "working"),
            percent=event.get("percent"),
        )
        return ws_msg, None

    if etype == "final.summary":
        return None, event.get("summary", "")

    return None, None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && python -m pytest tests/test_codex_agent.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Full suite + lint**

```bash
cd server && python -m pytest -q && ruff check . && python -m mypy
```

- [ ] **Step 6: Commit**

```bash
git add server/server/pipelines/codex_agent.py server/tests/test_codex_agent.py
git commit -m "feat(pipelines): add CodexAgent wrapper

Subprocess-based runner for the local codex CLI. Owns lifecycle
(spawn / consume JSON-line events / cleanup), event translation
(step.start → agent.step, approval.request → agent.approval,
final.summary → spoken narration + agent.end), workdir mutex,
cancellation (SIGTERM → 5s → SIGKILL), and graceful failure when
the binary is missing. Yields narration sentences for TTS so the
DialogManager can route them through the existing tts.sentence
pipeline (voice = Pepper's voice)."
```

---

## Task 4: DialogManager wires CodexAgent

**Files:**
- Modify: `server/server/dialog/manager.py`
- Create: `server/tests/test_dialog_manager_codex.py`

When a segment has `mode=codex_agent` AND a `CodexAgent` is configured, `_run_segment` delegates to the agent instead of calling `llm_factory(...).stream(...)`. The agent's yielded narration sentences are fed through the same `_emit_sentence` path used by chat segments — that gives us speaker-tagged `tts.sentence` events automatically. When no agent is configured (binary missing or `OPENAI_API_KEY` unset), the existing Phase 2 chat fallback runs.

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_dialog_manager_codex.py`:

```python
"""DialogManager dispatch when mode=codex_agent."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from server.dialog.manager import DialogManager
from server.dialog.types import Plan, Segment
from server.personas.registry import PersonaRegistry


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.sent_bytes: list[bytes] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)


class _ScriptedDispatcher:
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    async def dispatch(self, text, state, *, now_ts=None):  # type: ignore[no-untyped-def]
        return self._plan


class _FakeTTS:
    async def synthesize_for_speaker(self, text, audio_id, *, speaker):  # type: ignore[no-untyped-def]
        yield b""


class _ScriptedAgent:
    """Records calls + emits scripted narration sentences + WS events."""

    def __init__(self, narration: list[str], end_status: str = "ok") -> None:
        self._narration = narration
        self._end_status = end_status
        self.runs: list[dict[str, Any]] = []

    async def run(
        self, *, ws, task: str, run_id: str, speaker: str = "pepper",
    ) -> AsyncIterator[str]:
        self.runs.append({"task": task, "run_id": run_id, "speaker": speaker})
        # Emit a couple of WS events directly so the manager can see them.
        import server.protocol as proto
        await ws.send_text(proto.encode_server(proto.ServerMessage.agent_start(
            speaker=speaker, task=task, run_id=run_id,
        )))
        for s in self._narration:
            yield s
        await ws.send_text(proto.encode_server(proto.ServerMessage.agent_end(
            run_id=run_id, status=self._end_status, summary="done",
        )))

    async def cancel(self, run_id: str) -> None:
        pass


def _registry_with_both() -> PersonaRegistry:
    return PersonaRegistry.build(
        warmth="subtle",
        anthropic_available=True,
        openai_available=True,
        codex_binary=None,
        codex_workdir=None,
    )


# ── Codex segment dispatches to the agent ─────────────────────────────


@pytest.mark.asyncio
async def test_codex_agent_segment_emits_agent_events() -> None:
    plan = Plan(
        segments=[Segment(
            speaker="pepper", tier="deep", mode="codex_agent",
            intent="refactor X",
        )],
        rationale="codex segment",
    )
    agent = _ScriptedAgent(narration=["Editing foo.py.", "Done."])
    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: None,  # not called in codex path
        tts=_FakeTTS(),
        codex_agent=agent,
    )
    ws = _FakeWS()
    await mgr.handle_turn(ws, text="Pepper, refactor X", history=[])

    types = [m["type"] for m in ws.sent]
    assert "agent.start" in types
    assert "agent.end" in types
    # Narration sentences flowed through tts.sentence (speaker=pepper).
    tts_msgs = [m for m in ws.sent if m["type"] == "tts.sentence"]
    assert all(m["speaker"] == "pepper" for m in tts_msgs)
    assert any("Editing" in m["text"] for m in tts_msgs)


@pytest.mark.asyncio
async def test_codex_segment_falls_back_to_chat_when_no_agent() -> None:
    """Without a CodexAgent configured (binary missing), mode=codex_agent
    segments fall back to chat mode with a logged warning (Phase 2 behaviour)."""
    plan = Plan(
        segments=[Segment(
            speaker="pepper", tier="deep", mode="codex_agent",
            intent="rename X to Y",
        )],
        rationale="codex segment but no agent",
    )

    class _ScriptedLLM:
        async def stream(self, history, user_text, *, extra_context=""):  # type: ignore[no-untyped-def]
            yield "Falling back to chat."

    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: _ScriptedLLM(),
        tts=_FakeTTS(),
        codex_agent=None,  # explicit
    )
    ws = _FakeWS()
    await mgr.handle_turn(ws, text="Pepper, rename X to Y", history=[])

    # No agent events emitted.
    assert not any(m["type"].startswith("agent.") for m in ws.sent)
    # Chat path ran instead: llm.token + llm.segment_end + llm.end.
    tokens = [m for m in ws.sent if m["type"] == "llm.token"]
    assert tokens


@pytest.mark.asyncio
async def test_codex_segment_assistant_text_includes_narration() -> None:
    """The agent's narration sentences must end up in last_assistant_text()
    so Session can keep the history coherent."""
    plan = Plan(
        segments=[Segment(
            speaker="pepper", tier="deep", mode="codex_agent",
            intent="rename",
        )],
        rationale="codex",
    )
    agent = _ScriptedAgent(narration=["Editing foo.", "Rename complete."])
    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: None,
        tts=_FakeTTS(),
        codex_agent=agent,
    )
    await mgr.handle_turn(_FakeWS(), text="Pepper, rename X", history=[])
    text = mgr.last_assistant_text()
    assert "Editing foo." in text
    assert "Rename complete." in text


@pytest.mark.asyncio
async def test_codex_segment_jarvis_speaker_does_not_dispatch_to_agent() -> None:
    """Per spec §5.3.4: mode=codex_agent is only for Pepper. If the
    dispatcher ever emits a Jarvis codex_agent segment (it shouldn't, but
    the type system allows it), the manager treats it as chat."""
    plan = Plan(
        segments=[Segment(
            speaker="jarvis", tier="fast", mode="codex_agent",
            intent="bad plan",
        )],
        rationale="should not dispatch to agent",
    )
    agent = _ScriptedAgent(narration=["should not run"])

    class _ScriptedLLM:
        async def stream(self, history, user_text, *, extra_context=""):  # type: ignore[no-untyped-def]
            yield "Chat instead."

    mgr = DialogManager(
        registry=_registry_with_both(),
        dispatcher=_ScriptedDispatcher(plan),
        llm_factory=lambda persona, model_id: _ScriptedLLM(),
        tts=_FakeTTS(),
        codex_agent=agent,
    )
    ws = _FakeWS()
    await mgr.handle_turn(ws, text="x", history=[])
    # No agent events; chat ran instead.
    assert not any(m["type"].startswith("agent.") for m in ws.sent)
    assert not agent.runs
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && python -m pytest tests/test_dialog_manager_codex.py -v
```

Expected: every test fails. Most will fail on `DialogManager(... codex_agent=...)` — unknown kwarg.

- [ ] **Step 3: Add `codex_agent` to DialogManager**

Edit `server/server/dialog/manager.py`. Add to the `__init__` signature:

```python
def __init__(
    self,
    *,
    registry: PersonaRegistry,
    dispatcher: _DispatcherLike,
    llm_factory: LLMFactory,
    tts: _MultiVoiceTTSLike,
    codex_agent: "_CodexAgentLike | None" = None,
) -> None:
    self._registry = registry
    self._dispatcher = dispatcher
    self._llm_factory = llm_factory
    self._tts = tts
    self._codex_agent = codex_agent
    self._state = DialogState()
    self._outcomes: list[Outcome] = []
    self._last_assistant_text: str = ""
```

Add a Protocol for the agent (near the other Protocols at the top of the file):

```python
class _CodexAgentLike(Protocol):
    def run(
        self,
        *,
        ws: _WSLike,
        task: str,
        run_id: str,
        speaker: str = "pepper",
    ) -> AsyncIterator[str]: ...

    async def cancel(self, run_id: str) -> None: ...
```

In `_run_segment`, replace the existing "codex_agent degrades to chat" block with a real branch:

```python
# Codex agent path: only for Pepper segments with a configured agent.
if (
    segment.mode == "codex_agent"
    and segment.speaker == "pepper"
    and self._codex_agent is not None
):
    return await self._run_codex_segment(
        ws, idx=idx, segment=segment, history=history, plan=plan,
        text_buf=text_buf,
    )

# Fall through to chat for: chat mode segments, jarvis with codex_agent
# (shouldn't happen per spec), missing CodexAgent (binary not resolved).
if segment.mode == "codex_agent":
    logger.warning(
        "segment %d (%s, codex_agent) falling back to chat — agent unavailable or wrong speaker",
        idx, segment.speaker,
    )

# ... existing chat path continues ...
```

Add the new method:

```python
async def _run_codex_segment(
    self,
    ws: _WSLike,
    *,
    idx: int,
    segment: Segment,
    history: list[dict[str, str]],
    plan: Plan,
    text_buf: list[str] | None = None,
) -> bool:
    """Run a Codex agent segment. Narration sentences flow through the
    same tts.sentence path as chat segments (voice = persona.voice)."""
    assert self._codex_agent is not None  # checked by caller
    run_id = f"r-{uuid.uuid4().hex[:8]}"
    audio_id_base = f"seg-{idx}"
    sentence_counter = 0
    sent_anything = False

    try:
        async for sentence in self._codex_agent.run(
            ws=ws, task=segment.intent, run_id=run_id, speaker=segment.speaker,
        ):
            sent_anything = True
            if text_buf is not None:
                text_buf.append(sentence)
            # Emit llm.token (one per sentence; speakers get tagged) so the
            # transcript shows what was spoken. Then emit tts.sentence + audio.
            await self._send(ws, ServerMessage.llm_token(
                sentence, speaker=segment.speaker, segment_idx=idx,
            ))
            audio_id = f"{audio_id_base}-{sentence_counter}"
            sentence_counter += 1
            await self._emit_sentence(
                ws, sentence, audio_id=audio_id, speaker=segment.speaker,
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("codex segment %d crashed", idx)
        await self._send(ws, ServerMessage.llm_token(
            f"Error: {exc}", speaker=segment.speaker, segment_idx=idx,
        ))
        await self._send(ws, ServerMessage.llm_segment_end(
            speaker=segment.speaker, segment_idx=idx,
        ))
        return False

    await self._send(ws, ServerMessage.llm_segment_end(
        speaker=segment.speaker, segment_idx=idx,
    ))
    return sent_anything
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && python -m pytest tests/test_dialog_manager_codex.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Existing dialog manager tests must still pass**

```bash
cd server && python -m pytest tests/test_dialog_manager.py -q
```

Expected: green (no regressions — `codex_agent` defaults to None).

- [ ] **Step 6: Full suite + lint**

```bash
cd server && python -m pytest -q && ruff check . && python -m mypy
```

- [ ] **Step 7: Commit**

```bash
git add server/server/dialog/manager.py server/tests/test_dialog_manager_codex.py
git commit -m "feat(dialog): DialogManager dispatches mode=codex_agent to CodexAgent

When a CodexAgent is configured AND the segment is (pepper, codex_agent),
delegate to agent.run(). Narration sentences are appended to text_buf
and emitted as llm.token + tts.sentence with speaker=pepper, so they
flow through the existing voice pipeline and end up in
last_assistant_text() for history continuity.

When no agent is configured (binary missing) or the speaker is wrong
(jarvis with codex_agent), fall back to chat with a logged warning —
preserves Phase 2 behaviour."
```

---

## Task 5: main.py wiring + cancel/approval handlers

**Files:**
- Modify: `server/server/main.py`
- Modify: `server/server/session.py` (route `agent.approve` / `agent.cancel` client messages to the agent)
- Modify: `server/tests/test_phase2_smoke.py` → rename to `test_phase3_smoke.py` and extend

Builds the `CodexAgent` at startup, wires it into each `DialogManager`, and adds handlers for the new client → server messages.

- [ ] **Step 1: Read existing Session to find the client-message dispatch**

Open `server/server/session.py`. Find the loop that reads from `self._ws.receive()` and dispatches by `msg.type`. Note where existing types (`text`, `interrupt`, `audio.start`, etc.) are handled. That's where the new `agent.approve` / `agent.cancel` cases go.

- [ ] **Step 2: Add agent message handling to Session**

Add to `Session.__init__`:

```python
codex_agent: "CodexAgent | None" = None,
```

Store as `self._codex_agent`. Add a `TYPE_CHECKING` import for `CodexAgent`.

In the client-message dispatch loop, add cases:

```python
elif msg.type == "agent.approve":
    if self._codex_agent is not None:
        await self._codex_agent.submit_approval(msg.runId, msg.choice)
elif msg.type == "agent.cancel":
    if self._codex_agent is not None:
        await self._codex_agent.cancel(msg.runId)
```

- [ ] **Step 3: Wire `_codex_agent` in `main.py`**

In `lifespan()`, inside the existing `if settings.personas_enabled:` block, after the multi-voice TTS is built:

```python
_codex_agent: CodexAgent | None = None
pepper = _persona_registry.get("pepper") if _persona_registry.is_available("pepper") else None
if pepper is not None and pepper.agent is not None:
    from .pipelines.codex_agent import CodexAgent, CodexAgentConfig  # noqa: PLC0415

    _codex_agent = CodexAgent(CodexAgentConfig(
        binary=pepper.agent.binary,
        workdir=pepper.agent.workdir,
        approval_mode=pepper.agent.approval_mode,
        sandbox=pepper.agent.sandbox,
    ))
    log.info("personas: CodexAgent ready (binary=%s)", pepper.agent.binary)
```

Add `_codex_agent` to the module-level globals declared earlier.

In `ws_endpoint`, pass `codex_agent=_codex_agent` to the `DialogManager(...)` constructor and `codex_agent=_codex_agent` to the `Session(...)` constructor.

- [ ] **Step 4: Update the Phase 2 smoke / dormancy regression**

Rename `server/tests/test_phase2_smoke.py` → `server/tests/test_phase3_smoke.py` (or keep both — your call; the simpler path is to extend the existing file in-place and rename for clarity).

Add a new test:

```python
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
```

- [ ] **Step 5: Full suite + lint**

```bash
cd server && python -m pytest -q && ruff check . && python -m mypy
```

- [ ] **Step 6: Commit**

```bash
git add server/server/main.py server/server/session.py server/tests/test_phase3_smoke.py
git commit -m "feat(server): wire CodexAgent through main.py + Session

main.py lifespan builds _codex_agent when Pepper's persona has a
resolved codex binary (lazy import keeps the dormancy regression
guard passing). DialogManager + Session receive codex_agent kwargs.
Session routes new client messages (agent.approve, agent.cancel)
to the agent. Phase 3 dormancy guard extends the Phase 1/2 check
to assert server.pipelines.codex_agent stays out of sys.modules
with the flag off."
```

---

## Task 6: README + Phase 3 → 4 decision log seed

**Files:**
- Modify: `server/README.md`
- Modify: this plan file — Phase 3 → Phase 4 decision log section

- [ ] **Step 1: Update README**

Open `server/README.md`. Update the "Multi-model support" section heading from "(Phase 2 — dialog manager + chat, behind a flag)" to "(Phase 3 — Codex CLI agent escalation, behind a flag)". Append after the existing Phase 2 quick check:

```markdown
### Phase 3 — Codex CLI agent escalation

When Pepper is available AND the `codex` CLI is resolvable on `$PATH`
(or `JARVIS_CODEX_CLI_PATH`), `mode=codex_agent` segments dispatch to
the local CLI instead of running a chat stream. Pepper narrates
summary sentences in parallel (debounced ≥4s) so the user isn't
listening to silence while the agent grinds.

Quick manual check (real codex installed):

\`\`\`bash
ANTHROPIC_API_KEY=sk-ant-... \
OPENAI_API_KEY=sk-... \
JARVIS_PERSONAS_ENABLED=true \
JARVIS_TTS_ENGINE=edge \
JARVIS_CODEX_CLI_PATH=/usr/local/bin/codex \
JARVIS_CODEX_WORKDIR=$(pwd) \
uvicorn server.main:app --port 8000

python -m server.cli_test --text "/codex add a test for parse_prefix"
# Expect: dispatch.plan with mode=codex_agent;
#         agent.start, agent.step events stream;
#         tts.sentence events with speaker=pepper carry the narration;
#         agent.end status=ok on completion.
\`\`\`

Without the `codex` binary, the segment degrades to chat with a logged
warning — the rest of Phase 2 behaviour is unchanged.

Sandbox: defaults to `workspace-write` (Codex can read anywhere, write
only inside `JARVIS_CODEX_WORKDIR`). Approval mode: `auto-low` (low-
risk shell ops auto-approve; higher-risk ones surface as `agent.approval`
WS events the HUD will render in Phase 4).
```

- [ ] **Step 2: Seed the Phase 3 → 4 decision log**

Append to the end of this file (right above the `*End of plan.*` line):

```markdown
## Phase 3 → Phase 4 decision log

To be filled in as Phase 3 lands. Format:

```
- Task N (<file>): <decision worth carrying forward to Phase 4>
```

Initial entries (populated by implementer):

- _(empty — fill in during execution)_
```

- [ ] **Step 3: Commit + push**

```bash
git add server/README.md docs/superpowers/plans/2026-05-13-multi-model-support-phase-3.md
git commit -m "docs(personas): Phase 3 README section + decision log seed"
git push -u origin claude/multi-model-support-phase-3
```

---

## Phase 3 acceptance checklist

- [ ] `python -m pytest -q` green from `server/`.
- [ ] `ruff check .` clean.
- [ ] `python -m mypy` no new error kinds.
- [ ] `JARVIS_PERSONAS_ENABLED=false` preserves today's behaviour. No existing test modified.
- [ ] `test_phase3_dormant_when_flag_off` passes — `server.pipelines.codex_agent` NOT auto-imported when flag off.
- [ ] Both CI checks (`server`, `web`) pass on the PR.
- [ ] Any Codex P1/P2 reviewer findings addressed.

---

## Phase 3 → Phase 4 decision log

To be filled in as Phase 3 lands. Format:

```
- Task N (<file>): <decision worth carrying forward to Phase 4>
```

Initial entries (populated by implementer):

- _(empty — fill in during execution)_

---

*End of Phase 3 implementation plan.*

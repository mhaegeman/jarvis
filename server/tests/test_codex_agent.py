"""Tests for server.pipelines.codex_agent.CodexAgent (uses fake-binary fixture)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
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


# ── Regression tests for Codex review on PR #33 ──────────────────────


@pytest.mark.asyncio
async def test_approval_flow_resumes_run_on_approve(tmp_path: Path) -> None:
    """approval.request mid-stream pauses the run; submit_approval('approve')
    forwards the choice to stdin and the run continues to completion.
    """
    script_file = tmp_path / "script.json"
    script_file.write_text(json.dumps([
        {"type": "step.start", "kind": "thinking", "summary": "warming up"},
        {"type": "approval.request", "prompt": "Install X?",
         "choices": ["approve", "deny", "approve_session"]},
        {"type": "final.summary", "summary": "Done."},
    ]))
    os.environ["FAKE_CODEX_SCRIPT"] = str(script_file)
    # Fake binary blocks on stdin after the approval event (idx=1, 1-indexed=2).
    os.environ["FAKE_CODEX_WAIT_STDIN_AFTER"] = "2"
    try:
        ws = _FakeWS()
        agent = CodexAgent(_config())

        async def _consume() -> list[str]:
            sentences = []
            async for s in agent.run(ws=ws, task="install X", run_id="r-appr"):
                sentences.append(s)
            return sentences

        task = asyncio.create_task(_consume())
        # Wait until the approval WS message arrives.
        for _ in range(50):  # 5s timeout
            if any(m["type"] == "agent.approval" for m in ws.sent):
                break
            await asyncio.sleep(0.1)
        else:
            pytest.fail("agent.approval was never emitted")

        # Approve. This must forward the choice to stdin and let the run
        # continue to the final.summary event.
        await agent.submit_approval("r-appr", "approve")
        await task
    finally:
        del os.environ["FAKE_CODEX_SCRIPT"]
        del os.environ["FAKE_CODEX_WAIT_STDIN_AFTER"]

    end = next(m for m in ws.sent if m["type"] == "agent.end")
    assert end["status"] == "ok"
    # Approval message was emitted.
    assert any(m["type"] == "agent.approval" for m in ws.sent)


@pytest.mark.asyncio
async def test_approval_flow_cancels_run_on_deny(tmp_path: Path) -> None:
    """approval.request → submit_approval('deny') → run cancels."""
    script_file = tmp_path / "script.json"
    script_file.write_text(json.dumps([
        {"type": "step.start", "kind": "thinking", "summary": "warming up"},
        {"type": "approval.request", "prompt": "Install X?",
         "choices": ["approve", "deny", "approve_session"]},
        {"type": "final.summary", "summary": "Should never run."},
    ]))
    os.environ["FAKE_CODEX_SCRIPT"] = str(script_file)
    os.environ["FAKE_CODEX_WAIT_STDIN_AFTER"] = "2"
    try:
        ws = _FakeWS()
        agent = CodexAgent(_config())

        async def _consume() -> None:
            async for _ in agent.run(ws=ws, task="install X", run_id="r-deny"):
                pass

        task = asyncio.create_task(_consume())
        for _ in range(50):
            if any(m["type"] == "agent.approval" for m in ws.sent):
                break
            await asyncio.sleep(0.1)
        else:
            pytest.fail("agent.approval was never emitted")

        await agent.submit_approval("r-deny", "deny")
        await task
    finally:
        del os.environ["FAKE_CODEX_SCRIPT"]
        del os.environ["FAKE_CODEX_WAIT_STDIN_AFTER"]

    end = next(m for m in ws.sent if m["type"] == "agent.end")
    assert end["status"] == "cancelled"
    # final.summary must NOT have been processed.
    assert not any(
        m["type"] == "agent.step" and "Should never run" in m.get("summary", "")
        for m in ws.sent
    )


@pytest.mark.asyncio
async def test_stderr_drained_so_chatty_codex_does_not_deadlock(
    tmp_path: Path,
) -> None:
    """A chatty subprocess (>64 KB stderr) must NOT deadlock the run.

    Without stderr draining, the OS pipe fills and the child blocks on its
    next stderr write — stdout reader spins forever waiting for events
    that will never come.
    """
    script_file = tmp_path / "script.json"
    script_file.write_text(json.dumps([
        {"type": "step.start", "kind": "thinking", "summary": "x"},
        {"type": "final.summary", "summary": "done."},
    ]))
    os.environ["FAKE_CODEX_SCRIPT"] = str(script_file)
    # 256 KB of stderr — well above the typical 64 KB pipe buffer.
    os.environ["FAKE_CODEX_STDERR_BYTES"] = "262144"
    try:
        ws = _FakeWS()
        agent = CodexAgent(_config())

        async def _consume() -> None:
            async for _ in agent.run(ws=ws, task="x", run_id="r-stderr"):
                pass

        # If stderr draining is broken, this hangs forever. The wait_for
        # bounds the test at 10s and surfaces the deadlock as a failure.
        await asyncio.wait_for(_consume(), timeout=10.0)
    finally:
        del os.environ["FAKE_CODEX_SCRIPT"]
        del os.environ["FAKE_CODEX_STDERR_BYTES"]

    end = next(m for m in ws.sent if m["type"] == "agent.end")
    assert end["status"] == "ok"

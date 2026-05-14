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
            sentence = "Codex CLI is not installed or missing from the path; I can't run that here."
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

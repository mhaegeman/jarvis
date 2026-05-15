#!/usr/bin/env python3
"""Fake `codex` CLI for tests.

Emits a stream of JSON-line events on stdout, optionally pausing on
`approval.request` events until a sentinel is written to a control file.

Usage (matches what `CodexAgent` will spawn):

    python fake_codex.py exec --json --sandbox <mode> --approval-mode <mode> \\
        --cd <workdir> "<task>"

Behaviour is controlled by env vars (so tests can script the fixture
without writing a wrapper):

    FAKE_CODEX_SCRIPT       — path to a JSON file with a list of events to emit
                              (default: a hard-coded "happy path" sequence)
    FAKE_CODEX_DELAY_MS     — sleep between events (default: 0)
    FAKE_CODEX_EXIT_CODE    — process exit code (default: 0)
    FAKE_CODEX_HANG_AFTER   — if set to an int N, emit N events then sleep forever
    FAKE_CODEX_STDERR_BYTES — if set, emit this many bytes to stderr at start.
                              Used to verify the parent drains stderr (otherwise
                              the OS pipe buffer fills and the child blocks).
    FAKE_CODEX_WAIT_STDIN_AFTER  — if set to an int N, after emitting the Nth
                                   event, block on stdin.readline() before
                                   continuing. Used to test the approval flow.
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
    stderr_bytes_raw = os.environ.get("FAKE_CODEX_STDERR_BYTES")
    stderr_bytes = int(stderr_bytes_raw) if stderr_bytes_raw else 0
    wait_stdin_after_raw = os.environ.get("FAKE_CODEX_WAIT_STDIN_AFTER")
    wait_stdin_after = int(wait_stdin_after_raw) if wait_stdin_after_raw else None

    # Spray stderr first so the parent has to drain it to keep us alive.
    if stderr_bytes > 0:
        sys.stderr.write("X" * stderr_bytes + "\n")
        sys.stderr.flush()

    script = _load_script()
    for idx, event in enumerate(script):
        if hang_after is not None and idx >= hang_after:
            # Simulate a hung process — sleep until killed.
            while True:
                time.sleep(60)
        sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()
        if wait_stdin_after is not None and idx == wait_stdin_after - 1:
            # Block until the parent writes one line (the approval response).
            # If the parent never writes, we hang here — that's the test's job
            # to either call cancel() or call submit_approval(...).
            sys.stdin.readline()
        if delay_ms:
            time.sleep(delay_ms / 1000.0)

    # If hang_after is set and we emitted exactly hang_after events (i.e.,
    # the script had no more events to trigger the in-loop check), hang now.
    if hang_after is not None and len(script) >= hang_after:
        while True:
            time.sleep(60)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

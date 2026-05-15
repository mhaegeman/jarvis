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

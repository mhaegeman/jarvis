"""Round-trip tests for the WS JSON protocol messages."""

import json

import pytest

from server.protocol import (
    ClientMessage,
    ServerMessage,
    decode_client,
    encode_server,
)


def test_decode_client_text() -> None:
    msg = decode_client('{"type": "text", "content": "hi"}')
    assert msg.type == "text"
    assert msg.content == "hi"


def test_decode_client_hello_optional_capabilities() -> None:
    msg = decode_client('{"type": "hello", "clientVersion": "0.1"}')
    assert msg.type == "hello"
    assert msg.clientVersion == "0.1"
    assert msg.capabilities is None


def test_decode_client_audio_start() -> None:
    msg = decode_client('{"type": "audio.start", "sampleRate": 16000, "format": "pcm_s16le"}')
    assert msg.type == "audio.start"
    assert msg.sampleRate == 16000


def test_decode_client_interrupt() -> None:
    msg = decode_client('{"type": "interrupt"}')
    assert msg.type == "interrupt"


def test_decode_client_unknown_type_raises() -> None:
    with pytest.raises(ValueError, match="unknown"):
        decode_client('{"type": "nope"}')


def test_decode_client_malformed_json_raises() -> None:
    with pytest.raises(ValueError, match="json|JSON"):
        decode_client("not-json")


def test_encode_server_ready() -> None:
    out = encode_server(ServerMessage.ready())
    assert '"type":"ready"' in out


def test_encode_server_llm_token() -> None:
    out = encode_server(ServerMessage.llm_token("hi"))
    assert '"type":"llm.token"' in out
    assert '"delta":"hi"' in out


def test_encode_server_tts_sentence_carries_audio_id() -> None:
    out = encode_server(ServerMessage.tts_sentence(text="ok.", audio_id="s0-abc12"))
    assert '"audioId":"s0-abc12"' in out
    assert '"text":"ok."' in out


def test_encode_server_error() -> None:
    out = encode_server(ServerMessage.error(code="x.y", message="boom"))
    assert '"code":"x.y"' in out


def test_encode_server_telemetry_includes_ts() -> None:
    out = encode_server(ServerMessage.telemetry(level="info", message="hello"))
    assert '"ts":' in out
    assert '"level":"info"' in out


def test_client_message_is_a_union() -> None:
    """Type alias / union forms a discriminated set."""
    msg: ClientMessage = decode_client('{"type": "interrupt"}')
    assert msg.type == "interrupt"


# ─── v2 panels protocol additions ─────────────────────────────────────────


def test_decode_client_pong() -> None:
    msg = decode_client('{"type": "pong", "seq": 7}')
    assert msg.type == "pong"
    assert msg.seq == 7


def test_decode_client_pong_rejects_negative_seq() -> None:
    with pytest.raises(ValueError):
        decode_client('{"type": "pong", "seq": -1}')


def test_ready_with_session_id() -> None:
    out = encode_server(ServerMessage.ready(session_id="abc-123"))
    assert '"type":"ready"' in out
    assert '"sessionId":"abc-123"' in out


def test_ready_without_session_id_omits_field() -> None:
    out = encode_server(ServerMessage.ready())
    assert '"type":"ready"' in out
    assert "sessionId" not in out


def test_state_snapshot_round_trip() -> None:
    out = encode_server(
        ServerMessage.state_snapshot(
            system={"load": 12.5, "tokensPerMin": 240, "sessionId": "s1", "modelName": "mock"},
            memory={"contextUsed": 1024, "contextMax": 200000},
            network={
                "endpoint": "ws://localhost:8000/ws",
                "latencyMs": 4.2,
                "packets": 17,
                "sendQueueDepth": 3,
                "sendQueueMax": 256,
            },
            tasks={"queued": 1, "active": 2, "done": 5},
        )
    )
    payload = json.loads(out)
    assert payload["type"] == "state.snapshot"
    assert payload["system"]["modelName"] == "mock"
    assert payload["memory"]["contextMax"] == 200000
    assert payload["network"]["latencyMs"] == 4.2
    assert payload["tasks"]["done"] == 5


def test_state_snapshot_accepts_null_latency() -> None:
    out = encode_server(
        ServerMessage.state_snapshot(
            system={"load": 0, "tokensPerMin": 0, "sessionId": "s", "modelName": "m"},
            memory={"contextUsed": 0, "contextMax": 1},
            network={
                "endpoint": "x",
                "latencyMs": None,
                "packets": 0,
                "sendQueueDepth": 0,
                "sendQueueMax": 256,
            },
            tasks={"queued": 0, "active": 0, "done": 0},
        )
    )
    payload = json.loads(out)
    assert payload["network"]["latencyMs"] is None


def test_calendar_update_round_trip() -> None:
    out = encode_server(
        ServerMessage.calendar_update(
            entries=[
                {"time": "09:00", "title": "Standup", "durationMin": 30},
                {"time": "11:30", "title": "Lunch", "durationMin": 60},
            ]
        )
    )
    payload = json.loads(out)
    assert payload["type"] == "calendar.update"
    assert payload["entries"][0]["title"] == "Standup"
    assert payload["entries"][1]["durationMin"] == 60


def test_calendar_update_empty_entries() -> None:
    out = encode_server(ServerMessage.calendar_update(entries=[]))
    payload = json.loads(out)
    assert payload["type"] == "calendar.update"
    assert payload["entries"] == []


def test_ping_round_trip() -> None:
    out = encode_server(ServerMessage.ping(seq=42))
    payload = json.loads(out)
    assert payload["type"] == "ping"
    assert payload["seq"] == 42

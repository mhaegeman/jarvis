"""Round-trip tests for the WS JSON protocol messages."""

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

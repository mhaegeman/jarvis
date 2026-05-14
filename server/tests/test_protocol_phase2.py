"""Round-trip tests for Phase 2 protocol additions."""

from __future__ import annotations

import json

from server.protocol import ServerMessage, encode_server


def test_llm_token_without_speaker_unchanged() -> None:
    """Back-compat: old shape still produced when speaker omitted."""
    msg = ServerMessage.llm_token("hello")
    assert msg == {"type": "llm.token", "delta": "hello"}
    encoded = json.loads(encode_server(msg))
    assert "speaker" not in encoded
    assert "segmentIdx" not in encoded


def test_llm_token_with_speaker_and_segment() -> None:
    msg = ServerMessage.llm_token("hi", speaker="pepper", segment_idx=1)
    assert msg["type"] == "llm.token"
    assert msg["delta"] == "hi"
    assert msg["speaker"] == "pepper"
    assert msg["segmentIdx"] == 1


def test_llm_segment_end() -> None:
    msg = ServerMessage.llm_segment_end(speaker="jarvis", segment_idx=0)
    assert msg == {"type": "llm.segment_end", "speaker": "jarvis", "segmentIdx": 0}


def test_dispatch_plan() -> None:
    msg = ServerMessage.dispatch_plan(
        turn_id="t-abc",
        segments=[
            {"speaker": "jarvis", "tier": "balanced", "mode": "chat", "intent": "design"},
            {"speaker": "pepper", "tier": "deep", "mode": "chat", "intent": "implement"},
        ],
        rationale="design then implement",
    )
    assert msg["type"] == "dispatch.plan"
    assert msg["turnId"] == "t-abc"
    assert len(msg["segments"]) == 2
    assert msg["rationale"] == "design then implement"
    # Encoded JSON round-trips
    decoded = json.loads(encode_server(msg))
    assert decoded == msg


def test_tts_sentence_without_speaker_unchanged() -> None:
    msg = ServerMessage.tts_sentence("hi.", "audio-1")
    assert msg == {"type": "tts.sentence", "text": "hi.", "audioId": "audio-1"}


def test_tts_sentence_with_speaker() -> None:
    msg = ServerMessage.tts_sentence("hi.", "audio-1", speaker="pepper")
    assert msg["speaker"] == "pepper"


def test_state_snapshot_personas_field() -> None:
    msg = ServerMessage.state_snapshot(
        system={
            "load": 0.1,
            "tokensPerMin": 0,
            "sessionId": "s1",
            "modelName": "claude-haiku-4-5",
            "personas": {
                "jarvis": {"model": "claude-haiku-4-5", "tier": "fast", "status": "idle"},
                "pepper": {"model": "gpt-5-mini", "tier": "fast", "status": "idle"},
                "lastDispatch": None,
            },
        },
        memory={"contextUsed": 0, "contextMax": 200000},
        network={"endpoint": "ws://localhost:8000/ws", "latencyMs": 12, "packets": 5,
                 "sendQueueDepth": 0, "sendQueueMax": 32},
        tasks={"active": 0, "queued": 0, "done": 0},
    )
    assert "personas" in msg["system"]
    assert msg["system"]["personas"]["jarvis"]["model"] == "claude-haiku-4-5"

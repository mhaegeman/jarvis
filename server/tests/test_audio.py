"""Tests for the binary frame format (spec §4.4)."""

import pytest

from server.audio import (
    KIND_CLIENT_MIC,
    KIND_SERVER_TTS,
    decode_audio_frame,
    encode_mic_chunk,
    encode_tts_chunk,
)


def test_round_trip_tts_chunk() -> None:
    pcm = b"\x01\x02\x03\x04\x05\x06"
    frame = encode_tts_chunk("s0-abc12", pcm)
    decoded = decode_audio_frame(frame)
    assert decoded.kind == KIND_SERVER_TTS
    assert decoded.audio_id == "s0-abc12"
    assert decoded.samples == pcm


def test_round_trip_mic_chunk() -> None:
    pcm = b"\x10" * 320
    frame = encode_mic_chunk(pcm)
    decoded = decode_audio_frame(frame)
    assert decoded.kind == KIND_CLIENT_MIC
    assert decoded.audio_id == ""
    assert decoded.samples == pcm


def test_max_length_audio_id() -> None:
    long_id = "x" * 255
    frame = encode_tts_chunk(long_id, b"abc")
    decoded = decode_audio_frame(frame)
    assert decoded.audio_id == long_id


def test_audio_id_too_long_raises() -> None:
    with pytest.raises(ValueError, match="audioId"):
        encode_tts_chunk("y" * 256, b"abc")


def test_decode_truncated_frame_raises() -> None:
    with pytest.raises(ValueError, match="truncated|short"):
        decode_audio_frame(b"\x02\x05ab")


def test_decode_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="kind"):
        decode_audio_frame(b"\xff\x00")


def test_empty_audio_id_for_mic_chunk() -> None:
    frame = encode_mic_chunk(b"")
    decoded = decode_audio_frame(frame)
    assert decoded.audio_id == ""
    assert decoded.samples == b""


def test_int16_pcm_is_passed_through_byte_for_byte() -> None:
    """PCM payload is opaque bytes; encoder must not transform samples."""
    import struct

    pcm = struct.pack("<5h", 0, 1, -1, 32767, -32768)
    frame = encode_tts_chunk("a", pcm)
    decoded = decode_audio_frame(frame)
    assert decoded.samples == pcm

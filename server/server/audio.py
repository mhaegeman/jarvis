"""Binary frame format for audio chunks (spec §4.4).

Layout:
    ┌───────────┬───────────┬─────────────┬────────────────────┐
    │ kind (1B) │ idLen(1B) │ id (idLen)  │ samples (PCM, ...) │
    └───────────┴───────────┴─────────────┴────────────────────┘
"""

from __future__ import annotations

from dataclasses import dataclass

KIND_CLIENT_MIC = 0x01
KIND_SERVER_TTS = 0x02


@dataclass(frozen=True, slots=True)
class AudioFrame:
    kind: int
    audio_id: str
    samples: bytes


def encode_tts_chunk(audio_id: str, pcm: bytes) -> bytes:
    id_bytes = audio_id.encode("ascii")
    if len(id_bytes) > 255:
        raise ValueError(f"audioId too long: {len(id_bytes)} > 255")
    return bytes([KIND_SERVER_TTS, len(id_bytes)]) + id_bytes + pcm


def encode_mic_chunk(pcm: bytes) -> bytes:
    return bytes([KIND_CLIENT_MIC, 0]) + pcm


def decode_audio_frame(buf: bytes) -> AudioFrame:
    if len(buf) < 2:
        raise ValueError("frame truncated: header < 2 bytes")
    kind = buf[0]
    if kind not in (KIND_CLIENT_MIC, KIND_SERVER_TTS):
        raise ValueError(f"unknown kind byte: 0x{kind:02x}")
    id_len = buf[1]
    if len(buf) < 2 + id_len:
        raise ValueError(f"frame truncated: id ({id_len}B) exceeds buffer")
    audio_id = buf[2 : 2 + id_len].decode("ascii")
    samples = bytes(buf[2 + id_len :])
    return AudioFrame(kind=kind, audio_id=audio_id, samples=samples)

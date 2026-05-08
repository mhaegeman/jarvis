"""WS JSON protocol — pydantic-modeled messages with discriminated union."""

from __future__ import annotations

import json
import time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, NonNegativeInt, ValidationError

# ─── Client → Server ──────────────────────────────────────────────────────


class _Base(BaseModel):
    model_config = {"extra": "forbid"}


class Hello(_Base):
    type: Literal["hello"]
    clientVersion: str
    capabilities: dict[str, Any] | None = None


class AudioStart(_Base):
    type: Literal["audio.start"]
    sampleRate: int
    format: Literal["pcm_s16le"] = "pcm_s16le"


class AudioEnd(_Base):
    type: Literal["audio.end"]


class TextIn(_Base):
    type: Literal["text"]
    content: str


class Interrupt(_Base):
    type: Literal["interrupt"]


class Pong(_Base):
    type: Literal["pong"]
    seq: NonNegativeInt


ClientMessage = Annotated[
    Hello | AudioStart | AudioEnd | TextIn | Interrupt | Pong,
    Field(discriminator="type"),
]


class _ClientEnvelope(BaseModel):
    body: ClientMessage


def decode_client(raw: str) -> ClientMessage:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"malformed json: {e}") from e
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError("missing 'type'")
    try:
        return _ClientEnvelope.model_validate({"body": data}).body
    except ValidationError as e:
        msg = str(e)
        if "discriminator" in msg or "tag" in msg:
            raise ValueError(f"unknown type: {data.get('type')}") from e
        raise ValueError(f"invalid message: {e}") from e


# ─── Server → Client ──────────────────────────────────────────────────────


class ServerMessage:
    """Factory class — methods return JSON-serializable dicts."""

    @staticmethod
    def ready(*, session_id: str | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {"type": "ready"}
        if session_id is not None:
            out["sessionId"] = session_id
        return out

    @staticmethod
    def stt_partial(text: str) -> dict[str, Any]:
        return {"type": "stt.partial", "text": text}

    @staticmethod
    def stt_final(text: str) -> dict[str, Any]:
        return {"type": "stt.final", "text": text}

    @staticmethod
    def llm_token(delta: str) -> dict[str, Any]:
        return {"type": "llm.token", "delta": delta}

    @staticmethod
    def llm_end() -> dict[str, Any]:
        return {"type": "llm.end"}

    @staticmethod
    def tts_sentence(text: str, audio_id: str) -> dict[str, Any]:
        return {
            "type": "tts.sentence",
            "text": text,
            "audioId": audio_id,
        }

    @staticmethod
    def tts_end(audio_id: str) -> dict[str, Any]:
        return {"type": "tts.end", "audioId": audio_id}

    @staticmethod
    def error(code: str, message: str) -> dict[str, Any]:
        return {"type": "error", "code": code, "message": message}

    @staticmethod
    def telemetry(level: str, message: str, ts: float | None = None) -> dict[str, Any]:
        return {
            "type": "telemetry",
            "ts": ts if ts is not None else time.time(),
            "level": level,
            "message": message,
        }

    @staticmethod
    def state_snapshot(
        *,
        system: dict[str, Any],
        memory: dict[str, Any],
        network: dict[str, Any],
        tasks: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "type": "state.snapshot",
            "system": system,
            "memory": memory,
            "network": network,
            "tasks": tasks,
        }

    @staticmethod
    def calendar_update(*, entries: list[dict[str, Any]]) -> dict[str, Any]:
        return {"type": "calendar.update", "entries": entries}

    @staticmethod
    def ping(*, seq: int) -> dict[str, Any]:
        return {"type": "ping", "seq": seq}


def encode_server(msg: dict[str, Any]) -> str:
    return json.dumps(msg, separators=(",", ":"))

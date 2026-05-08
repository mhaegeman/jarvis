"""FastAPI app + WebSocket endpoint."""

from __future__ import annotations

import contextlib
import importlib.util
import logging
from collections.abc import AsyncIterator, MutableMapping
from typing import Any

import anthropic
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import settings
from .pipelines.claude_llm import ClaudeLLM
from .pipelines.interfaces import LLM, STT
from .pipelines.mock_llm import MockLLM
from .pipelines.mock_stt import MockSTT
from .pipelines.mock_tts import MockTTS
from .session import Session

logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)


def _build_llm() -> LLM:
    """Construct the LLM pipeline based on `JARVIS_MODEL_NAME`.

    Raises:
        RuntimeError: when a Claude model is selected but `ANTHROPIC_API_KEY` is unset
            (in either the process environment or `.env`).
        ValueError: when `model_name` is not 'mock' and does not start with 'claude-'.
    """
    name = settings.model_name
    if name == "mock":
        return MockLLM()
    if name.startswith("claude-"):
        if settings.anthropic_api_key is None:
            raise RuntimeError(
                "JARVIS_MODEL_NAME selects a Claude model but ANTHROPIC_API_KEY is unset."
            )
        client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value()
        )
        return ClaudeLLM(
            default_model=name,
            max_tokens=settings.llm_max_tokens,
            client=client,
        )
    raise ValueError(f"unknown JARVIS_MODEL_NAME: {name!r}")


def _resolve_device() -> str:
    """Return the torch device string for STT/TTS pipelines.

    Honors `JARVIS_DEVICE` when set to a concrete value; with `auto`,
    probes torch (cuda → mps → cpu) and falls back to `cpu` when torch
    is not importable.
    """
    explicit = settings.device
    if explicit in ("cuda", "mps", "cpu"):
        return explicit
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _build_stt() -> STT:
    """Construct the STT pipeline based on `JARVIS_STT_ENGINE`.

    `auto` (default) returns `WhisperSTT` when faster-whisper is importable,
    otherwise logs a warning and returns `MockSTT`. Setting the engine
    explicitly to `whisper` makes a missing dep a hard `ImportError`.

    Raises:
        ImportError: when `engine="whisper"` and faster-whisper is not installed.
        ValueError: when `engine` is not one of {auto, mock, whisper}.
    """
    engine = settings.stt_engine
    if engine == "mock":
        return MockSTT()
    if engine in ("auto", "whisper"):
        if importlib.util.find_spec("faster_whisper") is None:
            if engine == "whisper":
                raise ImportError(
                    "faster-whisper is not installed; run `pip install -e .[stt]`."
                )
            log.warning(
                "STT auto: faster-whisper not installed; using MockSTT. "
                "Install with `pip install -e .[stt]`."
            )
            return MockSTT()
        from .pipelines.whisper_stt import WhisperSTT
        return WhisperSTT(
            model=settings.whisper_model,
            device=_resolve_device(),
        )
    raise ValueError(f"unknown JARVIS_STT_ENGINE: {engine!r}")


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    log.info("lifespan: Phase 1 mock pipelines (no model loading)")
    yield


app = FastAPI(lifespan=lifespan, title="Jarvis backend (spec-02 Phase 1)")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


class _StarletteWSAdapter:
    """Adapter so Session._WS protocol matches FastAPI WebSocket."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def send_text(self, data: str) -> None:
        await self._ws.send_text(data)

    async def send_bytes(self, data: bytes) -> None:
        await self._ws.send_bytes(data)

    async def receive(self) -> MutableMapping[str, Any]:
        return await self._ws.receive()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    # Per-connection pipeline instances. Construction is cheap — heavy
    # state (Whisper model, Anthropic client) lives in module-level
    # singletons inside the wrappers.
    session = Session(
        ws=_StarletteWSAdapter(ws),
        stt=_build_stt(),
        llm=_build_llm(),
        tts=MockTTS(),
    )
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    finally:
        await session.cleanup()
        with contextlib.suppress(Exception):
            await ws.close()

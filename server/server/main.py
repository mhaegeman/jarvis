"""FastAPI app + WebSocket endpoint."""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import AsyncIterator, MutableMapping
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import settings
from .pipelines.claude_llm import ClaudeLLM
from .pipelines.interfaces import LLM
from .pipelines.mock_llm import MockLLM
from .pipelines.mock_stt import MockSTT
from .pipelines.mock_tts import MockTTS
from .session import Session

logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)


def _build_llm() -> LLM:
    """Construct the LLM pipeline based on `JARVIS_MODEL_NAME`.

    Raises:
        RuntimeError: when a Claude model is selected but `ANTHROPIC_API_KEY` is unset.
        ValueError: when `model_name` is not 'mock' and does not start with 'claude-'.
    """
    name = settings.model_name
    if name == "mock":
        return MockLLM()
    if name.startswith("claude-"):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "JARVIS_MODEL_NAME selects a Claude model but ANTHROPIC_API_KEY is unset."
            )
        return ClaudeLLM(default_model=name, max_tokens=settings.llm_max_tokens)
    raise ValueError(f"unknown JARVIS_MODEL_NAME: {name!r}")


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
    # Per-connection pipelines (stateless; cheap to allocate).
    session = Session(
        ws=_StarletteWSAdapter(ws),
        stt=MockSTT(),
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

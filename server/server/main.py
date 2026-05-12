"""FastAPI app + WebSocket endpoint."""

from __future__ import annotations

import contextlib
import importlib.util
import logging
import os
import secrets
import subprocess
from collections.abc import AsyncIterator, MutableMapping
from pathlib import Path
from typing import Any

import anthropic
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel as _BaseModel

from . import git_status as git_status_mod
from .config import settings
from .memory.store import MemoryStore
from .memory.summarizer import ClaudeSummarizer, Summarizer
from .pipelines.claude_llm import ClaudeLLM
from .pipelines.interfaces import LLM, STT, TTS
from .pipelines.mock_llm import MockLLM
from .pipelines.mock_stt import MockSTT
from .pipelines.mock_tts import MockTTS
from .session import Session

logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)

_memory_store: MemoryStore | None = None
_summarizer: Summarizer | None = None


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


def _build_summarizer() -> Summarizer | None:
    if settings.anthropic_api_key is None:
        log.warning("memory: ANTHROPIC_API_KEY unset; summarization disabled")
        return None
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    return ClaudeSummarizer(client=client, model=settings.memory_model)


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
        import torch  # type: ignore[import-not-found]
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


def _openvoice_assets_present(path: str) -> bool:
    """Cheap path-existence check for the OpenVoice clone OpenVoiceTTS expects.

    `_default_loader` requires `api.py` and the `checkpoints/base_speakers/EN/`
    + `checkpoints/converter/` subtrees. If any is missing, instantiation
    succeeds (it's lazy) but the first synthesize blows up inside
    `_default_loader` and the user gets `session.turn_failed` on every turn.
    Validating at factory time keeps the documented mock fallback intact.
    """
    base = Path(path).expanduser()
    required = (
        base / "api.py",
        base / "checkpoints" / "base_speakers" / "EN" / "checkpoint.pth",
        base / "checkpoints" / "converter" / "checkpoint.pth",
    )
    return all(p.exists() for p in required)


def _build_tts() -> TTS:
    """Construct the TTS pipeline based on `JARVIS_TTS_ENGINE`.

    `auto` (default) tries openvoice first, then edge-tts, then falls back to
    MockTTS with a warning. Explicit engine names make missing prerequisites a
    hard error.

    Raises:
        ImportError: when `engine="openvoice"` and torch is not installed,
            or `engine="edge"` and edge-tts/miniaudio are not installed.
        FileNotFoundError: when `engine="openvoice"` and the OpenVoice clone
            is missing or incomplete at `JARVIS_OPENVOICE_PATH`.
        ValueError: when `engine` is not one of {auto, mock, openvoice, edge}.
    """
    engine = settings.tts_engine
    if engine == "mock":
        return MockTTS()

    # --- openvoice (explicit or auto) ---
    if engine in ("auto", "openvoice"):
        if importlib.util.find_spec("torch") is None:
            if engine == "openvoice":
                raise ImportError(
                    "torch is not installed; run `pip install -e .[tts]`."
                )
            log.warning("TTS auto: torch not installed; skipping OpenVoice.")
        elif not _openvoice_assets_present(settings.openvoice_path):
            if engine == "openvoice":
                raise FileNotFoundError(
                    f"OpenVoice assets not found at {settings.openvoice_path!r}; "
                    "see server/deploy/README.md for the clone + checkpoints recipe."
                )
            log.warning(
                "TTS auto: OpenVoice clone missing at %s; skipping.",
                settings.openvoice_path,
            )
        else:
            from .pipelines.openvoice_tts import OpenVoiceTTS
            return OpenVoiceTTS(
                openvoice_path=settings.openvoice_path,
                device=_resolve_device(),
                speaker_wav=settings.speaker_wav,
            )
        # explicit "openvoice": raised above; "auto": fall through to edge.

    # --- edge (explicit or auto falling through from openvoice) ---
    if engine in ("auto", "edge"):
        _has_edge = (
            importlib.util.find_spec("edge_tts") is not None
            and importlib.util.find_spec("miniaudio") is not None
        )
        if not _has_edge:
            if engine == "edge":
                raise ImportError(
                    "edge-tts/miniaudio not installed; "
                    "run `pip install -e .[tts-edge]`."
                )
            log.warning(
                "TTS auto: edge-tts/miniaudio not installed; using MockTTS. "
                "Install with `pip install -e .[tts-edge]`."
            )
            return MockTTS()
        from .pipelines.edge_tts import EdgeTTS
        return EdgeTTS(voice=settings.tts_voice)

    raise ValueError(f"unknown JARVIS_TTS_ENGINE: {engine!r}")


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _memory_store, _summarizer
    log.info("lifespan: Phase 1 mock pipelines (no model loading)")
    if settings.memory_enabled:
        Path(settings.memory_db_path).parent.mkdir(parents=True, exist_ok=True)
        _memory_store = await MemoryStore.open(settings.memory_db_path)
        _summarizer = _build_summarizer()
        log.info("memory: enabled at %s", settings.memory_db_path)
    else:
        log.info("memory: disabled")
    try:
        yield
    finally:
        if _memory_store is not None:
            await _memory_store.close()


app = FastAPI(lifespan=lifespan, title="Jarvis backend (spec-02 Phase 1)")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _git_root() -> Path:
    """Resolve the git root the endpoints operate against.

    Reads ``JARVIS_GIT_ROOT`` from the env at call time so tests can
    monkeypatch the env without re-importing the module. Falls back to
    the process CWD.
    """
    return Path(os.environ.get("JARVIS_GIT_ROOT") or Path.cwd())


class _GitStatusFile(_BaseModel):
    path: str
    status: str


class _GitStatusResponse(_BaseModel):
    branch: str
    files: list[_GitStatusFile]
    buildStatus: str | None = None


class _GitDiffLine(_BaseModel):
    kind: str
    text: str


class _GitDiffResponse(_BaseModel):
    lines: list[_GitDiffLine]


@app.get("/git/status", response_model=_GitStatusResponse)
async def git_status() -> _GitStatusResponse:
    """Return current branch + changed files for the East Code zone.

    ``buildStatus`` is reserved for a future CI poll and is always
    ``None`` for now.
    """
    root = _git_root()
    try:
        branch = git_status_mod.current_branch(root)
        files = git_status_mod.changed_files(root)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="git unavailable") from exc
    return _GitStatusResponse(
        branch=branch,
        files=[_GitStatusFile(path=f.path, status=f.status) for f in files],
        buildStatus=None,
    )


@app.get("/git/diff", response_model=_GitDiffResponse)
async def git_diff(path: str = Query(..., min_length=1)) -> _GitDiffResponse:
    """Return a bounded unified diff for ``path`` relative to the git root."""
    root = _git_root()
    try:
        resolved = git_status_mod.safe_resolve(path, root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="path not found")
    try:
        lines = git_status_mod.diff(path, root)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail="git diff failed") from exc
    return _GitDiffResponse(
        lines=[_GitDiffLine(kind=line.kind, text=line.text) for line in lines],
    )


class _LoginRequest(_BaseModel):
    passphrase: str


@app.post("/auth/login")
async def auth_login(req: _LoginRequest) -> dict[str, str]:
    if settings.passphrase_hash is None:
        raise HTTPException(status_code=503, detail="Auth not configured")
    try:
        from argon2 import PasswordHasher
        from argon2.exceptions import InvalidHashError, VerifyMismatchError
    except ImportError:  # pragma: no cover
        raise HTTPException(status_code=503, detail="Auth not configured") from None
    ph = PasswordHasher()
    try:
        ph.verify(settings.passphrase_hash, req.passphrase)
    except VerifyMismatchError as exc:
        raise HTTPException(status_code=401, detail="Invalid passphrase") from exc
    except (InvalidHashError, ValueError) as exc:
        # JARVIS_PASSPHRASE_HASH is malformed or uses an unsupported algorithm.
        raise HTTPException(status_code=503, detail="Auth misconfigured") from exc
    token = secrets.token_hex(32)
    return {"token": token}


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
        tts=_build_tts(),
        memory=_memory_store,
        summarizer=_summarizer,
        resume_window_minutes=settings.memory_resume_minutes,
        recent_summary_refresh_turns=settings.memory_refresh_turns,
        recent_summary_window=settings.memory_recent_window,
        facts_cap=settings.memory_facts_cap,
    )
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    finally:
        await session.cleanup()
        with contextlib.suppress(Exception):
            await ws.close()

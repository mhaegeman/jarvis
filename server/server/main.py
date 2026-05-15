"""FastAPI app + WebSocket endpoint."""

from __future__ import annotations

import contextlib
import importlib.util
import logging
import os
import secrets
import subprocess
from collections.abc import AsyncIterator, Callable, MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anthropic
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
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

if TYPE_CHECKING:
    from .dialog.dispatcher import LLMBackedDispatcher
    from .dialog.feedback import FeedbackLogger
    from .dialog.manager import DialogManager
    from .dialog.profile_refresher import ProfileRefresher
    from .personas.models import Persona
    from .personas.registry import PersonaRegistry
    from .pipelines.multi_voice_tts import MultiVoiceTTS

logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)

_memory_store: MemoryStore | None = None
_summarizer: Summarizer | None = None

# ── Phase 2: persona infra (only non-None when personas_enabled=true) ──
_persona_registry: PersonaRegistry | None = None
_dispatcher: LLMBackedDispatcher | None = None
_multi_voice_tts: MultiVoiceTTS | None = None
_llm_factory: Callable[[Persona, str], LLM] | None = None
# ── Phase 3: Codex agent (only non-None when binary resolves at startup) ──
_codex_agent: Any = None
# ── Phase 5: learning loop ────────────────────────────────────────────────
_feedback_logger: FeedbackLogger | None = None
_profile_refresher: ProfileRefresher | None = None


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


def _build_llm_factory(
    anthropic_client: Any,
    openai_client: Any,
) -> Callable[[Persona, str], LLM]:
    """Return a factory that creates an LLM per persona + model_id.

    Lazy imports kept inside the factory body so they never execute when
    personas_enabled is False (dormancy regression guard).
    """

    def factory(persona: Persona, model_id: str) -> LLM:
        from .pipelines.claude_llm import ClaudeLLM  # noqa: PLC0415
        from .pipelines.openai_llm import OpenAILLM  # noqa: PLC0415

        if persona.provider == "anthropic":
            return ClaudeLLM(
                default_model=model_id,
                max_tokens=settings.llm_max_tokens,
                system_prompt=persona.system_prompt,
                client=anthropic_client,
            )
        return OpenAILLM(
            default_model=model_id,
            max_tokens=settings.llm_max_tokens,
            system_prompt=persona.system_prompt,
            client=openai_client,
        )

    return factory


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _memory_store, _summarizer
    global _persona_registry, _dispatcher, _multi_voice_tts, _llm_factory, _codex_agent
    global _feedback_logger, _profile_refresher
    log.info("lifespan: Phase 1 mock pipelines (no model loading)")
    if settings.memory_enabled:
        Path(settings.memory_db_path).parent.mkdir(parents=True, exist_ok=True)
        _memory_store = await MemoryStore.open(settings.memory_db_path)
        _summarizer = _build_summarizer()
        log.info("memory: enabled at %s", settings.memory_db_path)
    else:
        log.info("memory: disabled")

    if settings.personas_enabled:
        # ── Phase 2: build persona infra once at startup ────────────────
        # All imports inside this block so dormancy regression guard passes.
        from .dialog.dispatcher import LLMBackedDispatcher  # noqa: PLC0415
        from .dialog.feedback import FeedbackLogger  # noqa: PLC0415
        from .personas.registry import build_registry_from_settings  # noqa: PLC0415
        from .pipelines.multi_voice_tts import MultiVoiceTTS  # noqa: PLC0415

        _persona_registry = build_registry_from_settings(
            settings, codex_workdir=str(_git_root())
        )
        log.info(
            "personas: enabled; available=%s",
            _persona_registry.available_ids(),
        )

        # Build one TTS backend per available persona voice.
        _has_edge = (
            importlib.util.find_spec("edge_tts") is not None
            and importlib.util.find_spec("miniaudio") is not None
        )
        persona_voices: dict[str, TTS] = {}
        for pid in _persona_registry.available_ids():
            persona = _persona_registry.get(pid)
            if _has_edge:
                from .pipelines.edge_tts import EdgeTTS  # noqa: PLC0415

                persona_voices[pid] = EdgeTTS(voice=persona.voice)
            else:
                log.warning(
                    "personas: edge-tts/miniaudio not installed; "
                    "using MockTTS for persona %r voice %r",
                    pid,
                    persona.voice,
                )
                persona_voices[pid] = MockTTS()

        if persona_voices:
            default_speaker = _persona_registry.available_ids()[0]
            _multi_voice_tts = MultiVoiceTTS(
                persona_voices, default_speaker=default_speaker
            )

        # Build the Anthropic client for the dispatcher + Jarvis LLM.
        _anthropic_client: Any = None
        if settings.anthropic_api_key is not None:
            _anthropic_client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key.get_secret_value()
            )

        # Build the OpenAI client for Pepper LLM.
        _openai_client: Any = None
        if settings.openai_api_key is not None:
            import openai  # noqa: PLC0415

            _openai_client = openai.AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                base_url=settings.openai_base_url,
            )

        # Build the dispatcher with formatted persona profiles.
        profiles_parts = []
        for pid in _persona_registry.available_ids():
            p = _persona_registry.get(pid)
            profiles_parts.append(f"{p.display_name} ({pid}): {p.specialty_profile}")
        profiles_text = "\n".join(profiles_parts)

        _dispatcher = LLMBackedDispatcher(
            client=_anthropic_client,
            model=settings.dispatcher_model,
            profiles=profiles_text,
        )

        _llm_factory = _build_llm_factory(_anthropic_client, _openai_client)
        log.info("personas: dispatcher + multi-voice TTS + llm_factory ready")

        # ── Phase 5: learning loop ──────────────────────────────────────
        # FeedbackLogger + ProfileRefresher use the memory DB; they're only
        # constructed when learning_enabled is set (default True).
        if settings.learning_enabled and settings.memory_enabled:
            from .dialog.profile_refresher import ProfileRefresher  # noqa: PLC0415

            _feedback_logger = FeedbackLogger(settings.memory_db_path)
            _profile_refresher = ProfileRefresher(
                registry=_persona_registry,
                feedback=_feedback_logger,
                client=_anthropic_client,
                db_path=settings.memory_db_path,
                model=settings.dispatcher_model,
                warmth=settings.persona_warmth,
            )
            log.info("personas: FeedbackLogger + ProfileRefresher ready")

        # ── Phase 3: Codex agent ────────────────────────────────────────
        # Lazy import inside personas_enabled block so the dormancy
        # regression guard keeps passing with the flag off.
        pepper = (
            _persona_registry.get("pepper")
            if _persona_registry.is_available("pepper")
            else None
        )
        if pepper is not None and pepper.agent is not None:
            from .pipelines.codex_agent import CodexAgent, CodexAgentConfig  # noqa: PLC0415

            _codex_agent = CodexAgent(CodexAgentConfig(
                binary=pepper.agent.binary,
                workdir=pepper.agent.workdir,
                approval_mode=pepper.agent.approval_mode,
                sandbox=pepper.agent.sandbox,
            ))
            log.info("personas: CodexAgent ready (binary=%s)", pepper.agent.binary)

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


def _git_routes_available() -> bool:
    """True iff the resolved git root looks like a real git repo.

    If ``JARVIS_GIT_ROOT`` is unset and the CWD has no ``.git/``, refuse
    to serve git routes — they would otherwise crash on first request and
    take other features down with them. Other server features keep working.
    """
    return (_git_root() / ".git").exists()


# ── Auth: simple in-memory bearer-token store ────────────────────
#
# Tokens minted by ``POST /auth/login`` live in this set for the lifetime
# of the process. They never expire in this iteration — the trade-off is
# documented in ``server/deploy/README.md``: restart the server to revoke.
# When ``JARVIS_PASSPHRASE_HASH`` is unset (local dev), ``require_token``
# bypasses entirely; tighten by setting the hash.
_active_tokens: set[str] = set()


def _auth_enabled() -> bool:
    """True when ``JARVIS_PASSPHRASE_HASH`` is configured.

    Read at call time (not at import) so tests can monkeypatch the
    settings object without re-importing the module.
    """
    return settings.passphrase_hash is not None


def require_token(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dependency: validate ``Authorization: Bearer <token>``.

    Bypasses entirely when auth is not configured (local-dev parity with
    the existing ``/auth/login`` 503 path). Raises 401 otherwise.
    """
    if not _auth_enabled():
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[len("Bearer ") :].strip()
    if token not in _active_tokens:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


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


@app.get("/personas")
async def personas_endpoint(_: None = Depends(require_token)) -> dict[str, Any]:
    """Return current persona profiles + last-refresh metadata.

    Returns:
        200: dict keyed by persona id with displayName, provider, voice,
             specialtyProfile, lastRefreshTs, refreshCount.
        401: when auth is enabled and the token is missing / invalid.
        503: when the persona registry is not configured
             (``JARVIS_PERSONAS_ENABLED=false``).
    """
    if _persona_registry is None:
        raise HTTPException(status_code=503, detail="personas not enabled")
    out: dict[str, Any] = {}
    for pid in _persona_registry.available_ids():
        p = _persona_registry.get(pid)
        # Read refresh metadata from the persisted personas table when a
        # refresher is configured — in-memory dicts reset on every server
        # restart, so /personas would otherwise report null/0 across
        # process lifecycles even when SQLite has the real values.
        last_refresh_ts: float | None = None
        refresh_count = 0
        if _profile_refresher is not None:
            last_refresh_ts, refresh_count = (
                await _profile_refresher.get_persisted_metadata(pid)
            )
        out[pid] = {
            "displayName": p.display_name,
            "provider": p.provider,
            "voice": p.voice,
            "specialtyProfile": p.specialty_profile,
            "lastRefreshTs": last_refresh_ts,
            "refreshCount": refresh_count,
        }
    return out


@app.get("/git/status", response_model=_GitStatusResponse)
async def git_status(_: None = Depends(require_token)) -> _GitStatusResponse:
    """Return current branch + changed files for the East Code zone.

    ``buildStatus`` is reserved for a future CI poll and is always
    ``None`` for now.

    Returns 503 if no git repository is available at the configured root —
    keeps the rest of the server alive when a deploy forgot to set
    ``JARVIS_GIT_ROOT``.
    """
    if not _git_routes_available():
        raise HTTPException(
            status_code=503,
            detail="git routes unavailable: set JARVIS_GIT_ROOT or run from a repo",
        )
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
async def git_diff(
    path: str = Query(..., min_length=1),
    _: None = Depends(require_token),
) -> _GitDiffResponse:
    """Return a bounded unified diff for ``path`` relative to the git root.

    Path validation:
      * ``400`` on traversal, absolute paths, or ``.git/`` access attempts
      * ``404`` when the path is not in the current changed-files set
        (covers gitignored files, arbitrary tracked files, missing files)
    """
    if not _git_routes_available():
        raise HTTPException(
            status_code=503,
            detail="git routes unavailable: set JARVIS_GIT_ROOT or run from a repo",
        )
    root = _git_root()
    try:
        git_status_mod.safe_resolve(path, root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        lines = git_status_mod.diff(path, root)
    except git_status_mod.PathNotAllowedError as exc:
        # Path passed traversal checks but isn't in the changed-files
        # whitelist — surface as 404 so callers can't distinguish
        # "doesn't exist" from "not allowed to read" by status code.
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    _active_tokens.add(token)
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
async def ws_endpoint(ws: WebSocket, token: str | None = Query(default=None)) -> None:
    # Browsers can't send custom headers on the WS upgrade — accept the
    # bearer token via ?token= query string. Validate BEFORE accepting so
    # a bad token never sees an open socket.
    if _auth_enabled() and (token is None or token not in _active_tokens):
        # 1008 = policy violation. The browser observes this as a normal
        # close with the matching code (better than a TCP reset).
        await ws.close(code=1008)
        return
    await ws.accept()
    # Per-connection pipeline instances. Construction is cheap — heavy
    # state (Whisper model, Anthropic client) lives in module-level
    # singletons inside the wrappers.
    dialog_manager: DialogManager | None = None
    if (
        _persona_registry is not None
        and _dispatcher is not None
        and _multi_voice_tts is not None
        and _llm_factory is not None
    ):
        # Lazy import kept inside the personas_enabled branch so the
        # dormancy regression guard keeps passing with the flag off.
        from .dialog.manager import DialogManager  # noqa: PLC0415

        dialog_manager = DialogManager(
            registry=_persona_registry,
            dispatcher=_dispatcher,
            llm_factory=_llm_factory,
            tts=_multi_voice_tts,
            codex_agent=_codex_agent,
            feedback=_feedback_logger,
            refresher=_profile_refresher,
            refresh_every=settings.persona_refresh_turns,
        )
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
        dialog_manager=dialog_manager,
        codex_agent=_codex_agent,
        refresher=_profile_refresher,
    )
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    finally:
        await session.cleanup()
        with contextlib.suppress(Exception):
            await ws.close()

# Backend Streaming Server (spec-02 · Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `server/` Python package: a FastAPI WebSocket server that implements the protocol from the umbrella architecture §4.1 verbatim, driven by **mock pipelines** that emit canned events on realistic timings. End state: spec-03 can integrate the browser frontend against this server with no further backend work; only the mock pipelines need to be swapped for real ones in Phase 2 (future spec-02b).

**Architecture:** FastAPI + websockets (ASGI) server. Per-connection `Session` orchestrates STT → LLM → TTS pipelines via async generators. Binary frames carry PCM audio in/out (length-prefixed audioId). Mock pipelines share the **same async interface** as the eventual real pipelines so Phase 2 swap is mechanical.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, websockets, pydantic, pydantic-settings, pytest, pytest-asyncio, ruff, mypy, `httpx[ws]` for tests, `numpy` for the binary framing helpers (zero-cost dep).

**Spec:** `docs/superpowers/specs/2026-05-08-backend-streaming-design.md`

**Worktree:** `.worktrees/spec-02-backend-streaming` (created at start of Task 1)

---

## Task index

1. Create worktree + Python project scaffold
2. Dev tooling (ruff, mypy, pytest config) + sanity test
3. Protocol message types (pydantic) with TDD
4. Binary frame encode/decode with TDD
5. Sentence splitter with TDD
6. Pipeline interfaces + mock scenarios
7. Mock STT pipeline
8. Mock LLM pipeline
9. Mock TTS pipeline
10. Session orchestrator skeleton + state with TDD (mock pipelines)
11. Session: text input → reply flow
12. Session: audio input → reply flow
13. Session: interrupt + cancellation semantics
14. FastAPI app + WS route + lifespan
15. WS integration test (httpx async client)
16. CLI test client (text mode + REPL)
17. CLI test client: audio-input simulation
18. Final acceptance run (lint, mypy, pytest, manual smoke)
19. README + merge prep

---

## Task 1: Create worktree + Python project scaffold

**Files:**
- Create: `.worktrees/spec-02-backend-streaming/` (worktree on new branch `spec-02-backend-streaming`)
- Create: `server/pyproject.toml`, `server/server/__init__.py`, `server/.gitignore`, `server/.python-version`

- [ ] **Step 1: Create the worktree**

```bash
cd /home/max/perso/jarvis
git worktree add -b spec-02-backend-streaming .worktrees/spec-02-backend-streaming main
cd .worktrees/spec-02-backend-streaming
mkdir -p server/server server/tests/integration
```

- [ ] **Step 2: Create `server/pyproject.toml`**

```toml
[project]
name = "jarvis-server"
version = "0.0.1"
description = "Jarvis WebSocket server (spec-02 Phase 1, mock pipelines)"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "websockets>=13",
  "pydantic>=2.9",
  "pydantic-settings>=2.5",
  "numpy>=1.26",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "websockets>=13",
  "ruff>=0.7",
  "mypy>=1.13",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["server*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = ["requires_models: tests that need real Whisper/LLM/OpenVoice (Phase 2)"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "ASYNC", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["server"]
```

- [ ] **Step 3: Create `server/.gitignore`**

```gitignore
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
venv/
*.egg-info/
dist/
build/
.env

# Re-include package files (root .gitignore globally excludes "package*")
!package.json
```

- [ ] **Step 4: Create `server/server/__init__.py`**

```python
"""Jarvis backend WebSocket server (spec-02 Phase 1, mock pipelines)."""

__version__ = "0.0.1"
```

- [ ] **Step 5: Create venv and install**

```bash
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Verify with:

```bash
python -c "import fastapi, uvicorn, websockets, pydantic; print('ok')"
```

Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add server/
git commit -m "chore(server): scaffold Python package + dev deps"
```

---

## Task 2: Dev tooling sanity test

**Files:**
- Create: `server/tests/__init__.py`
- Create: `server/tests/test_sanity.py`

- [ ] **Step 1: Create `server/tests/__init__.py`** (empty file)

```python
```

- [ ] **Step 2: Create `server/tests/test_sanity.py`**

```python
"""Toolchain sanity check."""

import server


def test_package_importable() -> None:
    assert server.__version__ == "0.0.1"


def test_pytest_asyncio_works() -> None:
    """Ensures pytest-asyncio in auto mode is loaded."""
    import asyncio
    assert asyncio.get_event_loop_policy() is not None
```

- [ ] **Step 3: Run all gates**

```bash
. .venv/bin/activate
pytest -q
ruff check .
mypy
```

Expected: all three exit 0.

- [ ] **Step 4: Commit**

```bash
git add server/tests
git commit -m "chore(server): pytest sanity + ruff/mypy clean"
```

---

## Task 3: Protocol message types with TDD

**Files:**
- Create: `server/server/protocol.py`
- Create: `server/tests/test_protocol.py`

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_protocol.py`:

```python
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
    out = encode_server(ServerMessage.tts_sentence(text="ok.", audio_id="s0-abc12", sample_rate=24000))
    assert '"audioId":"s0-abc12"' in out
    assert '"sampleRate":24000' in out


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
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_protocol.py -q
```

Expected: collection error (`server.protocol` not importable).

- [ ] **Step 3: Implement `server/server/protocol.py`**

```python
"""WS JSON protocol — pydantic-modeled messages with discriminated union."""

from __future__ import annotations

import json
import time
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, ValidationError


# ─── Client → Server ──────────────────────────────────────────────────────


class _Base(BaseModel):
    model_config = {"extra": "forbid"}


class Hello(_Base):
    type: Literal["hello"]
    clientVersion: str
    capabilities: dict[str, object] | None = None


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


ClientMessage = Annotated[
    Union[Hello, AudioStart, AudioEnd, TextIn, Interrupt],
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
    def ready() -> dict[str, object]:
        return {"type": "ready"}

    @staticmethod
    def stt_partial(text: str) -> dict[str, object]:
        return {"type": "stt.partial", "text": text}

    @staticmethod
    def stt_final(text: str) -> dict[str, object]:
        return {"type": "stt.final", "text": text}

    @staticmethod
    def llm_token(delta: str) -> dict[str, object]:
        return {"type": "llm.token", "delta": delta}

    @staticmethod
    def llm_end() -> dict[str, object]:
        return {"type": "llm.end"}

    @staticmethod
    def tts_sentence(text: str, audio_id: str, sample_rate: int) -> dict[str, object]:
        return {
            "type": "tts.sentence",
            "text": text,
            "audioId": audio_id,
            "sampleRate": sample_rate,
        }

    @staticmethod
    def tts_end(audio_id: str) -> dict[str, object]:
        return {"type": "tts.end", "audioId": audio_id}

    @staticmethod
    def error(code: str, message: str) -> dict[str, object]:
        return {"type": "error", "code": code, "message": message}

    @staticmethod
    def telemetry(level: str, message: str, ts: float | None = None) -> dict[str, object]:
        return {
            "type": "telemetry",
            "ts": ts if ts is not None else time.time(),
            "level": level,
            "message": message,
        }


def encode_server(msg: dict[str, object]) -> str:
    return json.dumps(msg, separators=(",", ":"))
```

- [ ] **Step 4: Run, verify pass**

```bash
pytest tests/test_protocol.py -q
```

Expected: 12/12 PASS.

- [ ] **Step 5: Commit**

```bash
git add server/server/protocol.py server/tests/test_protocol.py
git commit -m "feat(server): protocol message types + JSON codec"
```

---

## Task 4: Binary frame encode/decode with TDD

**Files:**
- Create: `server/server/audio.py`
- Create: `server/tests/test_audio.py`

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_audio.py`:

```python
"""Tests for the binary frame format (spec §4.4)."""

import pytest

from server.audio import (
    KIND_CLIENT_MIC,
    KIND_SERVER_TTS,
    decode_audio_frame,
    encode_tts_chunk,
    encode_mic_chunk,
)


def test_round_trip_tts_chunk() -> None:
    pcm = b"\x01\x02\x03\x04\x05\x06"
    frame = encode_tts_chunk("s0-abc12", pcm)
    decoded = decode_audio_frame(frame)
    assert decoded.kind == KIND_SERVER_TTS
    assert decoded.audio_id == "s0-abc12"
    assert decoded.samples == pcm


def test_round_trip_mic_chunk() -> None:
    pcm = b"\x10" * 320  # 10 ms @ 16 kHz mono int16
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
        decode_audio_frame(b"\x02\x05ab")  # claims 5-byte id, gives 2


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
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_audio.py -q
```

Expected: collection error.

- [ ] **Step 3: Implement `server/server/audio.py`**

```python
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
```

- [ ] **Step 4: Run, verify pass**

```bash
pytest tests/test_audio.py -q
```

Expected: 8/8 PASS.

- [ ] **Step 5: Commit**

```bash
git add server/server/audio.py server/tests/test_audio.py
git commit -m "feat(server): binary audio frame codec (kind + idLen-prefixed)"
```

---

## Task 5: Sentence splitter with TDD

**Files:**
- Create: `server/server/pipelines/__init__.py`
- Create: `server/server/pipelines/sentence_split.py`
- Create: `server/tests/test_sentence_split.py`

- [ ] **Step 1: Create `server/server/pipelines/__init__.py`** (empty)

```python
```

- [ ] **Step 2: Write failing tests**

Create `server/tests/test_sentence_split.py`:

```python
"""Tests for the streaming sentence splitter."""

from collections.abc import AsyncIterator

import pytest

from server.pipelines.sentence_split import split_sentences_stream


async def _stream(parts: list[str]) -> AsyncIterator[str]:
    for p in parts:
        yield p


@pytest.mark.asyncio
async def test_single_sentence() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Hello world."]))]
    assert out == ["Hello world."]


@pytest.mark.asyncio
async def test_two_sentences_split_on_period_space() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Hi. ", "There."]))]
    assert out == ["Hi.", "There."]


@pytest.mark.asyncio
async def test_question_and_exclamation() -> None:
    out = [s async for s in split_sentences_stream(_stream(["What? ", "Wow!"]))]
    assert out == ["What?", "Wow!"]


@pytest.mark.asyncio
async def test_no_terminal_punctuation_flushes_at_end() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Half a sentence"]))]
    assert out == ["Half a sentence"]


@pytest.mark.asyncio
async def test_abbreviation_does_not_split() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Mr. Smith arrived. ", "Done."]))]
    assert out == ["Mr. Smith arrived.", "Done."]


@pytest.mark.asyncio
async def test_ellipsis_treated_as_one() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Hmm... ", "Yes."]))]
    assert out == ["Hmm...", "Yes."]


@pytest.mark.asyncio
async def test_chunks_arriving_mid_word() -> None:
    out = [s async for s in split_sentences_stream(_stream(["He", "llo. ", "Wo", "rld."]))]
    assert out == ["Hello.", "World."]


@pytest.mark.asyncio
async def test_empty_input() -> None:
    out = [s async for s in split_sentences_stream(_stream([]))]
    assert out == []


@pytest.mark.asyncio
async def test_whitespace_only_does_not_emit() -> None:
    out = [s async for s in split_sentences_stream(_stream(["   ", "\n"]))]
    assert out == []


@pytest.mark.asyncio
async def test_trailing_whitespace_trimmed() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Hi.    "]))]
    assert out == ["Hi."]
```

- [ ] **Step 3: Run, verify fail**

```bash
pytest tests/test_sentence_split.py -q
```

Expected: collection error.

- [ ] **Step 4: Implement `server/server/pipelines/sentence_split.py`**

```python
"""Streaming sentence splitter — buffers tokens, emits complete sentences."""

from __future__ import annotations

import re
from collections.abc import AsyncIterable, AsyncIterator

# Abbreviations that look like sentence-enders but aren't.
_ABBREVIATIONS = frozenset({
    "mr", "mrs", "ms", "dr", "mt", "st", "jr", "sr",
    "vs", "etc", "ie", "eg", "no", "fig", "vol",
})

# Match "<text>[.!?]+" optionally followed by whitespace.
_BOUNDARY = re.compile(r"^(.*?[.!?]+)(\s+|$)", re.DOTALL)


def _is_real_boundary(buffer: str, end_idx: int) -> bool:
    """End_idx points to the position right after a [.!?]+ run."""
    # Pull the word immediately before the punctuation.
    j = end_idx - 1
    while j >= 0 and buffer[j] in ".!?":
        j -= 1
    word_end = j + 1
    word_start = word_end
    while word_start > 0 and buffer[word_start - 1].isalnum():
        word_start -= 1
    word = buffer[word_start:word_end].lower()
    if word in _ABBREVIATIONS:
        return False
    return True


async def split_sentences_stream(tokens: AsyncIterable[str]) -> AsyncIterator[str]:
    """Consume token deltas, yield complete sentences as boundaries are crossed.

    A boundary is `[.!?]+` followed by whitespace OR end of stream.
    Abbreviations followed by `.` do not count as boundaries.
    """
    buf = ""
    async for chunk in tokens:
        buf += chunk
        while True:
            m = _BOUNDARY.match(buf)
            if not m:
                break
            sentence = m.group(1)
            # Determine the position of the punctuation run end inside `buf`.
            punct_end = len(sentence)
            if not _is_real_boundary(buf, punct_end):
                # Move past this false boundary; keep accumulating.
                # We do this by stripping the matched sentence + trailing whitespace
                # then re-prepending without the trailing space, so the loop continues.
                # But we cannot mutate the matched piece; simpler: break out and wait
                # for more text.
                break
            buf = buf[m.end() :]
            yield sentence.strip()
    tail = buf.strip()
    if tail:
        yield tail
```

- [ ] **Step 5: Run, verify pass**

```bash
pytest tests/test_sentence_split.py -q
```

Expected: 10/10 PASS.

- [ ] **Step 6: Commit**

```bash
git add server/server/pipelines/sentence_split.py server/server/pipelines/__init__.py server/tests/test_sentence_split.py
git commit -m "feat(server): streaming sentence splitter with abbreviation skip-list"
```

---

## Task 6: Pipeline interfaces + scenarios

**Files:**
- Create: `server/server/pipelines/interfaces.py`
- Create: `server/server/pipelines/scenarios.py`

- [ ] **Step 1: Create `server/server/pipelines/interfaces.py`**

```python
"""Async pipeline interfaces — implemented by both mock and (future) real pipelines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class STT(ABC):
    """Speech-to-text pipeline."""

    @abstractmethod
    async def partials(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Yield interim transcriptions as audio is consumed."""

    @abstractmethod
    async def final(self, audio: AsyncIterator[bytes]) -> str:
        """Return the final transcription once audio is exhausted."""


class LLM(ABC):
    """Large language model client."""

    @abstractmethod
    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
    ) -> AsyncIterator[str]:
        """Yield token deltas. Caller appends user/assistant to history."""


class TTS(ABC):
    """Text-to-speech pipeline.

    Phase 1 mock skips audio synthesis: synthesize() returns an empty bytes
    AsyncIterator. Phase 2 (real OpenVoice) yields PCM Int16 LE chunks.
    """

    @abstractmethod
    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        """Yield PCM Int16 LE chunks at the rate declared by sample_rate()."""

    @abstractmethod
    def sample_rate(self) -> int:
        ...
```

- [ ] **Step 2: Create `server/server/pipelines/scenarios.py`**

```python
"""Canned conversation scenarios for Phase 1 mock pipelines.

The mock LLM picks one based on coarse keyword matching of the user's text;
falls back to a default on no match.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Scenario:
    keywords: tuple[str, ...]   # any match → this scenario
    transcription: str          # what the mock STT "hears" if audio path used
    reply: str                  # what the mock LLM streams back


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        keywords=("brief", "today", "agenda"),
        transcription="Brief me on today.",
        reply=(
            "Two interviews on your calendar. "
            "The playtesting deck is ready for review. "
            "Three slides flagged for your attention. "
            "Otherwise, your morning is clear."
        ),
    ),
    Scenario(
        keywords=("research", "notes", "summarize", "summary"),
        transcription="Summarize yesterday's research notes.",
        reply=(
            "Eight key insights synthesized. "
            "The strongest pattern: testers consistently abandon at the second tutorial gate. "
            "I drafted a one-paragraph summary in your inbox."
        ),
    ),
    Scenario(
        keywords=("playtest", "review", "deck"),
        transcription="What's the status of the playtest review?",
        reply=(
            "Slides ready. "
            "Three need your review before sending. "
            "The remaining content is approved by Harsh."
        ),
    ),
    Scenario(
        keywords=("cancel", "meeting"),
        transcription="Cancel my eleven o'clock.",
        reply="Done. Apologies sent. Calendar slot reopened. Your morning is now fully clear.",
    ),
    Scenario(
        keywords=("inbox", "email", "urgent"),
        transcription="Anything urgent in my inbox?",
        reply=(
            "One. The grant deadline moved up by a week. "
            "I drafted a response asking for clarification. "
            "Want me to send it?"
        ),
    ),
)


DEFAULT_REPLY = "I'm not sure I understood, but I'm listening."


def pick_scenario(user_text: str) -> Scenario | None:
    """Return the first scenario whose keyword appears in `user_text` (case-insensitive)."""
    needle = user_text.lower()
    for s in SCENARIOS:
        if any(kw in needle for kw in s.keywords):
            return s
    return None
```

- [ ] **Step 3: Lint + typecheck**

```bash
ruff check . && mypy
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add server/server/pipelines/interfaces.py server/server/pipelines/scenarios.py
git commit -m "feat(server): pipeline interfaces + canned conversation scenarios"
```

---

## Task 7: Mock STT pipeline

**Files:**
- Create: `server/server/pipelines/mock_stt.py`
- Create: `server/tests/test_mock_stt.py`

- [ ] **Step 1: Failing test**

Create `server/tests/test_mock_stt.py`:

```python
"""Tests for the Phase 1 mock STT."""

from collections.abc import AsyncIterator

import pytest

from server.pipelines.mock_stt import MockSTT


async def _audio(chunks: list[bytes]) -> AsyncIterator[bytes]:
    for c in chunks:
        yield c


@pytest.mark.asyncio
async def test_final_returns_canned_text_for_brief_keyword() -> None:
    """The mock STT picks a scenario based on... hmm, it doesn't see text.

    The contract: STT consumes audio bytes and returns a transcription.
    For Phase 1, the bytes carry no real signal. So the mock returns a
    deterministic default; scenario keying happens at the LLM layer based
    on the final transcription string. The mock STT therefore returns a
    fixed string OR a hint encoded into the *number* of audio bytes.

    The simplest contract: caller can override the canned transcription
    via constructor; tests use that.
    """
    stt = MockSTT(canned_final="Brief me on today.")
    out = await stt.final(_audio([b"\x00" * 1024]))
    assert out == "Brief me on today."


@pytest.mark.asyncio
async def test_partials_emit_progressive_prefixes_during_audio() -> None:
    stt = MockSTT(canned_final="Hello world how are you")
    seen: list[str] = []
    async for p in stt.partials(_audio([b"\x00" * 1024 for _ in range(5)])):
        seen.append(p)
    # Should emit at least one partial; each is a non-decreasing prefix.
    assert len(seen) >= 1
    assert all(seen[i].startswith(seen[i - 1]) or seen[i] == seen[i - 1] for i in range(1, len(seen)))


@pytest.mark.asyncio
async def test_default_canned_when_unset() -> None:
    stt = MockSTT()
    out = await stt.final(_audio([b""]))
    assert isinstance(out, str)
    assert len(out) > 0
```

- [ ] **Step 2: Implement `server/server/pipelines/mock_stt.py`**

```python
"""Phase 1 mock STT — emits progressive prefixes; final = canned text."""

from __future__ import annotations

from collections.abc import AsyncIterator

from .interfaces import STT


class MockSTT(STT):
    def __init__(self, canned_final: str = "Brief me on today.") -> None:
        self._canned = canned_final

    async def partials(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        words = self._canned.split()
        emitted = 0
        async for _chunk in audio:
            # Emit one more word per consumed chunk, capped at len(words).
            emitted = min(emitted + 1, len(words))
            yield " ".join(words[:emitted])

    async def final(self, audio: AsyncIterator[bytes]) -> str:
        # Drain (we don't analyze the bytes in Phase 1).
        async for _ in audio:
            pass
        return self._canned

    def set_canned(self, text: str) -> None:
        self._canned = text
```

- [ ] **Step 3: Run, verify pass**

```bash
pytest tests/test_mock_stt.py -q
```

Expected: 3/3 PASS.

- [ ] **Step 4: Commit**

```bash
git add server/server/pipelines/mock_stt.py server/tests/test_mock_stt.py
git commit -m "feat(server): mock STT pipeline (Phase 1)"
```

---

## Task 8: Mock LLM pipeline

**Files:**
- Create: `server/server/pipelines/mock_llm.py`
- Create: `server/tests/test_mock_llm.py`

- [ ] **Step 1: Failing test**

Create `server/tests/test_mock_llm.py`:

```python
"""Tests for the Phase 1 mock LLM."""

import pytest

from server.pipelines.mock_llm import MockLLM


@pytest.mark.asyncio
async def test_picks_scenario_by_keyword_and_streams_reply() -> None:
    llm = MockLLM(token_delay_ms=0)
    history: list[dict[str, str]] = []
    seen = ""
    async for delta in llm.stream(history, "Brief me on today"):
        seen += delta
    assert "interview" in seen.lower() or "morning" in seen.lower()


@pytest.mark.asyncio
async def test_falls_back_to_default_on_no_keyword_match() -> None:
    llm = MockLLM(token_delay_ms=0)
    seen = ""
    async for delta in llm.stream([], "qzx"):
        seen += delta
    assert "not sure" in seen.lower() or "listening" in seen.lower()


@pytest.mark.asyncio
async def test_streams_in_multiple_deltas() -> None:
    llm = MockLLM(token_delay_ms=0)
    deltas = [d async for d in llm.stream([], "Brief me")]
    assert len(deltas) > 1


@pytest.mark.asyncio
async def test_history_is_not_mutated_by_llm() -> None:
    """Caller is responsible for appending; LLM treats history as read-only."""
    llm = MockLLM(token_delay_ms=0)
    history = [{"role": "user", "content": "hi"}]
    snapshot = list(history)
    _ = [d async for d in llm.stream(history, "Brief me")]
    assert history == snapshot
```

- [ ] **Step 2: Implement `server/server/pipelines/mock_llm.py`**

```python
"""Phase 1 mock LLM — keyword-routed, paced token streaming."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from random import Random

from .interfaces import LLM
from .scenarios import DEFAULT_REPLY, pick_scenario


class MockLLM(LLM):
    def __init__(self, token_delay_ms: int = 33, seed: int | None = None) -> None:
        self._delay = token_delay_ms / 1000.0
        self._rand = Random(seed)

    async def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
    ) -> AsyncIterator[str]:
        scenario = pick_scenario(user_text)
        reply = scenario.reply if scenario else DEFAULT_REPLY
        i = 0
        while i < len(reply):
            step = 3 + self._rand.randint(0, 3)
            j = min(i + step, len(reply))
            yield reply[i:j]
            i = j
            if self._delay:
                await asyncio.sleep(self._delay)
```

- [ ] **Step 3: Run, verify pass**

```bash
pytest tests/test_mock_llm.py -q
```

Expected: 4/4 PASS.

- [ ] **Step 4: Commit**

```bash
git add server/server/pipelines/mock_llm.py server/tests/test_mock_llm.py
git commit -m "feat(server): mock LLM pipeline with scenario routing (Phase 1)"
```

---

## Task 9: Mock TTS pipeline

**Files:**
- Create: `server/server/pipelines/mock_tts.py`
- Create: `server/tests/test_mock_tts.py`

- [ ] **Step 1: Failing test**

Create `server/tests/test_mock_tts.py`:

```python
"""Tests for the Phase 1 mock TTS."""

import pytest

from server.pipelines.mock_tts import MockTTS


@pytest.mark.asyncio
async def test_synthesize_yields_no_audio_in_phase_1() -> None:
    """Phase 1 contract: no binary audio chunks are emitted (spec §11.A.11)."""
    tts = MockTTS()
    chunks = [c async for c in tts.synthesize("hello.", "s0-abc12")]
    assert chunks == []


def test_sample_rate_default_is_24000() -> None:
    assert MockTTS().sample_rate() == 24000
```

- [ ] **Step 2: Implement `server/server/pipelines/mock_tts.py`**

```python
"""Phase 1 mock TTS — emits no audio chunks (sentence/end markers handled by Session)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from .interfaces import TTS


class MockTTS(TTS):
    def __init__(self, sample_rate: int = 24000) -> None:
        self._sample_rate = sample_rate

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        # Phase 1: no audio synthesized. Phase 2 will yield PCM Int16 LE chunks.
        # The async-generator function shape must yield zero or more times.
        return
        yield  # pragma: no cover  # makes this an async generator

    def sample_rate(self) -> int:
        return self._sample_rate
```

- [ ] **Step 3: Run, verify pass**

```bash
pytest tests/test_mock_tts.py -q
```

Expected: 2/2 PASS.

- [ ] **Step 4: Commit**

```bash
git add server/server/pipelines/mock_tts.py server/tests/test_mock_tts.py
git commit -m "feat(server): mock TTS pipeline — no audio chunks in Phase 1"
```

---

## Task 10: Session orchestrator skeleton + state, with TDD

**Files:**
- Create: `server/server/session.py`
- Create: `server/tests/test_session.py`

- [ ] **Step 1: Failing test (skeleton only — text input flow validated in Task 11)**

Create `server/tests/test_session.py`:

```python
"""Tests for the per-connection Session orchestrator.

Uses an in-memory FakeWS that records emitted JSON and binary frames so
the protocol can be exercised without a real WebSocket server.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from server.pipelines.mock_llm import MockLLM
from server.pipelines.mock_stt import MockSTT
from server.pipelines.mock_tts import MockTTS
from server.session import Session


class FakeWS:
    def __init__(self) -> None:
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []
        self._inbound: asyncio.Queue[dict[str, Any] | bytes | None] = asyncio.Queue()

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def receive(self) -> dict[str, Any]:
        item = await self._inbound.get()
        if item is None:
            return {"type": "websocket.disconnect"}
        if isinstance(item, bytes):
            return {"type": "websocket.receive", "bytes": item}
        return {"type": "websocket.receive", "text": json.dumps(item)}

    async def feed_text(self, msg: dict[str, Any]) -> None:
        await self._inbound.put(msg)

    async def feed_bytes(self, b: bytes) -> None:
        await self._inbound.put(b)

    async def close_inbound(self) -> None:
        await self._inbound.put(None)


@pytest.fixture
def fake_ws() -> FakeWS:
    return FakeWS()


@pytest.fixture
def session(fake_ws: FakeWS) -> Session:
    return Session(
        ws=fake_ws,
        stt=MockSTT(),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
    )


@pytest.mark.asyncio
async def test_emit_ready_on_run_start(session: Session, fake_ws: FakeWS) -> None:
    task = asyncio.create_task(session.run())
    await asyncio.sleep(0.05)
    await fake_ws.close_inbound()
    await task
    types = [json.loads(t).get("type") for t in fake_ws.sent_text]
    assert "ready" in types
```

- [ ] **Step 2: Implement skeleton `server/server/session.py`**

```python
"""Per-connection orchestrator. Receives WS messages, drives pipelines,
emits protocol events. Phase 1 uses mock pipelines; the orchestrator
itself is real and will be Phase-2-ready.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Protocol

from .audio import KIND_CLIENT_MIC, decode_audio_frame, encode_tts_chunk
from .pipelines.interfaces import LLM, STT, TTS
from .pipelines.sentence_split import split_sentences_stream
from .protocol import (
    AudioEnd,
    AudioStart,
    ClientMessage,
    Hello,
    Interrupt,
    ServerMessage,
    TextIn,
    decode_client,
    encode_server,
)

log = logging.getLogger(__name__)


class _WS(Protocol):
    async def send_text(self, data: str) -> None: ...
    async def send_bytes(self, data: bytes) -> None: ...
    async def receive(self) -> dict[str, Any]: ...


_AUDIO_ID_RANDS = "abcdefghijklmnopqrstuvwxyz0123456789"


def _audio_id(idx: int) -> str:
    import secrets
    rand = "".join(secrets.choice(_AUDIO_ID_RANDS) for _ in range(6))
    return f"s{idx}-{rand}"


class Session:
    def __init__(self, ws: _WS, stt: STT, llm: LLM, tts: TTS, history_cap: int = 20) -> None:
        self._ws = ws
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._history: list[dict[str, str]] = []
        self._history_cap = history_cap
        self._send_q: asyncio.Queue[tuple[str, str | bytes]] = asyncio.Queue(maxsize=256)
        self._sender_task: asyncio.Task[None] | None = None
        self._turn_task: asyncio.Task[None] | None = None
        self._mic_buf: list[bytes] = []
        self._mic_active = False
        self._closing = False
        self._llm_ended = False
        self._open_audio_ids: set[str] = set()

    # ─── public lifecycle ─────────────────────────────────────────────

    async def run(self) -> None:
        self._sender_task = asyncio.create_task(self._sender_loop())
        await self._enqueue_json(ServerMessage.ready())
        try:
            while not self._closing:
                ev = await self._ws.receive()
                etype = ev.get("type")
                if etype == "websocket.disconnect":
                    break
                if etype != "websocket.receive":
                    continue
                if "bytes" in ev and ev["bytes"] is not None:
                    await self._handle_binary(ev["bytes"])
                elif "text" in ev and ev["text"] is not None:
                    await self._handle_text(ev["text"])
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        self._closing = True
        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
            try:
                await self._turn_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._sender_task and not self._sender_task.done():
            await self._send_q.put(("__stop__", ""))
            try:
                await self._sender_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    # ─── inbound dispatch ─────────────────────────────────────────────

    async def _handle_text(self, raw: str) -> None:
        try:
            msg = decode_client(raw)
        except ValueError as e:
            await self._enqueue_json(ServerMessage.error("protocol.bad_message", str(e)))
            return
        match msg:
            case Hello():
                # No-op for Phase 1.
                pass
            case AudioStart():
                self._mic_buf = []
                self._mic_active = True
            case AudioEnd():
                if not self._mic_active:
                    await self._enqueue_json(
                        ServerMessage.error("protocol.audio_unframed", "audio.end without audio.start")
                    )
                    return
                self._mic_active = False
                self._start_turn(audio=True)
            case TextIn(content=text):
                self._start_turn(text=text)
            case Interrupt():
                await self._do_interrupt()

    async def _handle_binary(self, payload: bytes) -> None:
        try:
            frame = decode_audio_frame(payload)
        except ValueError as e:
            await self._enqueue_json(ServerMessage.error("protocol.bad_frame", str(e)))
            return
        if frame.kind != KIND_CLIENT_MIC:
            await self._enqueue_json(
                ServerMessage.error("protocol.bad_frame", "expected client mic kind")
            )
            return
        if not self._mic_active:
            await self._enqueue_json(
                ServerMessage.error("protocol.audio_unframed", "mic chunk before audio.start")
            )
            return
        self._mic_buf.append(frame.samples)

    # ─── turn machinery ───────────────────────────────────────────────

    def _start_turn(self, *, text: str | None = None, audio: bool = False) -> None:
        if self._turn_task and not self._turn_task.done():
            # New turn while previous in-flight: cancel it.
            self._turn_task.cancel()
        self._llm_ended = False
        self._open_audio_ids.clear()
        self._turn_task = asyncio.create_task(self._run_turn(text=text, audio=audio))

    async def _run_turn(self, *, text: str | None, audio: bool) -> None:
        try:
            user_text = await self._do_stt(text=text, audio=audio)
            await self._do_llm_and_tts(user_text)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("turn failed")
            await self._enqueue_json(ServerMessage.error("session.turn_failed", str(e)))

    async def _do_stt(self, *, text: str | None, audio: bool) -> str:
        if text is not None:
            await self._enqueue_json(ServerMessage.stt_final(text))
            return text
        # audio path
        async def _audio_iter() -> AsyncIterator[bytes]:
            for c in self._mic_buf:
                yield c
        # Partials
        async for partial in self._stt.partials(_audio_iter()):
            await self._enqueue_json(ServerMessage.stt_partial(partial))
        final = await self._stt.final(_audio_iter())
        await self._enqueue_json(ServerMessage.stt_final(final))
        return final

    async def _do_llm_and_tts(self, user_text: str) -> None:
        # Append user turn now; assistant turn appended at the end.
        self._history.append({"role": "user", "content": user_text})

        # Tee the LLM stream: one branch emits llm.token, another feeds the splitter.
        llm_iter = self._llm.stream(self._history, user_text)
        token_q: asyncio.Queue[str | None] = asyncio.Queue()
        sentence_q: asyncio.Queue[str | None] = asyncio.Queue()

        assistant_buf: list[str] = []

        async def fanout() -> None:
            try:
                async for delta in llm_iter:
                    assistant_buf.append(delta)
                    await self._enqueue_json(ServerMessage.llm_token(delta))
                    await token_q.put(delta)
            finally:
                await token_q.put(None)

        async def consume_tokens_to_sentences() -> None:
            async def _gen() -> AsyncIterator[str]:
                while True:
                    item = await token_q.get()
                    if item is None:
                        return
                    yield item
            async for sent in split_sentences_stream(_gen()):
                await sentence_q.put(sent)
            await sentence_q.put(None)

        async def speak_sentences() -> None:
            idx = 0
            while True:
                sent = await sentence_q.get()
                if sent is None:
                    return
                aid = _audio_id(idx)
                idx += 1
                self._open_audio_ids.add(aid)
                await self._enqueue_json(
                    ServerMessage.tts_sentence(text=sent, audio_id=aid, sample_rate=self._tts.sample_rate())
                )
                async for pcm in self._tts.synthesize(sent, aid):
                    await self._enqueue_bytes(encode_tts_chunk(aid, pcm))
                await self._enqueue_json(ServerMessage.tts_end(aid))
                self._open_audio_ids.discard(aid)

        await asyncio.gather(fanout(), consume_tokens_to_sentences(), speak_sentences())

        if not self._llm_ended:
            self._llm_ended = True
            await self._enqueue_json(ServerMessage.llm_end())

        full = "".join(assistant_buf)
        if full:
            self._history.append({"role": "assistant", "content": full})
        # Trim
        if len(self._history) > self._history_cap:
            self._history = self._history[-self._history_cap :]

    async def _do_interrupt(self) -> None:
        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
            try:
                await self._turn_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        # Idempotent llm.end
        if not self._llm_ended:
            self._llm_ended = True
            await self._enqueue_json(ServerMessage.llm_end())
        self._open_audio_ids.clear()

    # ─── outbound queue ───────────────────────────────────────────────

    async def _enqueue_json(self, msg: dict[str, Any]) -> None:
        try:
            self._send_q.put_nowait(("text", encode_server(msg)))
        except asyncio.QueueFull:
            log.warning("send queue overflow, dropping JSON message: %s", msg.get("type"))

    async def _enqueue_bytes(self, payload: bytes) -> None:
        try:
            self._send_q.put_nowait(("bytes", payload))
        except asyncio.QueueFull:
            log.warning("send queue overflow, dropping audio chunk (%d bytes)", len(payload))

    async def _sender_loop(self) -> None:
        while True:
            kind, payload = await self._send_q.get()
            if kind == "__stop__":
                return
            try:
                if kind == "text" and isinstance(payload, str):
                    await self._ws.send_text(payload)
                elif kind == "bytes" and isinstance(payload, (bytes, bytearray)):
                    await self._ws.send_bytes(bytes(payload))
            except Exception:  # noqa: BLE001
                log.exception("send failed")
                return
```

- [ ] **Step 3: Run, verify pass**

```bash
pytest tests/test_session.py -q
```

Expected: 1/1 PASS.

- [ ] **Step 4: Commit**

```bash
git add server/server/session.py server/tests/test_session.py
git commit -m "feat(server): Session orchestrator skeleton + ready emit on run"
```

---

## Task 11: Session text-input flow

**Files:**
- Modify: `server/tests/test_session.py`

- [ ] **Step 1: Add text-flow tests**

Append to `server/tests/test_session.py`:

```python
async def _drain_until(fake_ws: FakeWS, type_: str, timeout: float = 2.0) -> list[dict[str, Any]]:
    """Wait until the JSON event of the given type has been emitted."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        msgs = [json.loads(t) for t in fake_ws.sent_text]
        if any(m.get("type") == type_ for m in msgs):
            return msgs
        await asyncio.sleep(0.02)
    raise TimeoutError(f"never saw {type_}; saw: {[json.loads(t).get('type') for t in fake_ws.sent_text]}")


@pytest.mark.asyncio
async def test_text_input_drives_full_protocol(fake_ws: FakeWS, session: Session) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "text", "content": "Brief me on today"})
    # Wait for llm.end (turn complete)
    await _drain_until(fake_ws, "llm.end", timeout=3.0)
    await fake_ws.close_inbound()
    await task

    types = [json.loads(t)["type"] for t in fake_ws.sent_text]
    assert types[0] == "ready"
    assert "stt.final" in types
    assert "llm.token" in types
    assert "llm.end" in types
    assert "tts.sentence" in types
    assert "tts.end" in types

    # Sentence count: 4 sentences in the "brief" reply.
    sentences = [json.loads(t) for t in fake_ws.sent_text if json.loads(t)["type"] == "tts.sentence"]
    assert len(sentences) == 4
    audio_ids = [s["audioId"] for s in sentences]
    assert len(set(audio_ids)) == 4  # unique
    assert all(aid.startswith("s") and "-" in aid for aid in audio_ids)


@pytest.mark.asyncio
async def test_text_input_no_audio_chunks_in_phase_1(fake_ws: FakeWS, session: Session) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "text", "content": "Brief me"})
    await _drain_until(fake_ws, "llm.end", timeout=3.0)
    await fake_ws.close_inbound()
    await task
    assert fake_ws.sent_bytes == [], "Phase 1 mock TTS must not emit audio chunks"


@pytest.mark.asyncio
async def test_unknown_message_type_emits_protocol_error(fake_ws: FakeWS, session: Session) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "garbage"})
    await _drain_until(fake_ws, "error")
    await fake_ws.close_inbound()
    await task
    errors = [json.loads(t) for t in fake_ws.sent_text if json.loads(t)["type"] == "error"]
    assert any(e["code"].startswith("protocol.") for e in errors)


@pytest.mark.asyncio
async def test_history_accumulates_across_turns(fake_ws: FakeWS, session: Session) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "text", "content": "Brief me on today"})
    await _drain_until(fake_ws, "llm.end", timeout=3.0)
    fake_ws.sent_text.clear()
    await fake_ws.feed_text({"type": "text", "content": "research notes"})
    await _drain_until(fake_ws, "llm.end", timeout=3.0)
    await fake_ws.close_inbound()
    await task
    # Session should still be alive after the first turn; second turn went through.
    assert any(json.loads(t).get("type") == "llm.end" for t in fake_ws.sent_text)
    assert len(session._history) >= 2  # noqa: SLF001 — testing internal state
```

- [ ] **Step 2: Run, verify pass**

```bash
pytest tests/test_session.py -q
```

Expected: 5/5 PASS.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_session.py
git commit -m "test(server): Session text-input flow end-to-end"
```

---

## Task 12: Session audio-input flow

**Files:**
- Modify: `server/tests/test_session.py`

- [ ] **Step 1: Add audio-flow test**

Append to `server/tests/test_session.py`:

```python
@pytest.mark.asyncio
async def test_audio_input_drives_stt_then_full_protocol(fake_ws: FakeWS) -> None:
    # Use a mock STT with a brief-related canned final so we hit a scenario.
    sess = Session(
        ws=fake_ws,
        stt=MockSTT(canned_final="Brief me on today."),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
    )
    task = asyncio.create_task(sess.run())
    await fake_ws.feed_text({"type": "audio.start", "sampleRate": 16000, "format": "pcm_s16le"})
    # Send 5 mic chunks (binary frames).
    from server.audio import encode_mic_chunk
    for _ in range(5):
        await fake_ws.feed_bytes(encode_mic_chunk(b"\x00\x00" * 320))  # 20 ms @ 16 kHz
    await fake_ws.feed_text({"type": "audio.end"})
    await _drain_until(fake_ws, "llm.end", timeout=3.0)
    await fake_ws.close_inbound()
    await task

    types = [json.loads(t)["type"] for t in fake_ws.sent_text]
    # STT partial(s) before stt.final
    assert "stt.partial" in types
    final_idx = types.index("stt.final")
    partial_idxs = [i for i, t in enumerate(types) if t == "stt.partial"]
    assert all(i < final_idx for i in partial_idxs)
    # Then llm.token, tts.sentence, llm.end
    assert "llm.token" in types
    assert "tts.sentence" in types
    assert "llm.end" in types


@pytest.mark.asyncio
async def test_audio_end_without_start_errors(fake_ws: FakeWS, session: Session) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "audio.end"})
    await _drain_until(fake_ws, "error")
    await fake_ws.close_inbound()
    await task
    errors = [json.loads(t) for t in fake_ws.sent_text if json.loads(t)["type"] == "error"]
    assert any(e["code"] == "protocol.audio_unframed" for e in errors)


@pytest.mark.asyncio
async def test_mic_chunk_before_audio_start_errors(fake_ws: FakeWS, session: Session) -> None:
    from server.audio import encode_mic_chunk
    task = asyncio.create_task(session.run())
    await fake_ws.feed_bytes(encode_mic_chunk(b"\x00\x00" * 8))
    await _drain_until(fake_ws, "error")
    await fake_ws.close_inbound()
    await task
    errors = [json.loads(t) for t in fake_ws.sent_text if json.loads(t)["type"] == "error"]
    assert any(e["code"] == "protocol.audio_unframed" for e in errors)
```

- [ ] **Step 2: Run, verify pass**

```bash
pytest tests/test_session.py -q
```

Expected: 8/8 PASS.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_session.py
git commit -m "test(server): Session audio-input flow + framing errors"
```

---

## Task 13: Session interrupt + cancellation

**Files:**
- Modify: `server/tests/test_session.py`

- [ ] **Step 1: Add interrupt tests**

Append to `server/tests/test_session.py`:

```python
@pytest.mark.asyncio
async def test_interrupt_during_reply_stops_token_stream(fake_ws: FakeWS) -> None:
    # Slow LLM so we have time to interrupt mid-stream.
    sess = Session(
        ws=fake_ws,
        stt=MockSTT(),
        llm=MockLLM(token_delay_ms=20),
        tts=MockTTS(),
    )
    task = asyncio.create_task(sess.run())
    await fake_ws.feed_text({"type": "text", "content": "Brief me on today"})
    # Wait for at least one llm.token before interrupting.
    await _drain_until(fake_ws, "llm.token", timeout=2.0)
    await fake_ws.feed_text({"type": "interrupt"})
    await _drain_until(fake_ws, "llm.end", timeout=2.0)
    await fake_ws.close_inbound()
    await task

    # Exactly one llm.end overall
    types = [json.loads(t)["type"] for t in fake_ws.sent_text]
    assert types.count("llm.end") == 1


@pytest.mark.asyncio
async def test_interrupt_with_no_active_turn_is_noop(fake_ws: FakeWS, session: Session) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "interrupt"})
    await asyncio.sleep(0.1)
    await fake_ws.close_inbound()
    await task
    # No error emitted; possibly an llm.end (idempotent flag flips once).
    errors = [json.loads(t) for t in fake_ws.sent_text if json.loads(t)["type"] == "error"]
    assert errors == []
```

- [ ] **Step 2: Run, verify pass**

```bash
pytest tests/test_session.py -q
```

Expected: 10/10 PASS.

- [ ] **Step 3: Commit**

```bash
git add server/tests/test_session.py
git commit -m "test(server): Session interrupt cancels in-flight turn idempotently"
```

---

## Task 14: FastAPI app + WS route + lifespan

**Files:**
- Create: `server/server/config.py`
- Create: `server/server/main.py`

- [ ] **Step 1: Create `server/server/config.py`**

```python
"""Environment-driven configuration (Phase 1: minimal)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    ws_port: int = 8765
    log_level: str = "INFO"


settings = Settings()
```

- [ ] **Step 2: Create `server/server/main.py`**

```python
"""FastAPI app + WebSocket endpoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import settings
from .pipelines.mock_llm import MockLLM
from .pipelines.mock_stt import MockSTT
from .pipelines.mock_tts import MockTTS
from .session import Session

logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    log.info("lifespan: building Phase 1 mock pipelines")
    state = {
        "stt": MockSTT(),
        "llm": MockLLM(),
        "tts": MockTTS(),
    }
    yield state


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

    async def receive(self) -> dict[str, Any]:
        return await self._ws.receive()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    state = ws.app.state
    pipelines = ws.scope["app"].router.lifespan_context  # type: ignore[attr-defined]
    # The lifespan-yielded state is on app.state in FastAPI; access via
    # request scope. Here we just instantiate fresh per-connection mocks
    # to avoid coupling to internal lifespan plumbing.
    session = Session(
        ws=_StarletteWSAdapter(ws),
        stt=MockSTT(),
        llm=MockLLM(),
        tts=MockTTS(),
    )
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    finally:
        await session.cleanup()
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass
```

- [ ] **Step 3: Boot smoke**

```bash
uvicorn server.main:app --port 8765 &
sleep 2
curl -s http://localhost:8765/health
echo
kill %1 2>/dev/null
```

Expected: `{"status":"ok"}`.

- [ ] **Step 4: Commit**

```bash
git add server/server/config.py server/server/main.py
git commit -m "feat(server): FastAPI app + WS endpoint + health route"
```

---

## Task 15: WS integration test (httpx async client)

**Files:**
- Create: `server/tests/test_ws_integration.py`

- [ ] **Step 1: Create the integration test**

Create `server/tests/test_ws_integration.py`:

```python
"""End-to-end test: real FastAPI app, real WebSocket, against mock pipelines.

Uses httpx's ASGITransport + websockets via an in-process client. We open
a connection, drive the protocol, and assert the emitted event sequence.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from starlette.testclient import TestClient

from server.main import app


def test_ws_text_flow_end_to_end() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        ws.send_text(json.dumps({"type": "text", "content": "Brief me on today"}))
        types: list[str] = []
        sentences: list[dict[str, str]] = []
        while True:
            data = ws.receive()
            if "text" in data and data["text"]:
                msg = json.loads(data["text"])
                types.append(msg["type"])
                if msg["type"] == "tts.sentence":
                    sentences.append(msg)
                if msg["type"] == "llm.end":
                    break
            elif "bytes" in data and data["bytes"]:
                # Phase 1 must not emit binary frames.
                pytest.fail("Phase 1 must not emit audio chunks")
        assert "stt.final" in types
        assert "llm.token" in types
        assert sentences  # at least one sentence emitted


def test_ws_unknown_type_returns_error() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        _ = ws.receive_json()  # ready
        ws.send_text(json.dumps({"type": "garbage"}))
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"].startswith("protocol.")


def test_health_endpoint() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

Add `httpx` to dev deps if not already present (it is — Task 1).

- [ ] **Step 2: Run**

```bash
pytest tests/test_ws_integration.py -q
```

Expected: 3/3 PASS.

- [ ] **Step 3: Run full suite**

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add server/tests/test_ws_integration.py
git commit -m "test(server): WS integration via Starlette TestClient"
```

---

## Task 16: CLI test client (text mode + REPL)

**Files:**
- Create: `server/server/cli_test.py`

- [ ] **Step 1: Implement CLI**

Create `server/server/cli_test.py`:

```python
"""CLI test client for the Jarvis WS protocol.

Usage:
    python -m server.cli_test                     # REPL
    python -m server.cli_test --text "say hi"     # one-shot
    python -m server.cli_test --ws ws://host:port/ws
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from websockets.asyncio.client import connect


async def _drive_one(ws: Any, user_text: str) -> None:
    await ws.send(json.dumps({"type": "text", "content": user_text}))
    print()
    sys.stdout.write(f"> {user_text}\n< ")
    sys.stdout.flush()
    while True:
        raw = await ws.recv()
        if isinstance(raw, bytes):
            # Phase 1: no audio expected. Print marker.
            sys.stdout.write(f"[binary {len(raw)}B]")
            continue
        msg = json.loads(raw)
        match msg.get("type"):
            case "llm.token":
                sys.stdout.write(msg["delta"])
                sys.stdout.flush()
            case "llm.end":
                print()
                return
            case "tts.sentence":
                # Visual marker only.
                pass
            case "tts.end":
                pass
            case "error":
                print(f"\n[error] {msg.get('code')}: {msg.get('message')}")
                return
            case "telemetry":
                pass
            case _:
                pass


async def _await_ready(ws: Any) -> None:
    while True:
        raw = await ws.recv()
        if isinstance(raw, bytes):
            continue
        msg = json.loads(raw)
        if msg.get("type") == "ready":
            return


async def _run(url: str, text: str | None) -> int:
    async with connect(url, max_size=4 * 1024 * 1024) as ws:
        await _await_ready(ws)
        if text is not None:
            await _drive_one(ws, text)
            return 0
        # REPL
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
            except (EOFError, KeyboardInterrupt):
                return 0
            if not line:
                return 0
            line = line.strip()
            if not line:
                continue
            await _drive_one(ws, line)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ws", default="ws://localhost:8765/ws")
    p.add_argument("--text", default=None)
    args = p.parse_args()
    raise SystemExit(asyncio.run(_run(args.ws, args.text)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manual smoke**

```bash
uvicorn server.main:app --port 8765 &
sleep 2
python -m server.cli_test --text "Brief me on today"
kill %1 2>/dev/null
```

Expected: streamed reply prints; exits cleanly.

- [ ] **Step 3: Commit**

```bash
git add server/server/cli_test.py
git commit -m "feat(server): CLI test client (text + REPL)"
```

---

## Task 17: CLI audio-input simulation

**Files:**
- Modify: `server/server/cli_test.py`

- [ ] **Step 1: Add `--audio-fixture` mode**

Replace `_run` and `main` in `cli_test.py` to support `--audio-fixture <path>` that streams a WAV's PCM as binary mic chunks. Keep this minimal — no recording, just file replay.

```python
import wave
from server.audio import encode_mic_chunk


async def _drive_audio_fixture(ws: Any, wav_path: str) -> None:
    with wave.open(wav_path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("fixture must be mono 16-bit PCM")
        rate = w.getframerate()
        await ws.send(json.dumps({"type": "audio.start", "sampleRate": rate, "format": "pcm_s16le"}))
        # Stream in 20 ms windows.
        frames_per_chunk = max(1, rate // 50)
        while True:
            data = w.readframes(frames_per_chunk)
            if not data:
                break
            await ws.send(encode_mic_chunk(data))
            await asyncio.sleep(0.005)
        await ws.send(json.dumps({"type": "audio.end"}))
    # Drain reply
    print()
    sys.stdout.write("< ")
    sys.stdout.flush()
    while True:
        raw = await ws.recv()
        if isinstance(raw, bytes):
            continue
        msg = json.loads(raw)
        if msg.get("type") == "stt.final":
            sys.stdout.write(f"\n[stt.final] {msg['text']}\n< ")
        elif msg.get("type") == "llm.token":
            sys.stdout.write(msg["delta"])
            sys.stdout.flush()
        elif msg.get("type") == "llm.end":
            print()
            return
        elif msg.get("type") == "error":
            print(f"\n[error] {msg.get('code')}: {msg.get('message')}")
            return
```

Update the argument parser and dispatch:

```python
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ws", default="ws://localhost:8765/ws")
    p.add_argument("--text", default=None)
    p.add_argument("--audio-fixture", default=None, help="Path to a mono 16-bit PCM WAV")
    args = p.parse_args()

    async def _go() -> int:
        async with connect(args.ws, max_size=4 * 1024 * 1024) as ws:
            await _await_ready(ws)
            if args.audio_fixture is not None:
                await _drive_audio_fixture(ws, args.audio_fixture)
                return 0
            if args.text is not None:
                await _drive_one(ws, args.text)
                return 0
            loop = asyncio.get_event_loop()
            while True:
                try:
                    line = await loop.run_in_executor(None, sys.stdin.readline)
                except (EOFError, KeyboardInterrupt):
                    return 0
                if not line:
                    return 0
                line = line.strip()
                if not line:
                    continue
                await _drive_one(ws, line)

    raise SystemExit(asyncio.run(_go()))
```

- [ ] **Step 2: Generate a test fixture WAV (silence is fine)**

```bash
python -c "
import wave, struct
with wave.open('tests/fixtures/silence.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(struct.pack('<' + 'h' * 16000, *([0] * 16000)))
"
mkdir -p tests/fixtures
```

(If the path doesn't exist yet, create `tests/fixtures/` first then re-run the python snippet.)

- [ ] **Step 3: Manual smoke**

```bash
uvicorn server.main:app --port 8765 &
sleep 2
python -m server.cli_test --audio-fixture tests/fixtures/silence.wav
kill %1 2>/dev/null
```

Expected: `[stt.final] Brief me on today.` followed by a streamed reply.

- [ ] **Step 4: Commit**

```bash
git add server/server/cli_test.py server/tests/fixtures/silence.wav
git commit -m "feat(server): CLI audio-fixture mode (replay WAV as mic chunks)"
```

---

## Task 18: Final acceptance run

**Files:**
- (none — verification only)

- [ ] **Step 1: Full quality-gate sweep**

```bash
cd server
. .venv/bin/activate
ruff check .
mypy
pytest -q
```

Expected: ruff 0 errors · mypy 0 errors · pytest all green.

- [ ] **Step 2: Coverage spot-check**

```bash
pip install coverage
coverage run -m pytest -q
coverage report --include="server/protocol.py,server/session.py,server/pipelines/sentence_split.py"
```

Expected: ≥80% on each of the three.

- [ ] **Step 3: Manual end-to-end smoke**

```bash
uvicorn server.main:app --port 8765 &
sleep 2
python -m server.cli_test --text "Brief me on today"
python -m server.cli_test --text "research notes"
python -m server.cli_test --audio-fixture tests/fixtures/silence.wav
kill %1 2>/dev/null
```

Expected: each command prints a streamed reply.

- [ ] **Step 4: Commit if any inline tweaks were needed**

If the gates surfaced anything, fix and commit with descriptive messages. If not, no commit.

---

## Task 19: README + merge prep

**Files:**
- Create: `server/README.md`

- [ ] **Step 1: Write `server/README.md`**

```markdown
# Jarvis · Backend (`server/`)

FastAPI WebSocket server implementing the Jarvis protocol (architecture
§4.1). Spec-02 Phase 1: real protocol + framing + orchestrator + tests,
**mock pipelines** for STT / LLM / TTS. Phase 2 will swap mocks for
faster-whisper, an OpenAI-compatible LLM client, and OpenVoice.

## Develop

```bash
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
uvicorn server.main:app --port 8765
```

## Quality gates

```bash
ruff check .
mypy
pytest -q
```

## Try it

```bash
# Terminal 1
uvicorn server.main:app --port 8765

# Terminal 2 — one-shot
python -m server.cli_test --text "Brief me on today"

# Terminal 2 — REPL
python -m server.cli_test

# Terminal 2 — replay a WAV as mic input
python -m server.cli_test --audio-fixture tests/fixtures/silence.wav
```

## Architecture

See `docs/superpowers/specs/2026-05-08-backend-streaming-design.md`.

The pipeline interfaces (`server/pipelines/interfaces.py`) match the
shape that real `faster-whisper`, `openai.AsyncOpenAI`, and OpenVoice
will need in Phase 2. Swap is mechanical at the interface boundary.

## Phase 1 limitations

- Replies come from a static scenario library (`scenarios.py`); no real LLM.
- STT returns canned text regardless of audio content.
- TTS emits sentence markers but no audio chunks; spec-03 frontend uses
  its synthetic amplitude envelope during the `speaking` state.
```

- [ ] **Step 2: Commit**

```bash
git add server/README.md
git commit -m "docs(server): README — dev/run/test instructions"
```

- [ ] **Step 3: Inspect commit graph**

```bash
git log --oneline main..HEAD
```

Expected: a clean linear sequence of feature commits, one (or two) per task.

- [ ] **Step 4: Hand off to merge phase**

Stop here. Orchestrator will run `requesting-code-review` on a fresh subagent, apply Important fixes, then `finishing-a-development-branch` to merge.

---

## Self-review summary (orchestrator before commit of plan)

**Spec coverage check (each spec §11.A criterion → task):**

1. `pip install -e .[dev]` succeeds → Task 1
2. `uvicorn ... ` boots, emits `ready` → Task 14, Task 15
3. `pytest` passes ≥80% on protocol/session/sentence_split → Tasks 3, 5, 10–13, 18
4. `cli_test --text "say hi"` works → Tasks 16, 18
5. REPL accepts multi-turn → Task 16
6. `interrupt` mid-reply → Task 13
7. Binary frame round-trip → Task 4
8. Audio-input flow → Tasks 12, 17
9. `ruff check` clean → Task 2 + every task
10. `mypy` clean → Task 2 + every task
11. Phase 1 mock TTS emits no audio chunks → Tasks 9, 11

**Placeholder scan:** none — every step has concrete code or commands.

**Type consistency:** all event names, payload shapes, message types, and method signatures match across `protocol.py`, `audio.py`, `interfaces.py`, `session.py`, and the test fixtures.

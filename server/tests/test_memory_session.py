"""Session × MemoryStore integration with FakeSummarizer + MockLLM."""

from __future__ import annotations

import asyncio

import pytest

from server.memory.store import MemoryStore
from server.memory.types import Fact, Turn
from server.pipelines.mock_llm import MockLLM
from server.pipelines.mock_stt import MockSTT
from server.pipelines.mock_tts import MockTTS
from server.session import Session


class _FakeWS:
    def __init__(self) -> None:
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._closed = False

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def receive(self):
        return await self._inbox.get()

    def queue_disconnect(self) -> None:
        self._inbox.put_nowait({"type": "websocket.disconnect"})


class FakeSummarizer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def refresh_recent_summary(self, turns: list[Turn]) -> str:
        self.calls.append("refresh")
        return f"recent[{len(turns)}]"

    async def summarize_session(self, turns: list[Turn]) -> str:
        self.calls.append("session")
        return f"session[{len(turns)}]"

    async def extract_facts(self, turns: list[Turn]) -> list[Fact]:
        self.calls.append("facts")
        return [Fact("turns_seen", str(len(turns)))]


@pytest.fixture
async def store() -> MemoryStore:
    s = await MemoryStore.open(":memory:")
    yield s
    await s.close()


async def test_session_resume_picks_up_recent_session(store: MemoryStore) -> None:
    sid = await store.start_session()
    await store.append_turn(sid, "user", "earlier hi")
    await store.append_turn(sid, "assistant", "earlier hello")

    ws = _FakeWS()
    sess = Session(
        ws=ws,
        stt=MockSTT(),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
        memory=store,
        summarizer=FakeSummarizer(),
    )
    ws.queue_disconnect()
    await sess.run()
    assert sess.session_id == sid
    # _history seeded from prior session
    assert any(m["content"] == "earlier hi" for m in sess._history)


async def test_session_starts_fresh_when_nothing_resumable(store: MemoryStore) -> None:
    ws = _FakeWS()
    sess = Session(
        ws=ws,
        stt=MockSTT(),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
        memory=store,
        summarizer=FakeSummarizer(),
    )
    ws.queue_disconnect()
    await sess.run()
    assert sess._history == []


async def test_session_no_memory_starts_fresh() -> None:
    ws = _FakeWS()
    sess = Session(
        ws=ws,
        stt=MockSTT(),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
        memory=None,
    )
    ws.queue_disconnect()
    await sess.run()
    assert sess._history == []
    assert sess.session_id  # auto-generated, not None

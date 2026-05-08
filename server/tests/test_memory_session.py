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


class _RecordingLLM:
    def __init__(self) -> None:
        self.last_extra: str = "<unset>"

    async def stream(self, history, user_text, *, extra_context: str = ""):
        self.last_extra = extra_context
        for ch in "ok":
            yield ch


async def _drive_session(sess: Session, ws: _FakeWS, *texts: str) -> None:
    """Run sess.run() while sending text.in turns and waiting for each to complete."""
    import json

    run_task = asyncio.create_task(sess.run())
    try:
        await asyncio.sleep(0)  # let run() reach the receive loop
        for text in texts:
            payload = json.dumps({"type": "text", "content": text})
            ws._inbox.put_nowait({"type": "websocket.receive", "text": payload})
            # Wait for the turn task to be created AND complete.
            for _ in range(500):
                await asyncio.sleep(0.005)
                t = sess._turn_task
                if t is not None and t.done():
                    break
        ws._inbox.put_nowait({"type": "websocket.disconnect"})
        await run_task
    except Exception:
        run_task.cancel()
        raise


async def test_session_writes_user_and_assistant_turns(store: MemoryStore) -> None:
    ws = _FakeWS()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=_RecordingLLM(), tts=MockTTS(),
        memory=store, summarizer=FakeSummarizer(),
    )
    await _drive_session(sess, ws, "hello")
    turns = await store.load_session_turns(sess.session_id, cap=10)
    assert [t.role for t in turns] == ["user", "assistant"]
    assert turns[0].content == "hello"


async def test_session_passes_default_extra_context_when_no_trigger(store: MemoryStore) -> None:
    await store.write_recent_summary("recent stuff", last_turn_id=0)
    ws = _FakeWS()
    rec = _RecordingLLM()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=rec, tts=MockTTS(),
        memory=store, summarizer=FakeSummarizer(),
    )
    await _drive_session(sess, ws, "hello there")
    assert "Background" in rec.last_extra
    assert "What I know about you" not in rec.last_extra


async def test_session_passes_full_extra_context_on_trigger(store: MemoryStore) -> None:
    sid = await store.start_session()
    await store.upsert_facts([Fact("lang", "TypeScript")], sid)
    await store.write_recent_summary("recent stuff", last_turn_id=0)
    ws = _FakeWS()
    rec = _RecordingLLM()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=rec, tts=MockTTS(),
        memory=store, summarizer=FakeSummarizer(),
    )
    await _drive_session(sess, ws, "what's my preferred lang")
    assert "What I know about you" in rec.last_extra
    assert "lang: TypeScript" in rec.last_extra


async def test_session_refreshes_recent_summary_after_threshold(store: MemoryStore) -> None:
    ws = _FakeWS()
    fake = FakeSummarizer()
    sess = Session(
        ws=ws, stt=MockSTT(), llm=_RecordingLLM(), tts=MockTTS(),
        memory=store, summarizer=fake, recent_summary_refresh_turns=2,
    )
    await _drive_session(sess, ws, "turn 0", "turn 1", "turn 2")
    assert "refresh" in fake.calls

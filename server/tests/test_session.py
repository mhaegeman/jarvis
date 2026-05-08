"""Tests for the per-connection Session orchestrator."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from server.audio import encode_mic_chunk
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


async def _drain_until(
    fake_ws: FakeWS,
    type_: str,
    timeout: float = 3.0,  # noqa: ASYNC109 — polling helper, not a true asyncio.timeout
) -> list[dict[str, Any]]:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        msgs = [json.loads(t) for t in fake_ws.sent_text]
        if any(m.get("type") == type_ for m in msgs):
            return msgs
        await asyncio.sleep(0.02)
    seen = [json.loads(t).get("type") for t in fake_ws.sent_text]
    raise TimeoutError(f"never saw {type_}; saw: {seen}")


@pytest.mark.asyncio
async def test_emit_ready_on_run_start(session: Session, fake_ws: FakeWS) -> None:
    task = asyncio.create_task(session.run())
    await asyncio.sleep(0.05)
    await fake_ws.close_inbound()
    await task
    types = [json.loads(t).get("type") for t in fake_ws.sent_text]
    assert "ready" in types


@pytest.mark.asyncio
async def test_text_input_drives_full_protocol(session: Session, fake_ws: FakeWS) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "text", "content": "Brief me on today"})
    await _drain_until(fake_ws, "llm.end")
    await fake_ws.close_inbound()
    await task

    types = [json.loads(t)["type"] for t in fake_ws.sent_text]
    assert types[0] == "ready"
    assert "stt.final" in types
    assert "llm.token" in types
    assert "llm.end" in types
    assert "tts.sentence" in types
    assert "tts.end" in types

    sentences = [
        json.loads(t)
        for t in fake_ws.sent_text
        if json.loads(t)["type"] == "tts.sentence"
    ]
    assert len(sentences) == 4
    audio_ids = [s["audioId"] for s in sentences]
    assert len(set(audio_ids)) == 4
    assert all(aid.startswith("s") and "-" in aid for aid in audio_ids)


@pytest.mark.asyncio
async def test_text_input_no_audio_chunks_in_phase_1(session: Session, fake_ws: FakeWS) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "text", "content": "Brief me"})
    await _drain_until(fake_ws, "llm.end")
    await fake_ws.close_inbound()
    await task
    assert fake_ws.sent_bytes == []


@pytest.mark.asyncio
async def test_unknown_message_type_emits_protocol_error(
    session: Session, fake_ws: FakeWS
) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "garbage"})
    await _drain_until(fake_ws, "error")
    await fake_ws.close_inbound()
    await task
    errors = [json.loads(t) for t in fake_ws.sent_text if json.loads(t)["type"] == "error"]
    assert any(e["code"].startswith("protocol.") for e in errors)


@pytest.mark.asyncio
async def test_history_accumulates_across_turns(session: Session, fake_ws: FakeWS) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "text", "content": "Brief me on today"})
    await _drain_until(fake_ws, "llm.end")
    fake_ws.sent_text.clear()
    await fake_ws.feed_text({"type": "text", "content": "research notes"})
    await _drain_until(fake_ws, "llm.end")
    await fake_ws.close_inbound()
    await task
    assert any(json.loads(t).get("type") == "llm.end" for t in fake_ws.sent_text)
    # 2 turns: 4 history entries (user + assistant × 2)
    assert len(session._history) == 4  # noqa: SLF001


@pytest.mark.asyncio
async def test_audio_input_drives_stt_then_full_protocol(fake_ws: FakeWS) -> None:
    sess = Session(
        ws=fake_ws,
        stt=MockSTT(canned_final="Brief me on today."),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
    )
    task = asyncio.create_task(sess.run())
    await fake_ws.feed_text({"type": "audio.start", "sampleRate": 16000, "format": "pcm_s16le"})
    for _ in range(5):
        await fake_ws.feed_bytes(encode_mic_chunk(b"\x00\x00" * 320))
    await fake_ws.feed_text({"type": "audio.end"})
    await _drain_until(fake_ws, "llm.end")
    await fake_ws.close_inbound()
    await task

    types = [json.loads(t)["type"] for t in fake_ws.sent_text]
    assert "stt.partial" in types
    final_idx = types.index("stt.final")
    partial_idxs = [i for i, t in enumerate(types) if t == "stt.partial"]
    assert all(i < final_idx for i in partial_idxs)
    assert "llm.token" in types
    assert "tts.sentence" in types
    assert "llm.end" in types


@pytest.mark.asyncio
async def test_audio_end_without_start_errors(session: Session, fake_ws: FakeWS) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "audio.end"})
    await _drain_until(fake_ws, "error")
    await fake_ws.close_inbound()
    await task
    errors = [json.loads(t) for t in fake_ws.sent_text if json.loads(t)["type"] == "error"]
    assert any(e["code"] == "protocol.audio_unframed" for e in errors)


@pytest.mark.asyncio
async def test_mic_chunk_before_audio_start_errors(session: Session, fake_ws: FakeWS) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_bytes(encode_mic_chunk(b"\x00\x00" * 8))
    await _drain_until(fake_ws, "error")
    await fake_ws.close_inbound()
    await task
    errors = [json.loads(t) for t in fake_ws.sent_text if json.loads(t)["type"] == "error"]
    assert any(e["code"] == "protocol.audio_unframed" for e in errors)


@pytest.mark.asyncio
async def test_interrupt_during_reply_stops_token_stream(fake_ws: FakeWS) -> None:
    sess = Session(
        ws=fake_ws,
        stt=MockSTT(),
        llm=MockLLM(token_delay_ms=20),
        tts=MockTTS(),
    )
    task = asyncio.create_task(sess.run())
    await fake_ws.feed_text({"type": "text", "content": "Brief me on today"})
    await _drain_until(fake_ws, "llm.token", timeout=2.0)
    await fake_ws.feed_text({"type": "interrupt"})
    await _drain_until(fake_ws, "llm.end", timeout=2.0)
    await fake_ws.close_inbound()
    await task
    types = [json.loads(t)["type"] for t in fake_ws.sent_text]
    assert types.count("llm.end") == 1


@pytest.mark.asyncio
async def test_interrupt_with_no_active_turn_is_noop(session: Session, fake_ws: FakeWS) -> None:
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "interrupt"})
    await asyncio.sleep(0.1)
    await fake_ws.close_inbound()
    await task
    msgs = [json.loads(t) for t in fake_ws.sent_text]
    errors = [m for m in msgs if m["type"] == "error"]
    assert errors == []
    # Idle interrupt must not emit a spurious llm.end (regression for review #12).
    types = [m["type"] for m in msgs]
    assert "llm.end" not in types


@pytest.mark.asyncio
async def test_llm_end_fires_before_tts_completes(session: Session, fake_ws: FakeWS) -> None:
    """Regression: llm.end must arrive in parallel with TTS, not after the
    last tts.end. Frontend transitions out of `thinking` rely on llm.end.
    """
    task = asyncio.create_task(session.run())
    await fake_ws.feed_text({"type": "text", "content": "Brief me on today"})
    await _drain_until(fake_ws, "llm.end")
    await fake_ws.close_inbound()
    await task

    types = [json.loads(t)["type"] for t in fake_ws.sent_text]
    llm_end_idx = types.index("llm.end")
    # At least one tts.end appears AFTER llm.end (proves they are concurrent
    # and llm.end did not wait for the whole reply to be spoken).
    later_tts_ends = [i for i, t in enumerate(types) if t == "tts.end" and i > llm_end_idx]
    assert later_tts_ends, (
        f"llm.end should fire before all tts.end events; got types={types}"
    )


@pytest.mark.asyncio
async def test_duplicate_audio_start_errors_and_does_not_leak_task(
    fake_ws: FakeWS,
) -> None:
    """Regression: a second `audio.start` while already recording must be
    rejected with a protocol error and must NOT replace `_partials_task` /
    `_mic_q` (which would leak the previous task waiting on an abandoned queue).
    """
    sess = Session(
        ws=fake_ws,
        stt=MockSTT(canned_final="hi."),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
    )
    task = asyncio.create_task(sess.run())
    await fake_ws.feed_text({"type": "audio.start", "sampleRate": 16000, "format": "pcm_s16le"})
    await asyncio.sleep(0.05)
    first_task = sess._partials_task  # noqa: SLF001
    first_q = sess._mic_q  # noqa: SLF001
    assert first_task is not None and first_q is not None
    await fake_ws.feed_text({"type": "audio.start", "sampleRate": 16000, "format": "pcm_s16le"})
    await _drain_until(fake_ws, "error")
    # Same task / queue references — duplicate start must not replace state.
    assert sess._partials_task is first_task  # noqa: SLF001
    assert sess._mic_q is first_q  # noqa: SLF001
    errors = [json.loads(t) for t in fake_ws.sent_text if json.loads(t)["type"] == "error"]
    assert any(e["code"] == "protocol.audio_unframed" for e in errors)
    # Finish cleanly so the original partials task drains.
    await fake_ws.feed_text({"type": "audio.end"})
    await _drain_until(fake_ws, "llm.end")
    await fake_ws.close_inbound()
    await task


@pytest.mark.asyncio
async def test_cleanup_does_not_hang_when_send_queue_is_saturated(
    fake_ws: FakeWS,
) -> None:
    """Regression: if the outbound queue is full when cleanup runs, the
    `__stop__` sentinel cannot be enqueued. Cleanup must still terminate
    instead of awaiting the sender forever.
    """
    sess = Session(
        ws=fake_ws,
        stt=MockSTT(),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
    )
    # Start the sender/heartbeat tasks without entering the receive loop.
    sess._sender_task = asyncio.create_task(sess._sender_loop())  # noqa: SLF001
    # Fill the outbound queue so the sender is parked on send_text and
    # subsequent put_nowait calls (including the sentinel) raise QueueFull.

    blocked = asyncio.Event()

    async def blocking_send_text(_: str) -> None:
        blocked.set()
        await asyncio.Future()  # never completes

    fake_ws.send_text = blocking_send_text  # type: ignore[method-assign]

    sess._send_q.put_nowait(("text", "first"))  # noqa: SLF001
    await blocked.wait()  # sender is now stuck in send_text
    while not sess._send_q.full():  # noqa: SLF001
        sess._send_q.put_nowait(("text", "x"))  # noqa: SLF001

    await asyncio.wait_for(sess.cleanup(), timeout=2.0)
    assert sess._sender_task.done()  # noqa: SLF001


@pytest.mark.asyncio
async def test_partials_emitted_during_listening_not_after_audio_end(
    fake_ws: FakeWS,
) -> None:
    """Regression: stt.partial events must arrive WHILE mic chunks are
    streaming in, not all at once after audio.end. Otherwise Phase 2 swap
    (real Whisper) is non-mechanical.
    """
    sess = Session(
        ws=fake_ws,
        stt=MockSTT(canned_final="Brief me on today."),
        llm=MockLLM(token_delay_ms=0),
        tts=MockTTS(),
    )
    task = asyncio.create_task(sess.run())
    await fake_ws.feed_text({"type": "audio.start", "sampleRate": 16000, "format": "pcm_s16le"})
    # Feed two chunks then poll for partials BEFORE sending audio.end.
    await fake_ws.feed_bytes(encode_mic_chunk(b"\x00\x00" * 320))
    await fake_ws.feed_bytes(encode_mic_chunk(b"\x00\x00" * 320))
    # Give the partials task a chance to drain the queue.
    await asyncio.sleep(0.1)
    types_before_end = [json.loads(t)["type"] for t in fake_ws.sent_text]
    assert "stt.partial" in types_before_end, (
        f"partials should fire during listening; saw only {types_before_end}"
    )
    # Now finish.
    await fake_ws.feed_text({"type": "audio.end"})
    await _drain_until(fake_ws, "llm.end")
    await fake_ws.close_inbound()
    await task

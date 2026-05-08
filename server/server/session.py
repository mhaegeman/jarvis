"""Per-connection orchestrator. Receives WS messages, drives pipelines,
emits protocol events. Phase 1 uses mock pipelines; the orchestrator
itself is real and Phase-2-ready.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
from collections.abc import AsyncIterator, MutableMapping
from typing import Any, Protocol

from .audio import KIND_CLIENT_MIC, decode_audio_frame, encode_tts_chunk
from .calendar_client import CalendarClient
from .heartbeat import Heartbeat
from .memory.store import MemoryStore
from .memory.summarizer import Summarizer
from .pipelines.interfaces import LLM, STT, TTS
from .pipelines.sentence_split import split_sentences_stream
from .protocol import (
    AudioEnd,
    AudioStart,
    CalendarSync,
    Hello,
    Interrupt,
    Pong,
    ServerMessage,
    TextIn,
    decode_client,
    encode_server,
)
from .state import StateEmitter

log = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_S = 5.0


class _WS(Protocol):
    async def send_text(self, data: str) -> None: ...
    async def send_bytes(self, data: bytes) -> None: ...
    async def receive(self) -> MutableMapping[str, Any]: ...


_AUDIO_ID_RANDS = "abcdefghijklmnopqrstuvwxyz0123456789"


def _audio_id(idx: int) -> str:
    rand = "".join(secrets.choice(_AUDIO_ID_RANDS) for _ in range(6))
    return f"s{idx}-{rand}"


class Session:
    def __init__(
        self,
        ws: _WS,
        stt: STT,
        llm: LLM,
        tts: TTS,
        history_cap: int = 20,
        *,
        memory: MemoryStore | None = None,
        summarizer: Summarizer | None = None,
        resume_window_minutes: int = 30,
        recent_summary_refresh_turns: int = 5,
        recent_summary_window: int = 20,
        facts_cap: int = 50,
    ) -> None:
        self._ws = ws
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._history: list[dict[str, str]] = []
        self._history_cap = history_cap
        self._send_q: asyncio.Queue[tuple[str, str | bytes]] = asyncio.Queue(maxsize=256)
        self._sender_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._turn_task: asyncio.Task[None] | None = None
        self._partials_task: asyncio.Task[None] | None = None
        self._mic_buf: list[bytes] = []
        self._mic_q: asyncio.Queue[bytes | None] | None = None
        self._mic_active = False
        self._closing = False
        # llm_ended starts True so a stray `interrupt` while idle does not
        # spuriously emit `llm.end`. Reset to False at the start of each turn.
        self._llm_ended = True
        self.heartbeat = Heartbeat(interval_s=HEARTBEAT_INTERVAL_S)
        self.session_id = secrets.token_hex(4)
        self.endpoint = "ws://localhost:8000/ws"
        self.emitter = StateEmitter(self)
        self._state_task: asyncio.Task[None] | None = None
        self.calendar = CalendarClient()
        self._calendar_sync_task: asyncio.Task[None] | None = None
        self._memory = memory
        self._summarizer = summarizer
        self._resume_window_minutes = resume_window_minutes
        self._refresh_turns = recent_summary_refresh_turns
        self._recent_window = recent_summary_window
        self._facts_cap = facts_cap

    # ─── public lifecycle ─────────────────────────────────────────────

    async def run(self) -> None:
        self._sender_task = asyncio.create_task(self._sender_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._state_task = asyncio.create_task(self.emitter.run())
        # ── memory: resume or start a new session ──────────────────
        if self._memory is not None:
            resumable = await self._memory.find_resumable(
                within_minutes=self._resume_window_minutes
            )
            if resumable is not None:
                self.session_id = resumable
                turns = await self._memory.load_session_turns(resumable, cap=self._history_cap)
                self._history = [{"role": t.role, "content": t.content} for t in turns]
            else:
                self.session_id = await self._memory.start_session()
        await self._enqueue_json(ServerMessage.ready(session_id=self.session_id))
        # Calendar starts empty; the client requests a sync via calendar.sync.
        await self._enqueue_json(ServerMessage.calendar_update(entries=[]))
        try:
            while not self._closing:
                ev = await self._ws.receive()
                etype = ev.get("type")
                if etype == "websocket.disconnect":
                    break
                if etype != "websocket.receive":
                    continue
                if ev.get("bytes") is not None:
                    await self._handle_binary(ev["bytes"])
                elif ev.get("text") is not None:
                    await self._handle_text(ev["text"])
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        self._closing = True
        for t in (
            self._partials_task,
            self._turn_task,
            self._heartbeat_task,
            self._state_task,
            self._calendar_sync_task,
        ):
            if t and not t.done():
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t
        await self._consolidate_memory()  # NEW

        if self._sender_task and not self._sender_task.done():
            # If the queue is saturated the sentinel is dropped; cancel the
            # sender so cleanup cannot hang forever waiting on get().
            try:
                self._send_q.put_nowait(("__stop__", ""))
            except asyncio.QueueFull:
                self._sender_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._sender_task

    # ─── inbound dispatch ─────────────────────────────────────────────

    async def _handle_text(self, raw: str) -> None:
        try:
            msg = decode_client(raw)
        except ValueError as e:
            await self._enqueue_json(ServerMessage.error("protocol.bad_message", str(e)))
            return
        if isinstance(msg, Hello):
            log.info("hello: clientVersion=%s", msg.clientVersion)
            return
        if isinstance(msg, AudioStart):
            await self._begin_listening()
            return
        if isinstance(msg, AudioEnd):
            if not self._mic_active:
                await self._enqueue_json(
                    ServerMessage.error(
                        "protocol.audio_unframed", "audio.end without audio.start"
                    )
                )
                return
            await self._end_listening()
            return
        if isinstance(msg, TextIn):
            self._start_turn(text=msg.content)
            return
        if isinstance(msg, Interrupt):
            await self._do_interrupt()
            return
        if isinstance(msg, Pong):
            self.heartbeat.record_pong(msg.seq)
            return
        if isinstance(msg, CalendarSync):
            await self._do_calendar_sync()
            return

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
                ServerMessage.error(
                    "protocol.audio_unframed", "mic chunk before audio.start"
                )
            )
            return
        self._mic_buf.append(frame.samples)
        if self._mic_q is not None:
            self._mic_q.put_nowait(frame.samples)

    # ─── listening / partials ─────────────────────────────────────────

    async def _begin_listening(self) -> None:
        if self._mic_active:
            await self._enqueue_json(
                ServerMessage.error(
                    "protocol.audio_unframed",
                    "audio.start while already recording",
                )
            )
            return
        self._mic_buf = []
        self._mic_q = asyncio.Queue()
        self._mic_active = True
        self._partials_task = asyncio.create_task(self._run_partials())

    async def _end_listening(self) -> None:
        self._mic_active = False
        if self._mic_q is not None:
            self._mic_q.put_nowait(None)
        if self._partials_task and not self._partials_task.done():
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._partials_task
        self._partials_task = None
        self._mic_q = None
        self._start_turn(audio=True)

    async def _run_partials(self) -> None:
        """Stream stt.partial events as mic chunks arrive."""
        q = self._mic_q
        if q is None:
            return

        async def _audio_iter() -> AsyncIterator[bytes]:
            while True:
                item = await q.get()
                if item is None:
                    return
                yield item

        try:
            async for partial in self._stt.partials(_audio_iter()):
                await self._enqueue_json(ServerMessage.stt_partial(partial))
        except asyncio.CancelledError:
            raise

    # ─── turn machinery ───────────────────────────────────────────────

    def _start_turn(self, *, text: str | None = None, audio: bool = False) -> None:
        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
        self._llm_ended = False
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
        del audio  # signal only; mic_buf carries the data, partials already streamed
        if text is not None:
            await self._enqueue_json(ServerMessage.stt_final(text))
            return text

        async def _audio_iter() -> AsyncIterator[bytes]:
            for c in self._mic_buf:
                yield c

        final = await self._stt.final(_audio_iter())
        await self._enqueue_json(ServerMessage.stt_final(final))
        return final

    async def _do_llm_and_tts(self, user_text: str) -> None:
        from .memory.context import MemoryContext
        from .memory.triggers import is_memory_query

        self._history.append({"role": "user", "content": user_text})

        if self._memory is not None:
            await self._memory.append_turn(self.session_id, "user", user_text)

        extra = ""
        if self._memory is not None:
            if is_memory_query(user_text):
                extra = await MemoryContext.full(self._memory, user_text)
            else:
                extra = await MemoryContext.default(self._memory)

        llm_iter = self._llm.stream(self._history, user_text, extra_context=extra)
        token_q: asyncio.Queue[str | None] = asyncio.Queue()
        sentence_q: asyncio.Queue[str | None] = asyncio.Queue()
        assistant_buf: list[str] = []

        async def fanout() -> None:
            try:
                async for delta in llm_iter:
                    assistant_buf.append(delta)
                    self.emitter.record_token()
                    await self._enqueue_json(ServerMessage.llm_token(delta))
                    await token_q.put(delta)
            finally:
                # Emit `llm.end` immediately when the LLM token stream ends —
                # in parallel with the still-running TTS pipeline. (Issue #1
                # from review: do not wait for tts.end to fire llm.end.)
                if not self._llm_ended:
                    self._llm_ended = True
                    await self._enqueue_json(ServerMessage.llm_end())
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
                await self._enqueue_json(
                    ServerMessage.tts_sentence(text=sent, audio_id=aid)
                )
                async for pcm in self._tts.synthesize(sent, aid):
                    await self._enqueue_bytes(encode_tts_chunk(aid, pcm))
                await self._enqueue_json(ServerMessage.tts_end(aid))

        await asyncio.gather(fanout(), consume_tokens_to_sentences(), speak_sentences())

        full = "".join(assistant_buf)
        if full:
            self._history.append({"role": "assistant", "content": full})
            if self._memory is not None:
                await self._memory.append_turn(self.session_id, "assistant", full)
        if len(self._history) > self._history_cap:
            self._history = self._history[-self._history_cap :]
        # Approximate token budget tracking: ~4 chars per token. Cheap and
        # stable for v2; spec-02 Phase 2 will replace this with a real
        # tokenizer when the LLM client lands.
        total_chars = sum(len(m["content"]) for m in self._history)
        self.emitter.record_token_budget(total_chars // 4)

        await self._maybe_refresh_recent_summary()

    async def _do_interrupt(self) -> None:
        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._turn_task
        if not self._llm_ended:
            self._llm_ended = True
            await self._enqueue_json(ServerMessage.llm_end())

    # ─── outbound queue / heartbeat ───────────────────────────────────

    async def _enqueue_json(self, msg: dict[str, Any]) -> None:
        try:
            self._send_q.put_nowait(("text", encode_server(msg)))
            self.emitter.record_packet()
        except asyncio.QueueFull:
            log.warning("send queue overflow, dropping JSON: %s", msg.get("type"))

    async def _enqueue_bytes(self, payload: bytes) -> None:
        try:
            self._send_q.put_nowait(("bytes", payload))
            self.emitter.record_packet()
        except asyncio.QueueFull:
            log.warning("send queue overflow, dropping audio chunk (%dB)", len(payload))

    @property
    def send_queue_depth(self) -> int:
        return self._send_q.qsize()

    @property
    def send_queue_max(self) -> int:
        return self._send_q.maxsize

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

    async def _do_calendar_sync(self) -> None:
        """Fetch today's calendar on demand. Concurrent syncs coalesce."""
        if self._calendar_sync_task and not self._calendar_sync_task.done():
            return
        self._calendar_sync_task = asyncio.create_task(self._run_calendar_sync())

    async def _run_calendar_sync(self) -> None:
        try:
            entries = await self.calendar.fetch_today()
            await self._enqueue_json(ServerMessage.calendar_update(entries=entries))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("calendar sync failed")
            await self._enqueue_json(
                ServerMessage.error("calendar.fetch_failed", "calendar fetch failed")
            )

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._closing:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                self.heartbeat.evict_stale()
                seq = self.heartbeat.send_ping()
                await self._enqueue_json(ServerMessage.ping(seq=seq))
        except asyncio.CancelledError:
            raise

    async def _maybe_refresh_recent_summary(self) -> None:
        if self._memory is None or self._summarizer is None:
            return
        meta = await self._memory.get_recent_summary_meta()
        delta = await self._memory.turns_since(meta.last_turn_id)
        if delta < self._refresh_turns:
            return
        # Pull the latest N turns across all sessions for the summary.
        # We access _conn directly because we need a cross-session SELECT;
        # the public API doesn't expose a "latest N turns globally" method.
        cur = await self._memory._conn.execute(
            "SELECT id, session_id, ts, role, content FROM turns ORDER BY id DESC LIMIT ?",
            (self._recent_window,),
        )
        rows = list(reversed(await cur.fetchall()))
        from .memory.types import Turn
        latest = [Turn(id=r[0], session_id=r[1], ts=r[2], role=r[3], content=r[4]) for r in rows]
        if not latest:
            return
        try:
            summary = await self._summarizer.refresh_recent_summary(latest)
            if summary:
                await self._memory.write_recent_summary(summary, latest[-1].id)
        except Exception:
            log.exception("recent_summary refresh failed")

    async def _consolidate_memory(self) -> None:
        if self._memory is None or self._summarizer is None:
            return
        try:
            turns = await self._memory.load_session_turns(self.session_id, cap=200)
            if len(turns) >= 2:
                summary = await self._summarizer.summarize_session(turns)
                if summary:
                    await self._memory.write_session_summary(self.session_id, summary)
                facts = await self._summarizer.extract_facts(turns)
                if facts:
                    await self._memory.upsert_facts(facts, source_session_id=self.session_id)
                    await self._memory.evict_facts_to_cap(self._facts_cap)
            await self._memory.end_session(self.session_id)
        except Exception:
            log.exception("memory consolidation failed")

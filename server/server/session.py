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
from .heartbeat import Heartbeat
from .pipelines.interfaces import LLM, STT, TTS
from .pipelines.sentence_split import split_sentences_stream
from .protocol import (
    AudioEnd,
    AudioStart,
    Hello,
    Interrupt,
    Pong,
    ServerMessage,
    TextIn,
    decode_client,
    encode_server,
)

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

    # ─── public lifecycle ─────────────────────────────────────────────

    async def run(self) -> None:
        self._sender_task = asyncio.create_task(self._sender_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        await self._enqueue_json(ServerMessage.ready())
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
        for t in (self._partials_task, self._turn_task, self._heartbeat_task):
            if t and not t.done():
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t
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
        self._history.append({"role": "user", "content": user_text})

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
        if len(self._history) > self._history_cap:
            self._history = self._history[-self._history_cap :]

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
        except asyncio.QueueFull:
            log.warning("send queue overflow, dropping JSON: %s", msg.get("type"))

    async def _enqueue_bytes(self, payload: bytes) -> None:
        try:
            self._send_q.put_nowait(("bytes", payload))
        except asyncio.QueueFull:
            log.warning("send queue overflow, dropping audio chunk (%dB)", len(payload))

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

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._closing:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                self.heartbeat.evict_stale()
                seq = self.heartbeat.send_ping()
                await self._enqueue_json(ServerMessage.ping(seq=seq))
        except asyncio.CancelledError:
            raise

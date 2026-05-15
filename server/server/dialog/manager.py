"""DialogManager — per-turn orchestrator.

Spec anchors: §3.3 (per-turn flow), §6 (segment execution), §9.1 (protocol).

The Manager owns the routing → streaming → voice-swap pipeline. It's
constructed once per Session (in main.py's lifespan when
`personas_enabled` is true) and `handle_turn` is called from
`Session.run` per user utterance.

Streaming model:
  1. Build DialogState from session memory.
  2. Dispatch (LLMBackedDispatcher or fallback) → Plan.
  3. Emit `dispatch.plan` to WS.
  4. For each segment:
     - Resolve persona + model_id from registry.tier
     - Build extra_context = specialty_profile + segment.intent
     - llm_factory(persona, model_id).stream(...) → token deltas
     - Per token: send llm.token (with speaker, segmentIdx)
     - Per sentence boundary: send tts.sentence + stream audio chunks
     - On segment end: send llm.segment_end
  5. Send llm.end.
  6. Update sticky-speaker (last_speaker, last_turn_ts) for next turn.
  7. Record Outcome in-memory.

Phase 3: when a CodexAgent is configured and the segment is
(pepper, codex_agent), delegate to _run_codex_segment() instead of
the chat stream path. Narration sentences are pushed back through
the same tts.sentence path. When no agent is configured or the
speaker is not Pepper, falls back to chat with a logged warning.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any, Protocol

from server.dialog.types import (
    DialogState,
    Outcome,
    PersonaId,
    Plan,
    Segment,
)
from server.personas.models import Persona
from server.personas.registry import PersonaRegistry
from server.pipelines.sentence_split import split_sentences_stream
from server.protocol import ServerMessage, encode_server

if TYPE_CHECKING:
    from server.dialog.feedback import FeedbackLogger
    from server.dialog.profile_refresher import ProfileRefresher

logger = logging.getLogger(__name__)


class _WSLike(Protocol):
    async def send_text(self, data: str) -> None: ...
    async def send_bytes(self, data: bytes) -> None: ...


class _LLMLike(Protocol):
    def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]: ...


class _DispatcherLike(Protocol):
    async def dispatch(
        self,
        text: str,
        state: DialogState,
        *,
        now_ts: float | None = None,
    ) -> Plan: ...


class _MultiVoiceTTSLike(Protocol):
    def synthesize_for_speaker(
        self,
        text: str,
        audio_id: str,
        *,
        speaker: str,
    ) -> AsyncIterator[bytes]: ...


class _CodexAgentLike(Protocol):
    def run(
        self,
        *,
        ws: _WSLike,
        task: str,
        run_id: str,
        speaker: str = "pepper",
    ) -> AsyncIterator[str]: ...

    async def cancel(self, run_id: str) -> None: ...


LLMFactory = Callable[[Persona, str], _LLMLike]


class DialogManager:
    """Per-turn orchestrator (Phase 3, chat + Codex agent)."""

    def __init__(
        self,
        *,
        registry: PersonaRegistry,
        dispatcher: _DispatcherLike,
        llm_factory: LLMFactory,
        tts: _MultiVoiceTTSLike,
        codex_agent: _CodexAgentLike | None = None,
        feedback: FeedbackLogger | None = None,
        refresher: ProfileRefresher | None = None,
        refresh_every: int = 20,
    ) -> None:
        self._registry = registry
        self._dispatcher = dispatcher
        self._llm_factory = llm_factory
        self._tts = tts
        self._codex_agent = codex_agent
        self._feedback = feedback
        self._refresher = refresher
        self._refresh_every = refresh_every
        self._turn_count = 0
        self._state = DialogState()
        self._outcomes: list[Outcome] = []
        # Concatenated text of every segment that produced tokens in the
        # most recent turn. Session reads this to append to its `_history`
        # so multi-turn chats keep context.
        self._last_assistant_text: str = ""

    def current_state(self) -> DialogState:
        return self._state

    def last_outcome(self) -> Outcome | None:
        return self._outcomes[-1] if self._outcomes else None

    def last_assistant_text(self) -> str:
        """The concatenated spoken text from the most recent turn (all segments)."""
        return self._last_assistant_text

    async def handle_turn(
        self,
        ws: _WSLike,
        *,
        text: str,
        history: list[dict[str, str]],
    ) -> None:
        """Run one turn end-to-end. Emits all WS messages; does not raise."""
        turn_id = f"t-{uuid.uuid4().hex[:8]}"
        start = time.monotonic()

        plan = await self._dispatcher.dispatch(text, self._state)
        await self._send(ws, ServerMessage.dispatch_plan(
            turn_id=turn_id,
            segments=[s.model_dump() for s in plan.segments],
            rationale=plan.rationale,
        ))

        # Reset per-turn buffers BEFORE the segment loop so Session sees only
        # this turn's output.
        self._last_assistant_text = ""
        assistant_chunks: list[str] = []
        last_streamed_speaker: PersonaId | None = None

        outcome = Outcome()
        try:
            for idx, segment in enumerate(plan.segments):
                seg_text: list[str] = []
                ok = await self._run_segment(
                    ws, idx=idx, segment=segment, history=history, plan=plan,
                    text_buf=seg_text,
                )
                if seg_text:
                    assistant_chunks.extend(seg_text)
                if ok:
                    # Track the LAST speaker who actually produced tokens —
                    # not the last planned segment, which may never have run.
                    last_streamed_speaker = segment.speaker
                else:
                    break
            outcome = outcome.model_copy(update={"completed": True})
        finally:
            await self._send(ws, ServerMessage.llm_end())
            self._last_assistant_text = "".join(assistant_chunks)
            if last_streamed_speaker is not None:
                self._state = DialogState(
                    last_speaker=last_streamed_speaker,
                    last_turn_ts=time.time(),
                    recent_turns=self._state.recent_turns,  # Phase 2: leave compact
                    warmth_budget=self._state.warmth_budget,
                )
            outcome = outcome.model_copy(update={
                "latency_ms": (time.monotonic() - start) * 1000.0,
            })
            self._outcomes.append(outcome)

        # ── Phase 5: learning loop wiring ──────────────────────────────
        # Record this turn in dispatch_log after llm.end.
        if self._feedback is not None:
            try:
                await self._feedback.record_turn(
                    turn_id=turn_id,
                    utterance=text,
                    explicit=None,  # name-at-start detection is out of scope for now
                    plan=plan,
                    outcome=outcome,
                )
            except Exception:  # noqa: BLE001
                logger.exception("FeedbackLogger.record_turn failed")

        # Increment turn counter; schedule a refresh when threshold is reached.
        if self._refresher is not None:
            self._turn_count += 1
            if self._turn_count >= self._refresh_every:
                self._turn_count = 0
                asyncio.create_task(self._refresher.refresh())

    async def _run_segment(
        self,
        ws: _WSLike,
        *,
        idx: int,
        segment: Segment,
        history: list[dict[str, str]],
        plan: Plan,
        text_buf: list[str] | None = None,
    ) -> bool:
        """Run a single segment. Returns False on failure (caller halts plan).

        When `text_buf` is provided, every streamed token delta is also appended
        to it so the caller can reconstruct the assistant's spoken text without
        re-parsing WS messages.
        """
        if not self._registry.is_available(segment.speaker):
            logger.warning("segment %d: persona %s unavailable; skipping",
                           idx, segment.speaker)
            return False
        persona = self._registry.get(segment.speaker)
        tier = persona.tiers[segment.tier]

        # Phase 3: Codex agent path — only for Pepper segments with a
        # configured agent. Jarvis with codex_agent falls through to chat.
        if (
            segment.mode == "codex_agent"
            and segment.speaker == "pepper"
            and self._codex_agent is not None
        ):
            return await self._run_codex_segment(
                ws, idx=idx, segment=segment, history=history, plan=plan,
                text_buf=text_buf,
            )

        # Fall through to chat for: chat mode segments, jarvis with codex_agent
        # (shouldn't happen per spec), missing CodexAgent (binary not resolved).
        if segment.mode == "codex_agent":
            logger.warning(
                "segment %d (%s, codex_agent) falling back to chat — "
                "agent unavailable or wrong speaker",
                idx, segment.speaker,
            )

        llm = self._llm_factory(persona, tier.model_id)

        extra_context = (
            f"Persona profile: {persona.specialty_profile}\n"
            f"Segment intent: {segment.intent}"
        )

        audio_id_base = f"seg-{idx}"
        sent_anything = False
        sentence_counter = 0

        # We use split_sentences_stream (an async generator) to buffer token
        # deltas into complete sentences. We feed tokens via a queue: the
        # producer coroutine consumes the LLM stream and pushes deltas; the
        # consumer (split_sentences_stream) reads from the queue.
        #
        # A sentinel value of None signals end-of-stream to the token_gen.

        _SENTINEL = object()
        queue: asyncio.Queue[str | object] = asyncio.Queue()

        async def _token_gen() -> AsyncIterator[str]:
            """Yield tokens from the queue until the sentinel."""
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    return
                yield item  # type: ignore[misc]

        async def _produce() -> bool:
            """Push LLM token deltas into the queue and send llm.token events.

            Returns True if at least one delta was sent.
            """
            nonlocal sent_anything
            try:
                async for delta in llm.stream(
                    history=history,
                    user_text=plan_text_for_segment(plan, idx, persona),
                    extra_context=extra_context,
                ):
                    sent_anything = True
                    if text_buf is not None:
                        text_buf.append(delta)
                    await self._send(ws, ServerMessage.llm_token(
                        delta, speaker=segment.speaker, segment_idx=idx,
                    ))
                    await queue.put(delta)
            finally:
                await queue.put(_SENTINEL)
            return sent_anything

        try:
            # Run producer and consumer concurrently.
            # _produce pushes to queue; split_sentences_stream reads from _token_gen.
            produce_task = asyncio.create_task(_produce())

            async for sentence in split_sentences_stream(_token_gen()):
                audio_id = f"{audio_id_base}-{sentence_counter}"
                sentence_counter += 1
                await self._emit_sentence(
                    ws, sentence, audio_id=audio_id,
                    speaker=segment.speaker,
                )

            # Await producer to propagate any exception it raised.
            await produce_task

        except Exception as exc:  # noqa: BLE001 — defensive at top of stream
            logger.exception("segment %d crashed", idx)
            # Drain the queue so the token_gen task doesn't hang.
            while not queue.empty():
                queue.get_nowait()
            # Emit a spoken error in the same voice.
            await self._send(ws, ServerMessage.llm_token(
                f"Error: {exc}",
                speaker=segment.speaker,
                segment_idx=idx,
            ))
            await self._send(ws, ServerMessage.llm_segment_end(
                speaker=segment.speaker, segment_idx=idx,
            ))
            return False

        await self._send(ws, ServerMessage.llm_segment_end(
            speaker=segment.speaker, segment_idx=idx,
        ))
        return sent_anything

    async def _run_codex_segment(
        self,
        ws: _WSLike,
        *,
        idx: int,
        segment: Segment,
        history: list[dict[str, str]],
        plan: Plan,
        text_buf: list[str] | None = None,
    ) -> bool:
        """Run a Codex agent segment. Narration sentences flow through the
        same tts.sentence path as chat segments (voice = persona.voice)."""
        assert self._codex_agent is not None  # checked by caller
        run_id = f"r-{uuid.uuid4().hex[:8]}"
        audio_id_base = f"seg-{idx}"
        sentence_counter = 0
        sent_anything = False

        try:
            async for sentence in self._codex_agent.run(
                ws=ws, task=segment.intent, run_id=run_id, speaker=segment.speaker,
            ):
                sent_anything = True
                if text_buf is not None:
                    text_buf.append(sentence)
                # Emit llm.token (one per sentence) so the transcript shows
                # what was spoken, then tts.sentence + audio.
                await self._send(ws, ServerMessage.llm_token(
                    sentence, speaker=segment.speaker, segment_idx=idx,
                ))
                audio_id = f"{audio_id_base}-{sentence_counter}"
                sentence_counter += 1
                await self._emit_sentence(
                    ws, sentence, audio_id=audio_id, speaker=segment.speaker,
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("codex segment %d crashed", idx)
            await self._send(ws, ServerMessage.llm_token(
                f"Error: {exc}", speaker=segment.speaker, segment_idx=idx,
            ))
            await self._send(ws, ServerMessage.llm_segment_end(
                speaker=segment.speaker, segment_idx=idx,
            ))
            return False

        await self._send(ws, ServerMessage.llm_segment_end(
            speaker=segment.speaker, segment_idx=idx,
        ))
        return sent_anything

    async def _emit_sentence(
        self,
        ws: _WSLike,
        text: str,
        *,
        audio_id: str,
        speaker: PersonaId,
    ) -> None:
        await self._send(ws, ServerMessage.tts_sentence(
            text=text, audio_id=audio_id, speaker=speaker,
        ))
        async for chunk in self._tts.synthesize_for_speaker(
            text, audio_id, speaker=speaker,
        ):
            await ws.send_bytes(chunk)
        await self._send(ws, ServerMessage.tts_end(audio_id))

    async def _send(self, ws: _WSLike, payload: dict[str, Any]) -> None:
        await ws.send_text(encode_server(payload))


def plan_text_for_segment(plan: Plan, idx: int, persona: Persona) -> str:
    """Build the user-visible text the LLM sees for a given segment.

    Phase 2: the original utterance is fine for solo turns; for multi-
    segment plans the second persona sees "Continuing from <prior speaker>:
    <intent>" so it doesn't blindly repeat. Detail is intentionally minimal —
    the persona's system prompt + specialty profile + extra_context carry
    the heavy lifting.
    """
    if idx == 0:
        return plan.segments[0].intent
    prior = plan.segments[idx - 1]
    return (
        f"Continuing from {prior.speaker}'s segment "
        f"({prior.intent[:80]}). Your part: {plan.segments[idx].intent}"
    )

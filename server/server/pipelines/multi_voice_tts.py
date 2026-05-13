"""MultiVoiceTTS — routes synthesis to one of N TTS instances by speaker.

The existing `EdgeTTS` holds one voice (Microsoft neural voice id). Phase 2
needs a different voice per Jarvis / Pepper segment without modifying the
`TTS` ABC or the existing `_build_tts()` factory.

This wrapper holds a map `{speaker_id: TTS}` and:
  * Implements the `TTS` ABC by routing `synthesize()` to the default speaker
    (so the existing single-voice code path keeps working).
  * Exposes `synthesize_for_speaker(text, audio_id, speaker)` for the
    Phase 2 `DialogManager` to pick a voice per segment.

If a speaker isn't registered (e.g. Codex CLI binary missing and we fall
back to chat-only Pepper — but Pepper's voice never reaches this wrapper
because Pepper is just unavailable) we route to `default_speaker`. That
shouldn't happen in practice; logged as a warning.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from .interfaces import TTS

log = logging.getLogger(__name__)


class MultiVoiceTTS(TTS):
    """A `TTS` that dispatches by speaker id."""

    def __init__(self, voices: dict[str, TTS], *, default_speaker: str) -> None:
        if not voices:
            raise ValueError("MultiVoiceTTS requires at least one voice")
        if default_speaker not in voices:
            raise ValueError(
                f"default_speaker {default_speaker!r} not in voices: {sorted(voices)}"
            )
        rates = {v.sample_rate() for v in voices.values()}
        if len(rates) != 1:
            raise ValueError(
                f"all voices must share a sample_rate (got {sorted(rates)})"
            )
        self._voices = dict(voices)
        self._default_speaker = default_speaker
        self._sample_rate = next(iter(rates))

    def sample_rate(self) -> int:
        return self._sample_rate

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        """ABC entry point — routes to the default speaker.

        Preserves the existing single-voice code path so today's Session
        (with the flag off) keeps working unchanged.
        """
        backend = self._voices[self._default_speaker]
        async for chunk in backend.synthesize(text, audio_id):
            yield chunk

    async def synthesize_for_speaker(
        self,
        text: str,
        audio_id: str,
        *,
        speaker: str,
    ) -> AsyncIterator[bytes]:
        """Phase 2 entry point — pick the speaker's voice."""
        backend = self._voices.get(speaker)
        if backend is None:
            log.warning(
                "MultiVoiceTTS: speaker %r not registered; using default %r",
                speaker,
                self._default_speaker,
            )
            backend = self._voices[self._default_speaker]
        async for chunk in backend.synthesize(text, audio_id):
            yield chunk

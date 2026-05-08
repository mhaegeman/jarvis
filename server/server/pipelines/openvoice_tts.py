"""OpenVoiceTTS — real TTS via OpenVoice (per-sentence synth, ~100ms PCM chunks)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from .interfaces import TTS

log = logging.getLogger(__name__)


@dataclass
class LoadedOpenVoice:
    """Bundle of OpenVoice singletons cached per (path, device, speaker_wav).

    `target_se` is `None` when no `JARVIS_SPEAKER_WAV` is configured;
    `synthesize()` then skips the tone-color conversion step and uses the
    default English speaker directly.
    """

    tts_model: Any  # api.BaseSpeakerTTS
    tone_color_converter: Any  # api.ToneColorConverter
    en_source_se: Any  # torch.Tensor
    target_se: Any | None  # torch.Tensor | None
    sample_rate: int


# Module-level cache keyed by the resolved (path, device, speaker_wav) tuple.
_loaded_cache: dict[tuple[str, str, str | None], LoadedOpenVoice] = {}


def _default_loader(
    openvoice_path: str, device: str, speaker_wav: str | None
) -> LoadedOpenVoice:
    """Lazy import + cached construction of OpenVoice models. See Task 8."""
    raise NotImplementedError("populated in Task 8")


class OpenVoiceTTS(TTS):
    def __init__(
        self,
        *,
        openvoice_path: str = "~/OpenVoice",
        device: str = "cpu",
        speaker_wav: str | None = None,
        loader: Callable[[str, str, str | None], LoadedOpenVoice] | None = None,
    ) -> None:
        self._path = openvoice_path
        self._device = device
        self._speaker_wav = speaker_wav
        self._loader = loader or _default_loader
        self._loaded: LoadedOpenVoice | None = None

    def _ensure_loaded(self) -> LoadedOpenVoice:
        if self._loaded is None:
            self._loaded = self._loader(self._path, self._device, self._speaker_wav)
        return self._loaded

    def sample_rate(self) -> int:
        return self._ensure_loaded().sample_rate

    async def synthesize(self, text: str, audio_id: str) -> AsyncIterator[bytes]:
        # Implemented in Task 3; yields nothing for now so the file imports.
        if False:  # pragma: no cover
            yield b""
        return

"""OpenVoiceTTS — real TTS via OpenVoice (per-sentence synth, ~100ms PCM chunks)."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

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


# Module-level singleton shared across WebSocket connections; populated by
# `_default_loader` (the production code path) and bypassed by tests that
# inject their own `loader` callable into `OpenVoiceTTS`.
_loaded_cache: dict[tuple[str, str, str | None], LoadedOpenVoice] = {}


def _default_loader(
    openvoice_path: str, device: str, speaker_wav: str | None
) -> LoadedOpenVoice:
    """Lazy import + cached construction of OpenVoice models.

    Not yet implemented — tests pass an injected `loader` instead. The
    production body (sys.path injection + checkpoint loading + cache
    write) lands in a follow-up commit.
    """
    raise NotImplementedError(
        "Real OpenVoice model loading is not yet implemented. "
        "Pass the `loader` keyword to OpenVoiceTTS for unit tests."
    )


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
        loaded = self._ensure_loaded()
        pcm = await asyncio.to_thread(self._synth_one, loaded, text)
        if not pcm:
            return
        # 100 ms window × 2 bytes per Int16 sample = the chunk size in bytes.
        chunk_bytes = int(loaded.sample_rate * 0.1) * 2
        for i in range(0, len(pcm), chunk_bytes):
            yield pcm[i : i + chunk_bytes]

    def _synth_one(self, loaded: LoadedOpenVoice, text: str) -> bytes:
        import torch  # type: ignore[import-not-found]

        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        mark = loaded.tts_model.language_marks.get("english", None)
        wrapped = f"[{mark}]{text}[{mark}]"
        stn = loaded.tts_model.get_text(wrapped, loaded.tts_model.hps, False)
        with torch.no_grad():
            x = stn.unsqueeze(0).to(loaded.tts_model.device)
            x_len = torch.LongTensor([stn.size(0)]).to(loaded.tts_model.device)
            sid = torch.LongTensor(
                [loaded.tts_model.hps.speakers["default"]]
            ).to(loaded.tts_model.device)
            # OpenVoice infer() returns (audio_tensor, ...) where audio_tensor
            # has shape [1, 1, T]; [0][0, 0] extracts the waveform per the
            # upstream speech_text_speech.py example.
            audio = loaded.tts_model.model.infer(
                x, x_len, sid=sid, noise_scale=0.667, noise_scale_w=0.6
            )[0][0, 0].data.cpu().float().numpy()
            if loaded.target_se is not None:
                audio = loaded.tone_color_converter.convert_from_tensor(
                    audio=audio, src_se=loaded.en_source_se, tgt_se=loaded.target_se
                )
        clipped = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
        return clipped.tobytes()

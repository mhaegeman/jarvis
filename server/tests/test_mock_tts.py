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

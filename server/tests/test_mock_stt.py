"""Tests for the Phase 1 mock STT."""

from collections.abc import AsyncIterator

import pytest

from server.pipelines.mock_stt import MockSTT


async def _audio(chunks: list[bytes]) -> AsyncIterator[bytes]:
    for c in chunks:
        yield c


@pytest.mark.asyncio
async def test_final_returns_canned_text() -> None:
    stt = MockSTT(canned_final="Brief me on today.")
    out = await stt.final(_audio([b"\x00" * 1024]))
    assert out == "Brief me on today."


@pytest.mark.asyncio
async def test_partials_emit_progressive_prefixes_during_audio() -> None:
    stt = MockSTT(canned_final="Hello world how are you")
    seen: list[str] = []
    async for p in stt.partials(_audio([b"\x00" * 1024 for _ in range(5)])):
        seen.append(p)
    assert len(seen) >= 1
    for i in range(1, len(seen)):
        assert seen[i].startswith(seen[i - 1]) or seen[i] == seen[i - 1]


@pytest.mark.asyncio
async def test_default_canned_when_unset() -> None:
    stt = MockSTT()
    out = await stt.final(_audio([b""]))
    assert isinstance(out, str)
    assert len(out) > 0

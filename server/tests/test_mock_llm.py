"""Tests for the Phase 1 mock LLM."""

import pytest

from server.pipelines.mock_llm import MockLLM


@pytest.mark.asyncio
async def test_picks_scenario_by_keyword_and_streams_reply() -> None:
    llm = MockLLM(token_delay_ms=0)
    history: list[dict[str, str]] = []
    seen = ""
    async for delta in llm.stream(history, "Brief me on today"):
        seen += delta
    assert "interview" in seen.lower() or "morning" in seen.lower()


@pytest.mark.asyncio
async def test_falls_back_to_default_on_no_keyword_match() -> None:
    llm = MockLLM(token_delay_ms=0)
    seen = ""
    async for delta in llm.stream([], "qzx"):
        seen += delta
    assert "not sure" in seen.lower() or "listening" in seen.lower()


@pytest.mark.asyncio
async def test_streams_in_multiple_deltas() -> None:
    llm = MockLLM(token_delay_ms=0)
    deltas = [d async for d in llm.stream([], "Brief me")]
    assert len(deltas) > 1


@pytest.mark.asyncio
async def test_history_is_not_mutated_by_llm() -> None:
    llm = MockLLM(token_delay_ms=0)
    history = [{"role": "user", "content": "hi"}]
    snapshot = list(history)
    _ = [d async for d in llm.stream(history, "Brief me")]
    assert history == snapshot

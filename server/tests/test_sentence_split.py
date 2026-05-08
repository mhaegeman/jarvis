"""Tests for the streaming sentence splitter."""

from collections.abc import AsyncIterator

import pytest

from server.pipelines.sentence_split import split_sentences_stream


async def _stream(parts: list[str]) -> AsyncIterator[str]:
    for p in parts:
        yield p


@pytest.mark.asyncio
async def test_single_sentence() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Hello world."]))]
    assert out == ["Hello world."]


@pytest.mark.asyncio
async def test_two_sentences_split_on_period_space() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Hi. ", "There."]))]
    assert out == ["Hi.", "There."]


@pytest.mark.asyncio
async def test_question_and_exclamation() -> None:
    out = [s async for s in split_sentences_stream(_stream(["What? ", "Wow!"]))]
    assert out == ["What?", "Wow!"]


@pytest.mark.asyncio
async def test_no_terminal_punctuation_flushes_at_end() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Half a sentence"]))]
    assert out == ["Half a sentence"]


@pytest.mark.asyncio
async def test_abbreviation_does_not_split() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Mr. Smith arrived. ", "Done."]))]
    assert out == ["Mr. Smith arrived.", "Done."]


@pytest.mark.asyncio
async def test_ellipsis_treated_as_one() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Hmm... ", "Yes."]))]
    assert out == ["Hmm...", "Yes."]


@pytest.mark.asyncio
async def test_chunks_arriving_mid_word() -> None:
    out = [s async for s in split_sentences_stream(_stream(["He", "llo. ", "Wo", "rld."]))]
    assert out == ["Hello.", "World."]


@pytest.mark.asyncio
async def test_empty_input() -> None:
    out = [s async for s in split_sentences_stream(_stream([]))]
    assert out == []


@pytest.mark.asyncio
async def test_whitespace_only_does_not_emit() -> None:
    out = [s async for s in split_sentences_stream(_stream(["   ", "\n"]))]
    assert out == []


@pytest.mark.asyncio
async def test_trailing_whitespace_trimmed() -> None:
    out = [s async for s in split_sentences_stream(_stream(["Hi.    "]))]
    assert out == ["Hi."]

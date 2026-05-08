"""Streaming sentence splitter — buffers tokens, emits complete sentences."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator

# Abbreviations that look like sentence-enders but aren't.
_ABBREVIATIONS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "mt",
        "st",
        "jr",
        "sr",
        "vs",
        "etc",
        "ie",
        "eg",
        "no",
        "fig",
        "vol",
    }
)


def _is_real_boundary(buf: str, punct_end: int) -> bool:
    """Given buf[i] in .!? at position punct_end-1 (i.e. after the punct run),
    return False if the immediately preceding word is a known abbreviation.
    """
    j = punct_end - 1
    while j >= 0 and buf[j] in ".!?":
        j -= 1
    word_end = j + 1
    word_start = word_end
    while word_start > 0 and buf[word_start - 1].isalnum():
        word_start -= 1
    word = buf[word_start:word_end].lower()
    return word not in _ABBREVIATIONS


async def split_sentences_stream(tokens: AsyncIterable[str]) -> AsyncIterator[str]:
    """Consume token deltas, yield complete sentences as boundaries are crossed.

    A boundary is `[.!?]+` followed by whitespace OR end of stream. Abbreviations
    followed by `.` do not count as boundaries.
    """
    buf = ""
    async for chunk in tokens:
        buf += chunk
        i = 0
        last_emit = 0
        while i < len(buf):
            if buf[i] in ".!?":
                # Walk through the punctuation run.
                punct_end = i
                while punct_end < len(buf) and buf[punct_end] in ".!?":
                    punct_end += 1
                if punct_end < len(buf):
                    if buf[punct_end].isspace():
                        # Boundary candidate.
                        if _is_real_boundary(buf, punct_end):
                            sentence = buf[last_emit:punct_end].strip()
                            if sentence:
                                yield sentence
                            ws_end = punct_end
                            while ws_end < len(buf) and buf[ws_end].isspace():
                                ws_end += 1
                            last_emit = ws_end
                            i = ws_end
                            continue
                        # Fake boundary (abbreviation): skip past it.
                        i = punct_end
                        continue
                    # Punct followed by non-space (e.g. "v1.0"): not a boundary.
                    i = punct_end
                    continue
                # End of buffer reached during/right after punct run; wait for more.
                break
            i += 1
        buf = buf[last_emit:]

    tail = buf.strip()
    if tail:
        yield tail

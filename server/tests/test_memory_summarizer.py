"""Summarizer tests with a mocked AsyncAnthropic client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from server.memory.summarizer import ClaudeSummarizer
from server.memory.types import Turn


def _turns(*pairs: tuple[str, str]) -> list[Turn]:
    return [
        Turn(id=i + 1, session_id="s", ts="2026-05-08T10:00:00Z", role=role, content=content)
        for i, (role, content) in enumerate(pairs)
    ]


def _mock_client_returning(text: str) -> Any:
    """Build a MagicMock whose messages.create returns a faux Message with the given text."""
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    client.messages.create = AsyncMock(return_value=msg)
    return client


async def test_refresh_recent_summary_uses_haiku() -> None:
    client = _mock_client_returning("Recent summary text.")
    s = ClaudeSummarizer(client=client, model="claude-haiku-4-5-20251001")
    out = await s.refresh_recent_summary(_turns(("user", "hi"), ("assistant", "hello")))
    assert out == "Recent summary text."
    args, kwargs = client.messages.create.call_args
    assert kwargs["model"] == "claude-haiku-4-5-20251001"


async def test_summarize_session_returns_text() -> None:
    client = _mock_client_returning("We talked about deploys.")
    s = ClaudeSummarizer(client=client)
    out = await s.summarize_session(_turns(("user", "deploys?"), ("assistant", "Friday.")))
    assert out == "We talked about deploys."


async def test_extract_facts_parses_json_list() -> None:
    client = _mock_client_returning('[{"key": "lang", "value": "TS"}, {"key": "city", "value": "BRU"}]')
    s = ClaudeSummarizer(client=client)
    facts = await s.extract_facts(_turns(("user", "I use TS in BRU")))
    assert len(facts) == 2
    assert facts[0].key == "lang" and facts[0].value == "TS"


async def test_extract_facts_returns_empty_on_malformed_json() -> None:
    client = _mock_client_returning("not even close to json")
    s = ClaudeSummarizer(client=client)
    assert await s.extract_facts(_turns(("user", "hi"))) == []


async def test_extract_facts_returns_empty_on_empty_list() -> None:
    client = _mock_client_returning("[]")
    s = ClaudeSummarizer(client=client)
    assert await s.extract_facts(_turns(("user", "hi"))) == []

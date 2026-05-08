"""Unit tests for ClaudeLLM (v0.2 α)."""

from __future__ import annotations

import pytest

from server.pipelines.claude_llm import PREFIX_MAP, parse_prefix


HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-7"


class TestParsePrefix:
    def test_no_prefix_returns_default(self):
        assert parse_prefix("How's the weather", default=HAIKU) == (HAIKU, "How's the weather")

    def test_sonnet_prefix(self):
        assert parse_prefix("/sonnet Explain entanglement", default=HAIKU) == (
            SONNET,
            "Explain entanglement",
        )

    def test_opus_prefix(self):
        assert parse_prefix("/opus Design X", default=HAIKU) == (OPUS, "Design X")

    def test_haiku_prefix_explicit(self):
        assert parse_prefix("/haiku Quick question", default=HAIKU) == (
            HAIKU,
            "Quick question",
        )

    def test_unknown_prefix_passes_through(self):
        # Unknown slash-prefix is not stripped; full text routed to default.
        assert parse_prefix("/unknown foo", default=HAIKU) == (HAIKU, "/unknown foo")

    def test_prefix_with_extra_whitespace(self):
        # Multiple spaces between prefix and content collapse.
        assert parse_prefix("/sonnet   hi there", default=HAIKU) == (SONNET, "hi there")

    def test_empty_content_after_prefix(self):
        # Empty content is passed through; the API will 400, surfacing via §8.2.
        assert parse_prefix("/sonnet", default=HAIKU) == (SONNET, "")

    def test_prefix_map_keys(self):
        assert set(PREFIX_MAP.keys()) == {"/haiku", "/sonnet", "/opus"}

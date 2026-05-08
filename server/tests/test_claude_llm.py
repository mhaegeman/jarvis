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


from server.pipelines.claude_llm import JARVIS_SYSTEM_PROMPT, max_tokens_for


class TestMaxTokensFor:
    def test_haiku_uses_base(self):
        assert max_tokens_for(HAIKU, base=1024) == 1024

    def test_sonnet_doubles_base(self):
        assert max_tokens_for(SONNET, base=1024) == 2048

    def test_opus_quadruples_base(self):
        assert max_tokens_for(OPUS, base=1024) == 4096

    def test_unknown_model_uses_base(self):
        # Defensive: never crash on an unfamiliar id.
        assert max_tokens_for("claude-future-99", base=1024) == 1024

    def test_scales_with_base(self):
        assert max_tokens_for(SONNET, base=512) == 1024
        assert max_tokens_for(OPUS, base=512) == 2048


class TestSystemPrompt:
    def test_addresses_max_not_maxime(self):
        assert "Max" in JARVIS_SYSTEM_PROMPT
        assert "Maxime" not in JARVIS_SYSTEM_PROMPT

    def test_voice_friendly_rules_present(self):
        # Spec §6 requires voice-friendly guidance.
        assert "spoken aloud" in JARVIS_SYSTEM_PROMPT
        assert "no markdown" in JARVIS_SYSTEM_PROMPT.lower() or "plain prose" in JARVIS_SYSTEM_PROMPT.lower()

"""Tests for the LLM factory in main.py."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from server.main import _build_llm, _resolve_device
from server.pipelines.claude_llm import ClaudeLLM
from server.pipelines.mock_llm import MockLLM


class TestBuildLLM:
    def test_mock_returns_mock_llm(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.model_name", "mock")
        llm = _build_llm()
        assert isinstance(llm, MockLLM)

    def test_claude_haiku_returns_claude_llm_when_key_set(self, monkeypatch):
        monkeypatch.setattr(
            "server.main.settings.anthropic_api_key", SecretStr("sk-ant-test")
        )
        monkeypatch.setattr("server.main.settings.model_name", "claude-haiku-4-5")
        llm = _build_llm()
        assert isinstance(llm, ClaudeLLM)

    def test_claude_without_api_key_raises(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.anthropic_api_key", None)
        monkeypatch.setattr("server.main.settings.model_name", "claude-haiku-4-5")
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            _build_llm()

    def test_unknown_model_name_raises(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.model_name", "gpt-99")
        with pytest.raises(ValueError, match="JARVIS_MODEL_NAME"):
            _build_llm()


class TestResolveDevice:
    def test_explicit_cpu(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.device", "cpu")
        assert _resolve_device() == "cpu"

    def test_explicit_cuda(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.device", "cuda")
        assert _resolve_device() == "cuda"

    def test_explicit_mps(self, monkeypatch):
        monkeypatch.setattr("server.main.settings.device", "mps")
        assert _resolve_device() == "mps"

    def test_auto_without_torch_returns_cpu(self, monkeypatch):
        """When torch is not importable, auto resolves to cpu."""
        import sys
        monkeypatch.setattr("server.main.settings.device", "auto")
        # Block the import of torch within _resolve_device.
        monkeypatch.setitem(sys.modules, "torch", None)
        assert _resolve_device() == "cpu"

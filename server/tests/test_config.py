"""Settings defaults — guard against accidental drift."""

from __future__ import annotations

from server.config import Settings


class TestSTTSettings:
    def test_stt_engine_defaults_to_auto(self, monkeypatch):
        monkeypatch.delenv("JARVIS_STT_ENGINE", raising=False)
        s = Settings()
        assert s.stt_engine == "auto"

    def test_whisper_model_default(self, monkeypatch):
        monkeypatch.delenv("JARVIS_WHISPER_MODEL", raising=False)
        s = Settings()
        assert s.whisper_model == "base.en"

    def test_device_defaults_to_auto(self, monkeypatch):
        monkeypatch.delenv("JARVIS_DEVICE", raising=False)
        s = Settings()
        assert s.device == "auto"

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("JARVIS_STT_ENGINE", "whisper")
        monkeypatch.setenv("JARVIS_WHISPER_MODEL", "small.en")
        monkeypatch.setenv("JARVIS_DEVICE", "cuda")
        s = Settings()
        assert s.stt_engine == "whisper"
        assert s.whisper_model == "small.en"
        assert s.device == "cuda"

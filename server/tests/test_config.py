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


class TestTTSSettings:
    def test_tts_engine_defaults_to_auto(self, monkeypatch):
        monkeypatch.delenv("JARVIS_TTS_ENGINE", raising=False)
        s = Settings()
        assert s.tts_engine == "auto"

    def test_openvoice_path_default(self, monkeypatch):
        monkeypatch.delenv("JARVIS_OPENVOICE_PATH", raising=False)
        s = Settings()
        assert s.openvoice_path == "~/OpenVoice"

    def test_speaker_wav_defaults_to_none(self, monkeypatch):
        monkeypatch.delenv("JARVIS_SPEAKER_WAV", raising=False)
        s = Settings()
        assert s.speaker_wav is None

    def test_tts_env_overrides(self, monkeypatch):
        monkeypatch.setenv("JARVIS_TTS_ENGINE", "openvoice")
        monkeypatch.setenv("JARVIS_OPENVOICE_PATH", "/opt/OpenVoice")
        monkeypatch.setenv("JARVIS_SPEAKER_WAV", "/tmp/voice.wav")
        s = Settings()
        assert s.tts_engine == "openvoice"
        assert s.openvoice_path == "/opt/OpenVoice"
        assert s.speaker_wav == "/tmp/voice.wav"

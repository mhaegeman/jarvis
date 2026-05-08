"""Environment-driven configuration (Phase 1: minimal)."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    ws_port: int = 8765
    log_level: str = "INFO"
    model_name: str = "mock"
    model_context_max: int = 200000
    llm_max_tokens: int = 1024

    # validation_alias bypasses env_prefix so this loads from ANTHROPIC_API_KEY
    # (the SDK's standard convention) in either .env or the process environment.
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias="ANTHROPIC_API_KEY"
    )

    # STT pipeline selection.
    stt_engine: str = "auto"  # auto | mock | whisper
    whisper_model: str = "base.en"
    device: str = "auto"  # auto | cuda | mps | cpu


settings = Settings()

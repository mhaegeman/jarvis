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

    # Memory settings — aliases match the spec's env-var table.
    # JARVIS_MEMORY=off disables all memory; JARVIS_MEMORY_DB overrides the DB path.
    memory_enabled: bool = Field(default=True, validation_alias="JARVIS_MEMORY")
    memory_db_path: str = Field(
        default="server/data/memory.db", validation_alias="JARVIS_MEMORY_DB"
    )
    memory_resume_minutes: int = Field(default=30, validation_alias="JARVIS_MEMORY_RESUME_MIN")
    memory_refresh_turns: int = Field(default=5, validation_alias="JARVIS_MEMORY_REFRESH_TURNS")
    memory_recent_window: int = Field(default=20, validation_alias="JARVIS_MEMORY_RECENT_WINDOW")
    memory_facts_cap: int = Field(default=50, validation_alias="JARVIS_MEMORY_FACTS_CAP")
    memory_model: str = Field(
        default="claude-haiku-4-5-20251001", validation_alias="JARVIS_MEMORY_MODEL"
    )

    # validation_alias bypasses env_prefix so this loads from ANTHROPIC_API_KEY
    # (the SDK's standard convention) in either .env or the process environment.
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias="ANTHROPIC_API_KEY"
    )


settings = Settings()

"""Environment-driven configuration (Phase 1: minimal)."""

from __future__ import annotations

from typing import Literal

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
    # Default is cwd-relative: launched per docs as `cd server && uvicorn server.main:app`,
    # this lands at <repo>/server/data/memory.db, which the repo .gitignore covers.
    memory_enabled: bool = Field(default=True, validation_alias="JARVIS_MEMORY")
    memory_db_path: str = Field(
        default="data/memory.db", validation_alias="JARVIS_MEMORY_DB"
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

    # STT pipeline selection.
    stt_engine: str = "auto"  # auto | mock | whisper
    whisper_model: str = "base.en"
    device: str = "auto"  # auto | cuda | mps | cpu

    # TTS pipeline selection.
    tts_engine: str = "auto"  # auto | mock | openvoice | edge
    openvoice_path: str = "~/OpenVoice"
    speaker_wav: str | None = None
    tts_voice: str = "en-US-ChristopherNeural"

    # Auth — passphrase hash (argon2id). Generate with:
    #   python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('yourphrase'))"
    passphrase_hash: str | None = Field(default=None, validation_alias="JARVIS_PASSPHRASE_HASH")

    # ─── Multi-model support (Phase 5) ─────────────────────────────────
    # Phase 5: default is now true — the full multi-persona path runs out of
    # the box. Set JARVIS_PERSONAS_ENABLED=false to fall back to the
    # single-Jarvis path (offline dev, CI, demos, or deploys without
    # OPENAI_API_KEY).
    personas_enabled: bool = True

    # OpenAI credentials — required for Pepper chat and Codex CLI agent.
    # validation_alias bypasses the JARVIS_ prefix to follow the OpenAI
    # SDK's standard convention, mirroring how ANTHROPIC_API_KEY is loaded.
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias="OPENAI_API_KEY"
    )
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")

    # Per-persona default tier ("fast" / "balanced" / "deep").
    tier_default_jarvis: Literal["fast", "balanced", "deep"] = "fast"
    tier_default_pepper: Literal["fast", "balanced", "deep"] = "fast"

    # The router model — cheap, used for every non-fast-path turn.
    dispatcher_model: str = "claude-haiku-4-5"

    # Persona dynamics. "subtle" = the quiet-warmth clause is appended to
    # each persona's system prompt; "off" strips it entirely.
    persona_warmth: Literal["subtle", "off"] = "subtle"

    # Learning loop cadence — profile refresh every N turns.
    persona_refresh_turns: int = 20

    # Learning loop master switch. validation_alias to keep the env-var
    # name consistent with JARVIS_MEMORY (the existing pattern).
    learning_enabled: bool = Field(default=True, validation_alias="JARVIS_LEARNING")

    # Codex CLI agent (used in Phase 3 — declared here so Phase 1 tests pass).
    codex_cli_path: str | None = None
    codex_approval: Literal["auto-low", "manual", "never"] = "auto-low"
    codex_sandbox: Literal["read-only", "workspace-write", "full-access"] = "workspace-write"
    codex_workdir: str | None = None


settings = Settings()

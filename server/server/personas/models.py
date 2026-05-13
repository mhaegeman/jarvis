"""Persona / ModelTier / AgentBackend pydantic types (spec §4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, PositiveInt, model_validator


PersonaId = Literal["jarvis", "pepper"]
Provider = Literal["anthropic", "openai"]
TierName = Literal["fast", "balanced", "deep"]
ApprovalMode = Literal["auto-low", "manual", "never"]
Sandbox = Literal["read-only", "workspace-write", "full-access"]


class ModelTier(BaseModel):
    """One model tier for a persona ('fast' / 'balanced' / 'deep')."""

    model_config = {"extra": "forbid"}

    name: TierName
    model_id: str = Field(min_length=1, max_length=80)
    max_tokens: PositiveInt


class AgentBackend(BaseModel):
    """Optional agentic backend (Codex CLI for Pepper, in v1)."""

    model_config = {"extra": "forbid"}

    kind: Literal["codex_cli"]
    binary: str = Field(min_length=1)
    workdir: str = Field(min_length=1)
    approval_mode: ApprovalMode
    sandbox: Sandbox


class Persona(BaseModel):
    """The durable identity of a colleague.

    `specialty_profile` is the live, ~200-word blurb the Dispatcher reads
    on every turn. Refreshed by the Profile Refresher (Phase 5); seeded
    from `seed.py` at first launch.
    """

    model_config = {"extra": "forbid"}

    id: PersonaId
    display_name: str = Field(min_length=1, max_length=40)
    provider: Provider
    voice: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=10, max_length=8000)
    tiers: dict[str, ModelTier]
    agent: AgentBackend | None = None
    # Cap is ~1800 chars (≈250 words) to bound Dispatcher prompt cost.
    specialty_profile: str = Field(min_length=1, max_length=1800)

    @model_validator(mode="after")
    def _require_three_tiers(self) -> "Persona":
        expected = {"fast", "balanced", "deep"}
        missing = expected - set(self.tiers.keys())
        if missing:
            raise ValueError(f"persona missing tiers: {sorted(missing)}")
        for name, tier in self.tiers.items():
            if tier.name != name:
                raise ValueError(
                    f"tier key {name!r} does not match ModelTier.name {tier.name!r}"
                )
        return self

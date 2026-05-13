"""PersonaRegistry — owns the live persona instances.

Spec anchors: §4 (model + lifecycle), §10 (config). Phase 1 covers
construction + lookup + availability. Phase 5 will add persistent
storage of the live specialty_profile in memory.db (see schema in §8.1).
"""

from __future__ import annotations

import shutil
from typing import Literal

from server.config import Settings
from server.personas.models import Persona
from server.personas.seed import Warmth, build_jarvis_seed, build_pepper_seed

PersonaId = Literal["jarvis", "pepper"]


class PersonaUnavailableError(LookupError):
    """Raised when a persona is requested but its provider key is missing."""


class PersonaRegistry:
    """In-memory registry of persona instances.

    Personas are constructed once (either at server startup or on first use)
    from seed text + config flags. The Profile Refresher in Phase 5 will
    update `specialty_profile` in place via `update_profile()`.
    """

    def __init__(self, personas: dict[PersonaId, Persona]) -> None:
        self._personas: dict[PersonaId, Persona] = dict(personas)

    @classmethod
    def build(
        cls,
        *,
        warmth: Warmth,
        anthropic_available: bool,
        openai_available: bool,
        codex_binary: str | None,
        codex_workdir: str | None,
    ) -> PersonaRegistry:
        """Construct a registry from feature flags + resolved Codex paths.

        A persona is registered only when its provider's API key is
        available. Missing keys → the persona is omitted; callers should
        check `is_available()` before `get()`.
        """
        out: dict[PersonaId, Persona] = {}
        if anthropic_available:
            out["jarvis"] = build_jarvis_seed(warmth=warmth)
        if openai_available:
            out["pepper"] = build_pepper_seed(
                warmth=warmth,
                codex_binary=codex_binary,
                workdir=codex_workdir,
            )
        return cls(out)

    def get(self, persona_id: PersonaId) -> Persona:
        try:
            return self._personas[persona_id]
        except KeyError as exc:
            raise PersonaUnavailableError(
                f"persona {persona_id!r} is not registered "
                "(provider API key likely missing)"
            ) from exc

    def is_available(self, persona_id: PersonaId) -> bool:
        return persona_id in self._personas

    def available_ids(self) -> list[PersonaId]:
        # Deterministic order: jarvis first, pepper second
        order: list[PersonaId] = ["jarvis", "pepper"]
        return [pid for pid in order if pid in self._personas]

    def update_profile(self, persona_id: PersonaId, new_profile: str) -> None:
        """Used by the Phase 5 Profile Refresher to overwrite the live blurb."""
        persona = self.get(persona_id)
        # Pydantic models are frozen by default in v2 only when configured;
        # ours are not. Replace via model_copy(update=...) to preserve validation.
        self._personas[persona_id] = persona.model_copy(
            update={"specialty_profile": new_profile}
        )


def build_registry_from_settings(settings: Settings, codex_workdir: str | None) -> PersonaRegistry:
    """Helper that translates Settings → PersonaRegistry.

    Used by `main.py` lifespan once `JARVIS_PERSONAS_ENABLED=true` (Phase 2).
    Kept here for Phase 1 so the construction logic is testable independently.
    """
    anthropic_available = settings.anthropic_api_key is not None
    openai_available = settings.openai_api_key is not None

    # Codex binary resolution: explicit env var beats $PATH, both optional.
    codex_binary: str | None = settings.codex_cli_path or shutil.which("codex")

    return PersonaRegistry.build(
        warmth=settings.persona_warmth,
        anthropic_available=anthropic_available,
        openai_available=openai_available,
        codex_binary=codex_binary,
        codex_workdir=codex_workdir,
    )

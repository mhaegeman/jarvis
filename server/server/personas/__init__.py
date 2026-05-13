"""Persona definitions: Jarvis (Claude) + Pepper (OpenAI).

Phase 1 ships the data model, seed text, and registry. Subsequent phases
wire personas into the DialogManager (Phase 2) and CodexAgent (Phase 3).
"""

from server.personas.models import AgentBackend, ModelTier, Persona
from server.personas.seed import build_jarvis_seed, build_pepper_seed

__all__ = [
    "AgentBackend",
    "ModelTier",
    "Persona",
    "build_jarvis_seed",
    "build_pepper_seed",
]

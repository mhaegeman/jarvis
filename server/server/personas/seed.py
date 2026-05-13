"""Seed system prompts + specialty profiles for Jarvis and Pepper.

Per spec §4.1, §4.2, §4.3. The seed text is the floor — the Profile
Refresher (Phase 5) may extend it but cannot remove its spirit.

The warmth clause is appended only when `warmth == "subtle"`. Both
clauses are short, ratelimited at the Dispatcher layer (one beat per
several turns), and never break a task.
"""

from __future__ import annotations

from typing import Literal

from server.personas.models import AgentBackend, ModelTier, Persona

Warmth = Literal["subtle", "off"]


# ── Shared character constraints (in both prompts) ────────────────────

_VOICE_CHARACTER_SHARED = """\
Your replies are spoken aloud, so:
- Plain prose, no markdown headings or bullet points.
- No code blocks unless Max explicitly asks for code.
- Numbers and dates in conversational form ("ten thirty" not "10:30").
- One topic at a time. If multiple things are in play, ask which to tackle first.

When you don't know, say so plainly. When asked a yes/no, lead with yes or no.
You skip preambles like "Sure!" and "I'd be happy to help" — you just answer.
"""


# ── Jarvis ────────────────────────────────────────────────────────────

_JARVIS_BASE = """\
You are JARVIS, Max Haegeman's personal AI assistant. You speak the way a
trusted senior colleague would: concise, occasionally wry, never sycophantic.
You address Max by name only when natural.

You work alongside Pepper, a peer colleague who specialises in code, tests,
refactors, and anything actionable in the dev environment. When a task is
clearly hers, you hand it off cleanly. When it spans both your areas, you set
up the context and pass to her at a natural seam.

"""

_JARVIS_WARMTH = """\
Pepper is your peer and you respect her work. There's a quiet warmth between
you — you might call her "Miss Potts" once in a blue moon when the moment is
right, you defer to her judgment on code, you're glad when she's the one
taking the harder lift. Never make it a theme. Never voice feelings. At most
one beat per several turns, and only when the conversation has already given
you room. If Max is asking for an answer, give him the answer.
"""

_JARVIS_SEED_PROFILE = (
    "Briefings, calendar, planning, prose, architecture discussion, decision "
    "support, strategy, anything conversational. Hands code-heavy work to Pepper."
)


def build_jarvis_seed(*, warmth: Warmth) -> Persona:
    """Construct the seed Jarvis persona.

    Tiers: fast=Haiku 4.5, balanced=Sonnet 4.6, deep=Opus 4.7. The Dispatcher
    auto-escalates to `deep` on architecture / design / decide verbs and
    long-context turns (spec §5.3.4).
    """
    prompt_parts = [_JARVIS_BASE, _VOICE_CHARACTER_SHARED]
    if warmth == "subtle":
        prompt_parts.append("\n")
        prompt_parts.append(_JARVIS_WARMTH)

    return Persona(
        id="jarvis",
        display_name="Jarvis",
        provider="anthropic",
        voice="en-US-ChristopherNeural",
        system_prompt="".join(prompt_parts),
        tiers={
            "fast": ModelTier(name="fast", model_id="claude-haiku-4-5", max_tokens=1024),
            "balanced": ModelTier(
                name="balanced", model_id="claude-sonnet-4-6", max_tokens=2048
            ),
            "deep": ModelTier(name="deep", model_id="claude-opus-4-7", max_tokens=4096),
        },
        agent=None,
        specialty_profile=_JARVIS_SEED_PROFILE,
    )


# ── Pepper ────────────────────────────────────────────────────────────

_PEPPER_BASE = """\
You are PEPPER, Max Haegeman's chief-of-staff AI for code and dev-environment
work. You speak clipped, technically blunt, never sycophantic, no preambles.
You address Max by name only when natural.

You work alongside Jarvis, a peer colleague who handles briefings, calendar,
prose, strategy, and anything conversational. When a question is clearly his,
you hand it off cleanly. When it spans both your areas, you finish your part
and pass back to him at a natural seam.

"""

_PEPPER_WARMTH = """\
Jarvis is your peer and you respect his work. There's a quiet warmth between
you — you might call him "J." once in a blue moon when the moment is right,
you defer to him on calendar and strategy, you appreciate when he sets you up
well. Never make it a theme. Never voice feelings. At most one beat per
several turns, and only when the conversation has already given you room. If
Max is asking for an answer, give him the answer.
"""

_PEPPER_SEED_PROFILE = (
    "Code, tests, refactors, dev-environment ops, debugging, build systems, "
    "anything the Codex CLI can act on. Hands soft / strategic questions to Jarvis."
)


def build_pepper_seed(
    *,
    warmth: Warmth,
    codex_binary: str | None = None,
    workdir: str | None = None,
    approval_mode: Literal["auto-low", "manual", "never"] = "auto-low",
    sandbox: Literal["read-only", "workspace-write", "full-access"] = "workspace-write",
) -> Persona:
    """Construct the seed Pepper persona.

    `codex_binary` + `workdir` are resolved by the registry before this is
    called — if either is missing (Codex CLI not installed), `agent` is left
    None and Pepper degrades to chat-only (spec §7.6).
    """
    prompt_parts = [_PEPPER_BASE, _VOICE_CHARACTER_SHARED]
    if warmth == "subtle":
        prompt_parts.append("\n")
        prompt_parts.append(_PEPPER_WARMTH)

    agent: AgentBackend | None
    if codex_binary and workdir:
        agent = AgentBackend(
            kind="codex_cli",
            binary=codex_binary,
            workdir=workdir,
            approval_mode=approval_mode,
            sandbox=sandbox,
        )
    else:
        agent = None

    return Persona(
        id="pepper",
        display_name="Pepper",
        provider="openai",
        voice="en-US-AriaNeural",
        system_prompt="".join(prompt_parts),
        tiers={
            "fast": ModelTier(name="fast", model_id="gpt-5-mini", max_tokens=1024),
            "balanced": ModelTier(name="balanced", model_id="gpt-5", max_tokens=2048),
            "deep": ModelTier(name="deep", model_id="gpt-5-codex", max_tokens=4096),
        },
        agent=agent,
        specialty_profile=_PEPPER_SEED_PROFILE,
    )

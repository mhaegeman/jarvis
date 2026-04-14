# jarvis — Project Instructions

## Project Overview

This repository is Maxime Haegeman's personal AI tooling workspace. It contains:
- `second-brain/` — A persistent LLM-maintained wiki (has its own `second-brain/CLAUDE.md`)
- Development of new AI-powered tools and experiments

---

## Exception: Second-Brain Ingestions

**When performing ingestion or wiki operations inside `second-brain/`, Superpowers workflow does NOT apply.**

The second-brain has its own defined processes in `second-brain/CLAUDE.md` that take full precedence:
- No brainstorming or spec phase needed for ingestion operations
- No plan document required for ingestion operations
- No TDD cycle for ingestion operations
- Follow `second-brain/CLAUDE.md` exclusively for all ingest, query, lint, and update operations

**All other development work** (new tools, features, scripts, experiments) in this repository MUST follow the Superpowers workflow below.

---

## Superpowers Workflow

This repository uses the Superpowers skills-based development workflow. Skills are defined in `.claude/skills/`. Read a skill by using `Read` on `.claude/skills/<skill-name>.md`.

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing (outside of second-brain ingestion), you ABSOLUTELY MUST read and follow the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This is not negotiable. This is not optional. You cannot rationalize your way out of this.
</EXTREMELY-IMPORTANT>

## Instruction Priority

1. **User's explicit instructions** (this file, direct requests) — highest priority
2. **Superpowers skills** (`.claude/skills/`) — override default behavior where they conflict
3. **Default system prompt** — lowest priority

## How to Access Skills

**In this repo:** Use the `Read` tool to read `.claude/skills/<skill-name>.md`. Follow the skill content directly once read.

Available skills:
- `brainstorming` — Before any feature, component, or behavior modification
- `writing-plans` — After spec approval, before touching code
- `executing-plans` — Execute a written plan in batch with checkpoints
- `subagent-driven-development` — Execute plan tasks with fresh subagents + two-stage review
- `test-driven-development` — During implementation (RED-GREEN-REFACTOR)
- `systematic-debugging` — Before proposing any fix for a bug or failure
- `verification-before-completion` — Before claiming work is complete
- `requesting-code-review` — After completing a task or feature
- `receiving-code-review` — When receiving review feedback
- `using-git-worktrees` — Before starting feature implementation
- `finishing-a-development-branch` — When implementation is complete
- `dispatching-parallel-agents` — When 2+ independent tasks can be parallelised
- `writing-skills` — When creating or modifying skills

## The Rule

**Read the relevant skill BEFORE any response or action.**

```
User message received
  → Is this a second-brain ingestion? → Yes → Follow second-brain/CLAUDE.md only
  → Might any skill apply? (even 1%)  → Yes → Read skill → Follow it exactly
  → Definitely not applicable         → Respond normally
```

## Skill Priority When Multiple Apply

1. **Process skills first** (brainstorming, debugging) — determine HOW to approach
2. **Implementation skills second** — guide execution

"Let's build X" → brainstorming first.
"Fix this bug" → systematic-debugging first.

## Red Flags — You Are Rationalizing

| Thought | Reality |
|---------|---------|
| "This is just a simple question" | Questions are tasks. Check for skills. |
| "I need more context first" | Skill check comes BEFORE clarifying questions. |
| "Let me explore the codebase first" | Skills tell you HOW to explore. Check first. |
| "This is too simple for a design" | Every project needs a design, however short. |
| "I already know the skill" | Skills evolve. Read current version. |
| "This doesn't count as a task" | Action = task. Check for skills. |
| "The skill is overkill" | Simple things become complex. Use it. |
| "This is a second-brain ingestion" | Is it really? Verify before skipping workflow. |

---

## Git Worktrees

Feature work should use isolated git worktrees. See `.claude/skills/using-git-worktrees.md`.

Worktrees directory: `.worktrees/` (project-local, gitignored)

## Docs Structure

- Specs: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Plans: `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`

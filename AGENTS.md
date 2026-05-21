# AGENTS.md — jarvis

Vendor-neutral instructions for any AI coding agent in this repo (Codex, Cursor, Aider, Claude Code, Jules, etc.). Read at session start.

Claude Code: also read `CLAUDE.md` for skill-loading mechanics. Rules here apply regardless.

---

## Project Overview

Maxime Haegeman's personal AI tooling workspace:

- `server/` — Python 3.12+ FastAPI backend (LLM, STT, TTS, memory, calendar)
- `web/` — Vite + TypeScript frontend (HUD)
- `second-brain/` — persistent LLM-maintained wiki w/ own rules (see `second-brain/AGENTS.md`)
- `prototypes/`, `docs/`, root scripts — experiments + tooling

---

## Build, Test, Run

Setup, env vars, e2e smoke test → `SETUP.md`. Daily commands:

```bash
# Backend (Python 3.12+, venv at server/.venv)
cd server && source .venv/bin/activate
pytest -q                                # tests (~54, mocked by default)
uvicorn server.main:app --port 8000      # dev server

# Frontend (Node 20+)
cd web
npm run test                             # tests
npm run dev                              # dev server (http://localhost:5173)
```

No top-level lint — per-subproject tooling is source of truth.

---

## Exception: Second-Brain Operations

For ingest/query/lint/update inside `second-brain/`, follow `second-brain/AGENTS.md` exclusively. Workflow below does NOT apply:

- No brainstorming/spec phase
- No plan document
- No TDD cycle

All other work (tools, features, scripts, experiments) → workflow below.

---

## Instruction Priority

1. **User's explicit instructions** (this file, direct requests) — highest
2. **Vendor-specific overrides** (e.g. `CLAUDE.md` for Claude Code) — agent mechanics on top
3. **Default agent behavior** — lowest

---

## Development Workflow

Skills-based workflow inspired by Superpowers. Intent applies to any agent:

1. **Brainstorm** before any feature/component/behavior change.
2. **Write plan** after spec approval, before code (`docs/superpowers/plans/YYYY-MM-DD-<feature>.md`).
3. **TDD** during implementation — RED → GREEN → REFACTOR.
4. **Systematic debugging** before any bug/failure fix (read error, form hypothesis, prove it, fix).
5. **Verify** before claiming complete (run tests, exercise feature, check regressions).
6. **Request review** after completing task/feature.

Agents w/ structured skill-loading (Claude Code via `.claude/skills/`) → consult those skill files; they encode same intent in detail. Other agents → follow spirit above, ask user when unsure.

---

## Git Worktrees

Feature work uses isolated git worktrees. Dir: `.worktrees/` (project-local, gitignored).

---

## Docs Structure

- Specs: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Plans: `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`

---

## Commit & Branch Conventions

- Develop on feature branch — never commit straight to `main`.
- One logical change per commit; descriptive subjects.
- Push only the branch asked to push.
- No PR unless user explicitly asks.

---

## Red Flags — You Are Rationalizing

| Thought | Reality |
|---------|---------|
| "Just a simple question" | Questions are tasks. Apply process. |
| "I need more context first" | Process check BEFORE clarifying questions. |
| "Let me explore codebase first" | Process tells you HOW to explore. Check first. |
| "Too simple for a design" | Every project needs a design, however short. |
| "Doesn't count as a task" | Action = task. Apply process. |
| "Workflow is overkill" | Simple things become complex. Use it. |
| "This is a second-brain operation" | Is it really? Verify before skipping. |

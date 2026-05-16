# AGENTS.md — jarvis

Vendor-neutral instructions for any AI coding agent working in this repo (Codex, Cursor, Aider, Claude Code, Jules, etc.). Read this file at the start of every session.

Claude Code users: also read `CLAUDE.md` for Claude-specific skill-loading mechanics. The rules in this file apply regardless.

---

## Project Overview

This repository is Maxime Haegeman's personal AI tooling workspace. It contains:

- `server/` — Python 3.12+ FastAPI backend (LLM, STT, TTS, memory, calendar)
- `web/` — Vite + TypeScript frontend (the HUD)
- `second-brain/` — A persistent LLM-maintained wiki with its own rules (see `second-brain/AGENTS.md`)
- `prototypes/`, `docs/`, root scripts — experiments and tooling

Full setup, env vars, and deployment are documented in `SETUP.md`.

---

## Build, Test, Run

Both the backend and frontend have their own toolchains. Run from repo root.

```bash
# Backend (Python 3.12+, venv at server/.venv)
cd server && source .venv/bin/activate
pip install -e ".[dev]"                 # first time only
pytest -q                                # run tests (~54 tests, all mocked by default)
uvicorn server.main:app --port 8000      # run dev server

# Frontend (Node 20+)
cd web
npm install                              # first time only
npm run test                             # run tests
npm run dev                              # run dev server (http://localhost:5173)
```

There is no top-level lint command — per-subproject tooling is the source of truth. See `SETUP.md` for the full environment matrix, env vars, and end-to-end smoke test.

---

## Exception: Second-Brain Operations

When performing ingestion, query, lint, or update operations inside `second-brain/`, follow `second-brain/AGENTS.md` exclusively. The development workflow below does NOT apply to those operations:

- No brainstorming or spec phase
- No plan document
- No TDD cycle

All other work in this repository — new tools, features, scripts, experiments — follows the workflow below.

---

## Instruction Priority

1. **User's explicit instructions** (this file, direct requests) — highest priority
2. **Vendor-specific overrides** (e.g. `CLAUDE.md` for Claude Code) — agent-specific mechanics layered on top
3. **Default agent behavior** — lowest priority

---

## Development Workflow

This repo uses a skills-based workflow inspired by Superpowers. The intent applies to any agent, regardless of how it loads guidance:

1. **Brainstorm** before any feature, component, or behavior modification.
2. **Write a plan** after spec approval, before touching code (file under `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`).
3. **TDD** during implementation — RED → GREEN → REFACTOR.
4. **Systematic debugging** before proposing any fix for a bug or failure (read the error, form a hypothesis, prove it, then fix).
5. **Verify** before claiming work is complete (run the tests, exercise the feature, check for regressions).
6. **Request review** after completing a task or feature.

Agents with structured skill-loading (Claude Code via `.claude/skills/`) should consult those skill files directly — they encode the same intent in more detail. Other agents should follow the spirit of the above and ask the user when unsure which step to apply.

---

## Git Worktrees

Feature work should use isolated git worktrees. Worktrees directory: `.worktrees/` (project-local, gitignored).

---

## Docs Structure

- Specs: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Plans: `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`

---

## Commit & Branch Conventions

- Develop on a feature branch — never commit straight to `main`.
- One logical change per commit; descriptive subject lines.
- Push only the branch you were asked to push to.
- Don't open a pull request unless the user explicitly asks.

---

## Red Flags — You Are Rationalizing

| Thought | Reality |
|---------|---------|
| "This is just a simple question" | Questions are tasks. Apply the process. |
| "I need more context first" | Process check comes BEFORE clarifying questions. |
| "Let me explore the codebase first" | The process tells you HOW to explore. Check first. |
| "This is too simple for a design" | Every project needs a design, however short. |
| "This doesn't count as a task" | Action = task. Apply the process. |
| "The workflow is overkill" | Simple things become complex. Use it. |
| "This is a second-brain operation" | Is it really? Verify before skipping the workflow. |

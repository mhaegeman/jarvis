# Jarvis Build · Live Status

> **Single source of truth.** Updated at every phase boundary and committed.
> Any agent resuming this project should read this file first.

**Last updated:** 2026-05-08 (spec-01 Task 2/22 complete)

---

## Current Phase
**spec-01-frontend-shell · implementation (inline mode)**

## Macro Progress

| # | Sub-spec | Brainstorm | Plan | Implement | Review | Verify | Merged |
|---|---|---|---|---|---|---|---|
| 0 | Umbrella architecture | ✅ committed | n/a | n/a | n/a | n/a | ✅ on main |
| 1 | spec-01-frontend-shell | ✅ committed | ✅ committed | ⏳ Task 2/22 done | ⬜ | ⬜ | ⬜ |
| 2 | spec-02-backend-streaming | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 3 | spec-03-integration | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 4 | spec-04-deploy-and-gate | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

Legend: ⬜ not started · ⏳ in progress · ✅ done

## Authority
- Architect (Maxime) has delegated v1 decision authority to the orchestrator.
- Orchestrator commits, dispatches subagents, and resolves design ambiguities autonomously.
- Architect is escalated to only when something genuinely "goes sideways" (out-of-scope, irreversible, or user-taste).

## Anchor docs
- Architecture: `docs/superpowers/specs/2026-05-07-jarvis-architecture.md`
- Multi-agent design: section 6 of architecture doc

## Last completed action
Spec-01 Task 2 done. Worktree `.worktrees/spec-01-frontend-shell` set up with Vite + TS scaffold and full toolchain (TS strict, ESLint flat config, Prettier, Vitest). All quality gates green.

### Toolchain deviations from plan (Node 18 environment)
The plan was authored assuming a modern Node 20+ env. Adapted on the fly:
- **Vite scaffold**: manual (create-vite v9 requires Node 20+).
- **ESLint**: pinned to v9 (flat config), v10 has Node 20+ formatter dep.
- **Vitest**: pinned to v2 (v4 uses rolldown which needs Node 20+).
- **TS composite config**: dropped `tsconfig.node.json` + project refs; `tsc --noEmit && vite build` is sufficient.
- **`web/.gitignore`**: must contain `!package.json` and `!package-lock.json` to negate the root repo's global `package*` ignore rule.

## Execution mode for spec-01
**Inline** via `executing-plans` skill (orchestrator runs each task in this session). Trade-off: chosen over subagent-driven for visibility/velocity given the user's emphasis on constant progress updates and the plan's high specificity (subagent reviews would add little marginal quality given TDD steps + tight specs).

Quality safeguards retained:
- TDD steps in every task
- After every group of 3-4 tasks: dispatch a fresh code-review subagent on the diff
- After Task 22: full verification + final code review

## Next action
Continue from Task 3 (shared types) → Task 6 (EventSource interface + mock skeleton). All four are pure TS with TDD; no install drama expected. Then checkpoint before Task 7 (UI assembly begins).

## Resume hint for future sessions
1. Read this file.
2. Read `docs/superpowers/plans/2026-05-07-frontend-shell.md`.
3. Check the worktree at `.worktrees/spec-01-frontend-shell`.
4. `cd` into the worktree and run `git log --oneline main..HEAD` to see what's been completed.
5. Look at the highest-numbered Task N already committed. Resume at Task N+1.

## Open blockers
None.

## Notes for future sessions
- Existing `speech_text_speech.py` is the legacy reference for the backend pipeline. Do **not** modify it; it is preserved until spec-02 supersedes it.
- Existing `prototypes/` are reference-only (4 HTML files + index). Do not modify; the production frontend lives in `web/`.
- `second-brain/` is governed by its own `CLAUDE.md` and is exempt from this workflow.
- Skills available: see `.claude/skills/`.

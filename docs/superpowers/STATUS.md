# Jarvis Build · Live Status

> **Single source of truth.** Updated at every phase boundary and committed.
> Any agent resuming this project should read this file first.

**Last updated:** 2026-05-08 (spec-02 brainstorm complete, planning next)

---

## Current Phase
**spec-02-backend-streaming · planning**

## Macro Progress

| # | Sub-spec | Brainstorm | Plan | Implement | Review | Verify | Merged |
|---|---|---|---|---|---|---|---|
| 0 | Umbrella architecture | ✅ committed | n/a | n/a | n/a | n/a | ✅ on main |
| 1 | spec-01-frontend-shell | ✅ committed | ✅ committed | ✅ 22/22 | ✅ subagent | ✅ 30/30 tests | ✅ merged 7a6abe1 |
| 2 | spec-02-backend-streaming | ✅ committed (5d4f31f) | ⏳ in progress | ⬜ | ⬜ | ⬜ | ⬜ |
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
**Spec-01 merged to `main` (commit 7a6abe1).** Code review by fresh subagent identified 7 important issues; all addressed before merge:
- AudioPanel HTML-escapes `mic.message` (XSS hardening)
- main.ts tracks open `audioId`s + `llm.end` so multi-sentence replies finish correctly
- mic stream stopped on transition out of `listening`
- MockEventSource `interrupt()` is idempotent for `llm.end`; clears scenario state
- Spec doc clarified that `AnalyserNode` is sufficient for spec-01 (vs `AudioWorklet` planned for spec-03 PCM streaming)

Worktree `.worktrees/spec-01-frontend-shell` removed. Branch `spec-01-frontend-shell` deleted.

### Toolchain deviations from plan (Node 18 environment) — applies to spec-02 too
The plan was authored assuming a modern Node 20+ env. Adapted on the fly:
- **Vite scaffold**: manual (create-vite v9 requires Node 20+).
- **ESLint**: pinned to v9 (flat config), v10 has Node 20+ formatter dep.
- **Vitest**: pinned to v2 (v4 uses rolldown which needs Node 20+).
- **TS composite config**: dropped `tsconfig.node.json` + project refs; `tsc --noEmit && vite build` is sufficient.
- **`web/.gitignore`**: must contain `!package.json` and `!package-lock.json` to negate the root repo's global `package*` ignore rule. Same will apply to `server/`.
- **Playwright e2e** requires `sudo npx playwright install-deps chromium` (system libs). Documented in `web/README.md`.

## Execution mode for spec-01
**Inline** via `executing-plans` skill (orchestrator runs each task in this session). Trade-off: chosen over subagent-driven for visibility/velocity given the user's emphasis on constant progress updates and the plan's high specificity (subagent reviews would add little marginal quality given TDD steps + tight specs).

Quality safeguards retained:
- TDD steps in every task
- After every group of 3-4 tasks: dispatch a fresh code-review subagent on the diff
- After Task 22: full verification + final code review

## Next action
Read `.claude/skills/writing-plans.md`, then write spec-02 implementation plan: `docs/superpowers/plans/2026-05-08-backend-streaming.md`. Self-review, commit. Then create worktree `.worktrees/spec-02-backend-streaming` and begin implementation.

### Implementation pre-requisites (will gate the impl phase)
The protocol layer, session orchestrator, and sentence splitter can all be built and tested with mock pipelines on this machine. The full pipeline acceptance criteria (§11.4–§11.6 of the design) require:
- LM Studio running locally with a model loaded (or another OpenAI-compatible endpoint reachable)
- A Whisper model cached (faster-whisper auto-downloads `base.en` on first use)
- OpenVoice cloned to `~/OpenVoice` with checkpoints

If any of those is missing on the dev machine when impl reaches integration, surface to Architect and proceed with mock-only acceptance for now.

## Spec-01 implementation summary

**24 task commits + 1 fix commit + 1 docs commit + merge** on `main`. All quality gates green:
- 29/29 unit tests passing (Vitest)
- ESLint clean
- `tsc --noEmit` clean
- `vite build` ~7KB gzip JS, ~2KB gzip CSS
- `vite preview` serves HTTP 200

**Caveat:** Playwright e2e smoke test code is committed but the test run requires `sudo npx playwright install-deps chromium` (system libs). Documented in `web/README.md`.

### File breakdown

| Area | Files |
|---|---|
| Types | `src/types.ts` |
| State | `src/state/stateMachine.ts`, `src/state/store.ts` |
| Events | `src/events/eventSource.ts`, `src/events/mockEventSource.ts`, `src/events/scenarios.ts` |
| Audio | `src/audio/analyzer.ts`, `src/audio/micCapture.ts` |
| UI | `src/ui/Component.ts`, `Panel.ts`, `Header.ts`, `Centerpiece.ts`, `Waveform.ts`, `Transcript.ts`, `Controls.ts`, `keyboard.ts` |
| Panels | `src/ui/panels/{System,Memory,Calendar,Network,Tasks,Telemetry,Audio}Panel.ts` |
| Data | `src/data/calendar.ts` |
| App | `src/main.ts` (boot sequence wiring everything) |
| Styles | `src/styles/{global,grid,panel}.css` |
| Tests | `test/{sanity,stateMachine,store,mockEventSource,component,transcript,analyzer}.test.ts` (29 tests) |
| E2E | `e2e/smoke.spec.ts`, `playwright.config.ts` |
| Tooling | `package.json`, `tsconfig.json`, `vite.config.ts`, `vitest.config.ts`, `eslint.config.js`, `.prettierrc.json`, `.gitignore` |
| Docs | `web/README.md` |

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

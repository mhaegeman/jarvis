# Jarvis Build · Live Status

> **Single source of truth.** Updated at every phase boundary and committed.
> Any agent resuming this project should read this file first.

**Last updated:** 2026-05-07

---

## Current Phase
**spec-01-frontend-shell · brainstorming**

## Macro Progress

| # | Sub-spec | Brainstorm | Plan | Implement | Review | Verify | Merged |
|---|---|---|---|---|---|---|---|
| 0 | Umbrella architecture | ✅ approved | n/a | n/a | n/a | n/a | ⏳ pending commit |
| 1 | spec-01-frontend-shell | ⏳ in progress | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
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
Wrote umbrella architecture doc, self-reviewed, user approved with delegation. Created STATUS.md and memory pointer.

## Next action
Begin spec-01-frontend-shell brainstorm. Orchestrator acts as Brainstorming Lead. Output: `docs/superpowers/specs/2026-05-07-frontend-shell-design.md`. Auto-approved by orchestrator on completion (per delegation), commit, then transition to writing-plans for spec-01.

## Open blockers
None.

## Notes for future sessions
- Existing `speech_text_speech.py` is the legacy reference for the backend pipeline. Do **not** modify it; it is preserved until spec-02 supersedes it.
- Existing `prototypes/` are reference-only (4 HTML files + index). Do not modify; the production frontend lives in `web/`.
- `second-brain/` is governed by its own `CLAUDE.md` and is exempt from this workflow.
- Skills available: see `.claude/skills/`.

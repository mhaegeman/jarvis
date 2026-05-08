# Jarvis Build · Live Status

> **Single source of truth.** Updated at every phase boundary and committed.
> Any agent resuming this project should read this file first.

**Last updated:** 2026-05-08 (spec-04 implementation complete on branch)

---

## Current Phase
**spec-04-deploy-and-gate · pending PR + Architect manual setup (Pages source, secret, branch protection)**

## Macro Progress

| # | Sub-spec | Brainstorm | Plan | Implement | Review | Verify | Merged |
|---|---|---|---|---|---|---|---|
| 0 | Umbrella architecture | ✅ committed | n/a | n/a | n/a | n/a | ✅ on main |
| 1 | spec-01-frontend-shell | ✅ committed | ✅ committed | ✅ 22/22 | ✅ subagent | ✅ 30/30 tests | ✅ merged 7a6abe1 |
| 2 | spec-02-backend-streaming | ✅ committed (5d4f31f) | ✅ committed (639f631) | ✅ 19/19 (Phase 1) | ✅ subagent + Codex P1/P2 | ✅ 58/58 tests | ✅ merged 6efecde + 95e6eee |
| 3 | spec-03-integration | ✅ committed (dc84817) | ✅ committed (c1f6041) | ✅ 13/13 tasks | ✅ Codex P1/P1 (5cfb2dc) | ✅ 60/60 vitest, lint+tsc+build clean | ✅ merged ab7cb7c |
| 4 | spec-04-deploy-and-gate | ✅ committed (f80d562) | ✅ committed (84da47e) | ✅ 5/5 tasks | ⏳ pending PR | ⏳ CI runs against PR | ⏳ branch pushed |

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
Spec-04 implementation complete on branch `spec-04-deploy-and-gate`
(7 commits). Architect to:

1. Open PR — CI workflow self-tests by running on this PR
2. Set repo secret `STATICRYPT_PASSWORD`
3. Settings → Pages → Source: "GitHub Actions"
4. Settings → Branches → main → require `web` and `server` checks
5. Merge PR — first deploy lands at `https://mhaegeman.github.io/jarvis/`
6. Install systemd unit on the laptop per `server/deploy/README.md`

After merge, v1 ships. Future scope (out of v1): spec-02 Phase 2 (real
Whisper / LLM / OpenVoice), HTTPS for backend (Cloudflare tunnel),
custom domain.

### Spec-04 implementation summary
**7 commits on branch `spec-04-deploy-and-gate`.** No application-code
changes; pure infra:
- `web/vite.config.ts` — `base: process.env.VITE_BASE ?? "/"` (one line)
- `.github/workflows/ci.yml` — web (npm ci → tsc → eslint → vitest →
  vite build) + server (pip install → ruff → mypy → pytest), parallel
- `.github/workflows/deploy.yml` — push-to-main trigger, vite build with
  `VITE_BASE=/jarvis/`, staticrypt encrypt, `actions/deploy-pages@v4`
- `server/deploy/jarvis-backend.service` — systemd `--user` unit
  (Restart=on-failure, RestartSec=2, journal logging, default.target)
- `server/deploy/README.md` — install + verify + lingering procedure
- `web/README.md` — Live URL + password-rotation + autostart pointers

Local verification passing: 60/60 vitest, 58/58 pytest, both default
and `VITE_BASE=/jarvis/` builds produce correct asset paths.

### Spec-03 implementation summary
**14 commits on `spec-03-integration` + Codex review fix, merged via PR #5.** All quality gates green at merge:
- 60/60 vitest tests passing (30 new for spec-03 — 27 from initial impl, 3 regression for Codex P1s)
- `tsc --noEmit` clean
- `eslint .` clean
- `vite build` succeeds, JS bundle 9.23 KB gzip (under 30 KB target)
- New modules: `audio/wsCodec.ts`, `audio/playbackQueue.ts`,
  `audio/micWorklet.ts`, `public/mic-processor.js`,
  `events/wsEventSource.ts`, `events/connect.ts`
- Vite/esbuild target bumped to es2022 for top-level await in `main.ts`
- ESLint configured with AudioWorklet globals for `public/*.js`

### Codex review fixes (commit `5cfb2dc`)
- **P1-A** — `wsEventSource.beginListening()` was emitting `audio.start`
  before awaiting mic setup. Mic failure left the server stuck in
  recording mode. Fix: defer `audio.start` until the mic handle resolves;
  track `audioStartSent` so `endListening` only sends `audio.end` when a
  start was actually emitted.
- **P1-B** — `main.onMicDown` awaited `beginListening` before transitioning
  to `listening`, so a quick Space release was ignored by `onMicUp`'s
  state guard. Fix: transition first, then await; rollback on failure.
- Race coverage: `endListening` now aborts an in-flight `beginListening`,
  discarding the mic handle when it eventually resolves so no spurious
  protocol messages hit the wire.

### Acceptance gating
Manual e2e checklist in `web/README.md` covers: live boot + telemetry
heartbeats, text path, audio path, barge-in, reconnect with backoff,
demo fallback when backend offline, mic-denied path, analyser-driven
centerpiece reactivity. Spec doc:
`docs/superpowers/specs/2026-05-08-integration-design.md`.

### Spec-02 Phase 1 implementation summary
**13 commits on branch `spec-02-backend-streaming`.** All quality gates green:
- 54/54 tests passing (pytest)
- Coverage: protocol 97%, sentence_split 96%, session 87%, total 90%
- `ruff check` clean
- `mypy --strict` clean
- `uvicorn server.main:app` boots; `/health` returns 200
- `python -m server.cli_test --text "Brief me on today"` streams a reply end-to-end
- `python -m server.cli_test --audio-fixture tests/fixtures/silence.wav` exercises the audio path

### Phase 2 (deferred)
- Replace `MockSTT` with `faster-whisper`; pre-load `base.en` in lifespan
- Replace `MockLLM` with `openai.AsyncOpenAI` streaming (default LM Studio)
- Replace `MockTTS` with OpenVoice; emit real PCM Int16 binary frames
- Triggered after spec-04 deploys the Phase 1 stack
- Pre-reqs: LM Studio running, Whisper model cached, OpenVoice cloned + checkpoints

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

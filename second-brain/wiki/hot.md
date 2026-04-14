# Hot Topics
_Short-term memory primer. Keywords only. ≤500 words. Updated: 2026-04-14._

---

## 2026-04-14

**obra/superpowers** — complete software dev workflow plugin for AI coding agents. Jesse Vincent / Prime Radiant. MIT. Claude Code official marketplace: `/plugin install superpowers@claude-plugins-official`. Also: Cursor, Codex, OpenCode, Gemini CLI, GitHub Copilot CLI. v5.0.7. Zero-dependency.

Core mechanic: **session-start shell hook** injects `using-superpowers` skill → agent obligated to invoke relevant skill before ANY action. "1% chance it applies = MUST invoke." Skill format: YAML frontmatter (`name`, `description`) + DOT flow diagrams + Red Flags rationalization tables.

**13 skills** (mandatory lifecycle):
1. `brainstorming` → HARD-GATE: no code before approved spec. Spec saved `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
2. `using-git-worktrees` → isolated branch per feature
3. `writing-plans` → checkbox steps 2–5 min each, exact file paths, complete code. Plan saved `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`
4. `subagent-driven-development` → **fresh subagent per task**, two-stage review: spec compliance then code quality. Implementer statuses: DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED
5. `test-driven-development` → RED-GREEN-REFACTOR enforced
6. `requesting-code-review` / `receiving-code-review`
7. `systematic-debugging` → 4-phase root cause
8. `verification-before-completion` → Iron Law: no completion claims without fresh evidence. 24 failure memories.
9. `finishing-a-development-branch`, `dispatching-parallel-agents`, `writing-skills`, `using-superpowers`

**v5.0.6 key change:** inline self-review replaces subagent review loops for specs/plans — same quality, 25 min faster.

Priority: user CLAUDE.md > Superpowers skills > system prompt. `<SUBAGENT-STOP>` block prevents recursive skill activation in dispatched subagents.

**Visual brainstorming companion:** opt-in Node.js WS server + browser window for mockups during brainstorming. Zero-dep (built-in http/crypto/fs). 30-min idle auto-exit + owner-PID tracking.

New concepts: [skills-based-agent-extension](concepts/skills-based-agent-extension.md), [subagent-driven-development](concepts/subagent-driven-development-concept.md). 94% PR rejection rate — strict human-review requirement.

---

## 2026-04-14 (earlier)

**airbnb/chronon** — open-source **Feature Platform** for ML. Airbnb + Stripe co-maintained. Apache 2.0. Python API (`GroupBy` / `Join` / `StagingQuery`) → Thrift → Spark (batch) + Flink (streaming) + online `Fetcher` (Scala/Java) + Vert.x REST service. KV store pluggable (MongoDB in quickstart). Airflow control plane.

Core guarantees: **Point-in-Time Correctness** (Sawtooth Windows), **Online/Offline Consistency** (log fetches → re-backfill → compare). **Tiled Architecture** (Stripe-contributed) — 33% latency cut. CHIP-1 (22–35% batch latency cut). Ships `.claude/` + CLAUDE.md + 10 slash commands.

## 2026-04-13

**Jumbo** — memory + context orchestration CLI for coding agents. 5-phase lifecycle. **Context packet** assembly. Agent-agnostic. 12 Claude Code skills.

**nexos.ai** — NOT compliance competitor. "Guardrails" = PII filtering. $350M, NordVPN founders.

**RuFlo** — multi-agent orchestration. 100+ agents, 137 skills, 313 MCP tools. Topologies hierarchical/mesh/ring/star.

**GuardRail team** — Maxime (ML), Harsh (UX), Karoline (legal/EU AI Act), Fabio (AI agents)

## Wiki state
88 pages | 22 sources | 9 people | 22 entities | 30 concepts | 0 analyses

---
_Deep dive: [overview](overview.md) | Full catalog: [index](index.md) | History: [log](log.md)_

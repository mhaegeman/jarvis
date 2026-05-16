# CLAUDE.md — Claude Code Instructions

**Read `AGENTS.md` at repo root first.** Defines project overview, workflow, build/test, conventions for every agent. This file adds Claude-Code-specific mechanics (skill loading) on top.

Second-brain ops → follow `second-brain/AGENTS.md` exclusively (ingest/query/lint/update wiki).

---

## Superpowers Skills

Skills defined in `.claude/skills/`. Read via `Read` on `.claude/skills/<skill-name>.md`.

<EXTREMELY-IMPORTANT>
If even 1% chance a skill applies (outside second-brain ops), you ABSOLUTELY MUST read + follow it.

IF A SKILL APPLIES, YOU MUST USE IT. Not negotiable. Not optional. Cannot rationalize out.
</EXTREMELY-IMPORTANT>

---

## Available Skills

- `brainstorming` — before any feature/component/behavior change
- `writing-plans` — after spec approval, before code
- `executing-plans` — execute written plan in batch w/ checkpoints
- `subagent-driven-development` — plan tasks w/ fresh subagents + two-stage review
- `test-driven-development` — RED-GREEN-REFACTOR during implementation
- `systematic-debugging` — before proposing any bug/failure fix
- `verification-before-completion` — before claiming work complete
- `requesting-code-review` — after completing task/feature
- `receiving-code-review` — when receiving review feedback
- `using-git-worktrees` — before starting feature implementation
- `finishing-a-development-branch` — when implementation complete
- `dispatching-parallel-agents` — when 2+ independent tasks parallelisable
- `writing-skills` — when creating/modifying skills
- `stop-slop` — when writing/editing/reviewing prose for AI tells
- `ui-ux-pro-max` — UI components, color, typography, UX patterns
- `context-engineering` — structuring context/reasoning protocols for LLM tasks
- `remotion` — programmatic videos w/ React + Remotion
- `grill-with-docs` — stress-test plan vs domain model, sharpen terms, update CONTEXT.md/ADRs inline

---

## Skill Priority When Multiple Apply

1. **Process skills first** (brainstorming, debugging) — determine HOW to approach
2. **Implementation skills second** — guide execution

"Let's build X" → brainstorming first.
"Fix this bug" → systematic-debugging first.

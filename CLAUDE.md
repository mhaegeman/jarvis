# CLAUDE.md — Claude Code-Specific Instructions

**Read `AGENTS.md` at the repo root first.** It defines the project overview, workflow, build/test commands, and conventions that apply to every agent. This file only adds Claude-Code-specific mechanics (skill loading) layered on top.

For second-brain operations, `AGENTS.md` directs you to `second-brain/AGENTS.md` — follow that file exclusively when ingesting, querying, linting, or updating the wiki.

---

## Superpowers Skills

This repository uses the Superpowers skills-based development workflow. Skills are defined in `.claude/skills/`. Read a skill by using `Read` on `.claude/skills/<skill-name>.md`.

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing (outside of second-brain operations), you ABSOLUTELY MUST read and follow the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This is not negotiable. This is not optional. You cannot rationalize your way out of this.
</EXTREMELY-IMPORTANT>

---

## Available Skills

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
- `stop-slop` — When writing, editing, or reviewing prose for AI writing tells
- `ui-ux-pro-max` — When designing UI components, color palettes, typography, or UX patterns
- `context-engineering` — When structuring context or reasoning protocols for LLM tasks
- `remotion` — When building programmatic videos with React and Remotion
- `grill-with-docs` — When stress-testing a coding plan against the domain model, sharpening terminology, and updating CONTEXT.md / ADRs inline

---

## The Rule

**Read the relevant skill BEFORE any response or action.**

```
User message received
  → Is this a second-brain operation?  → Yes → Follow second-brain/AGENTS.md only
  → Might any skill apply? (even 1%)   → Yes → Read skill → Follow it exactly
  → Definitely not applicable          → Respond normally
```

---

## Skill Priority When Multiple Apply

1. **Process skills first** (brainstorming, debugging) — determine HOW to approach
2. **Implementation skills second** — guide execution

"Let's build X" → brainstorming first.
"Fix this bug" → systematic-debugging first.

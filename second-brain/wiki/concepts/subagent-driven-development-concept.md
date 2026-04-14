---
title: Subagent-Driven Development
type: concept
tags: [coding-agents, superpowers, multi-agent, tdd, code-review, workflow-automation, claude-code]
---

## Definition

A software implementation workflow where a **controller agent** dispatches fresh subagents — one per plan task — each with isolated context constructed by the controller. After each task, the controller runs a two-stage review: (1) spec compliance review, then (2) code quality review. Reviewers are also subagents. Nothing passes to the next task until both reviews approve.

Coined and implemented in [Superpowers](../entities/superpowers.md) by [Jesse Vincent](../people/jesse-vincent.md). The controller is the current session; subagents are dispatched via the `Task` tool (Claude Code) or equivalent.

## Why It Matters

Coding agents lose context and coherence over long sessions. Giving each task a fresh subagent with precisely constructed context produces higher-quality, more focused implementation than a single agent accumulating context debt. The two-stage review (spec compliance before code quality) catches both "built the wrong thing" and "built it badly" failures, in that order.

The pattern enables autonomous multi-hour work sessions. The Superpowers README claims Claude can work "a couple hours at a time without deviating from the plan."

## Evidence & Examples

From the Superpowers skill:
- **Implementer statuses:** `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `BLOCKED` — each handled differently
- **Model selection guidance:** cheap model for mechanical tasks (1-2 files, clear spec), standard for integration, most capable for architecture/review
- **Context isolation principle:** controller curates exactly what each subagent needs; subagents never inherit session history
- **Review loop:** reviewer finds issue → implementer (same subagent) fixes → reviewer reviews again → repeat until approved

vs `executing-plans`: SDD stays in the same session with automatic review; executing-plans works across parallel sessions with human checkpoints.

## Tensions & Counterarguments

- **Cost:** More subagent invocations (implementer + 2 reviewers per task); review loops add iterations — but catches issues early, cheaper than debugging later
- **Tight coupling:** If tasks are interdependent (shared state, sequential builds), fresh-context subagents struggle; SDD works best for independent tasks
- **Overhead for simple tasks:** For 1-2 step tasks, the full SDD process (dispatch → 2 reviews → loops) is heavier than inline execution

## Related

- [Superpowers](../entities/superpowers.md) — implements this as the `subagent-driven-development` skill
- [Skills-Based Agent Extension](../concepts/skills-based-agent-extension.md) — the broader pattern SDD lives within
- [Agentic Workflow Patterns](../concepts/agentic-workflow-patterns.md) — broader category
- [SPARC Methodology](../concepts/sparc-methodology.md) — similar phase-driven philosophy

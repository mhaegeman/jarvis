---
title: "jumbocontext / jumbo.cli"
type: source
date_ingested: 2026-04-13
source_file: raw/jumbocontext-jumbo-cli.md
source_url: https://github.com/jumbocontext/jumbo.cli
tags: [
  github, open-source, agpl-3,
  agent-memory, context-orchestration, agent-amnesia,
  coding-agents, claude-code, copilot, gemini, cursor, codex, vibe,
  goal-lifecycle, context-packets, knowledge-persistence,
  event-sourcing, cqrs, ddd, clean-architecture,
  typescript, node-js, sqlite, inversify, commander,
  multi-agent, parallel-agents, claims-system,
  skills, hooks, agents-md,
  copenhagen, jumbocontext
]
---

## Summary

Jumbo is a CLI tool that gives coding agents persistent memory and structured project context. It solves the "agent amnesia" problem — every new session forgets prior context — by maintaining a local event-sourced knowledge store (`.jumbo/`) containing components, decisions, invariants, guidelines, dependencies, audiences, pains, value propositions, and typed relations between them. When an agent starts a goal, Jumbo assembles a curated **context packet** from the entities linked to that goal, delivering precisely the knowledge the agent needs without context bloat.

The tool is agent-agnostic: it integrates with Claude Code, GitHub Copilot, Gemini CLI, Cursor, Codex, and Mistral Vibe via session hooks and AGENTS.md. It ships 12 Claude Code skills covering the full goal lifecycle. All data stays local — no cloud, no network calls.

## Tech Stack

- **Runtime**: Node.js 18.18+, TypeScript
- **Persistence**: Event sourcing (append-only JSON files) + CQRS read projections (SQLite via better-sqlite3)
- **CLI framework**: Commander.js
- **DI**: Inversify + reflect-metadata
- **Terminal UI**: Ink + React, Inquirer, Chalk, Boxen
- **Architecture**: Clean Screaming Architecture — Domain → Application → Infrastructure → Presentation, strict inward dependency rule
- **Patterns**: Event Sourcing, CQRS, DDD (one aggregate per bounded context), Gateway Pattern (Inversify wiring)

## Purpose

Jumbo solves three problems for developers using AI coding agents: (1) agent amnesia — persistent memory across sessions so agents don't start from zero, (2) slop — structured goals with criteria, scope, invariants, and QA review enforce production-quality output, (3) vendor lock-in — agent-agnostic design means switching models/harnesses doesn't lose context. The primary user action is defining goals (`jumbo goal add`) and letting agents drive through the lifecycle.

## Key Points

- **Goal lifecycle** is the core workflow: **Define** (objective + criteria + scope) → **Refine** (agent links relevant entities as relations, building context packet) → **Implement** (agent receives curated context, executes within scope) → **Review** (QA verification against every criterion, invariant, guideline) → **Codify** (capture new learnings, update stale entities, close goal).
- **Context packets** are dynamically assembled bundles of project knowledge delivered at workflow transitions — session start (project overview, available goals) and goal start (objective, criteria, scope, architecture, components, decisions, invariants, guidelines).
- **Entity graph**: Jumbo tracks 9 entity types — components, decisions, invariants, guidelines, dependencies, audiences, audience pains, value propositions, relations. Relations are typed (`involves`, `uses`, `must-respect`, `follows`, `implements`) and bidirectional.
- **12 Claude Code skills**: define-goals, refine-goals, start-goal, review-goal, reject-goal, codify-goal, design-goal, add-component, add-decision, add-dependency, add-guideline, add-invariant.
- **Multi-agent parallel work**: Multiple agents in separate terminals can claim different goals. Claims expire after configurable duration (default 30 min). `work pause` / `work resume` for continuity.
- **Goal chaining**: `--previous-goal` / `--next-goal` creates ordered sequences. Agent finishes goal A → Jumbo suggests goal B with fresh context. Prevents context rot across multi-goal workstreams.
- **Brownfield onboarding**: First session on existing project prompts agent to scan and register existing knowledge (components, decisions, patterns).
- **Event store**: Append-only JSON files organized by aggregate UUID. SQLite is a rebuildable read projection — delete `jumbo.db` and reconstruct from events via `jumbo heal --yes`.
- **`jumbo evolve --yes`**: Single command for schema migrations, data migrations, config refresh, projection rebuild.
- **Refinery daemon**: `jumbo work refine --agent <agent>` continuously polls for `defined` goals and delegates refinement to agent subprocesses.
- **AGPL-3.0 license**, dual-licensed for commercial use. Built in Copenhagen.
- **v2.11.1** as of 2026-04-11. Active development since Dec 2025.

## Quotes

> "Jumbo is a CLI tool that gives your coding agents persistent memory and structured project context, turning them from makers of workable prototypes into builders of production-quality software."

> "An elephant never forgets. Neither should [your agent]."

> "A goal's definition determines everything downstream. During refinement, the agent registers relations based on the objective and criteria. During implementation, `jumbo goal start` assembles context from those relations into an implementation prompt. Vague objectives produce vague relations. Vague relations produce bloated or incomplete context."

> "Context registered now is served to future sessions. What you skip is lost."

## Connections

- [Agentic Workflow Patterns](../concepts/agentic-workflow-patterns.md) — Jumbo's define→refine→implement→review→codify is the most structured agent workflow pattern in the wiki; extends triage→specialize→validate with explicit knowledge curation and QA gates
- [Claude Code](../entities/claude-code.md) — Primary integration target; 12 skills, session hooks, CLAUDE.md generation
- [Agent Context Orchestration](../concepts/agent-context-orchestration.md) — New concept: structured context assembly for agent workflows (Jumbo's core innovation)
- [LLM Wiki Pattern](../concepts/llm-wiki-pattern.md) — Both solve knowledge persistence; wiki compiles prose, Jumbo maintains an entity graph with typed relations — complementary approaches
- [RuFlo](../entities/ruflo.md) — Both are Claude Code orchestration platforms; RuFlo focuses on swarm topologies and multi-agent consensus, Jumbo focuses on goal lifecycle and persistent memory
- [Boris Cherny](../people/boris-cherny.md) — Cherny's "information mode" principle validates Jumbo's approach: invest in structured context, not prompts

## Questions Raised

- How does Jumbo's entity-graph approach compare to the LLM Wiki Pattern at scale? Wiki compounds prose; Jumbo compounds relations — which produces better agent output for complex projects?
- Can Jumbo and the LLM Wiki Pattern be combined? Wiki for synthesis and understanding, Jumbo for operational context during implementation?
- The AGPL-3.0 license with CLA suggests a commercial cloud version is planned. How will that affect adoption?
- How well does the refinement phase scale? With hundreds of entities, does relation curation become a bottleneck?

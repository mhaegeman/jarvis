---
title: Jumbo
type: entity
entity_type: product
tags: [agent-memory, context-orchestration, cli, coding-agents, event-sourcing, goal-lifecycle]
---

## Overview

Jumbo is a CLI tool for memory and context orchestration for coding agents. It maintains a local event-sourced knowledge store that gives agents persistent memory across sessions, solving the "agent amnesia" problem. Its core mechanism is the **goal lifecycle** — a 5-phase workflow (define → refine → implement → review → codify) where context packets are dynamically assembled from linked project entities to give agents precisely the knowledge they need.

## Key Facts

- **Package**: `npm install -g jumbo-cli` (Node.js 18.18+)
- **License**: AGPL-3.0 (dual-licensed, commercial cloud version planned)
- **Architecture**: Clean Architecture + Event Sourcing + CQRS + DDD, TypeScript
- **Agent support**: Claude Code, GitHub Copilot, Gemini CLI, Cursor, Codex, Mistral Vibe — via hooks + AGENTS.md
- **Data**: Local only — `.jumbo/` directory with append-only JSON event store + SQLite read projections
- **Entity types tracked**: components, decisions, invariants, guidelines, dependencies, audiences, audience pains, value propositions, relations
- **Goal lifecycle**: defined → in-refinement → refined → doing → submitted → in-review → approved → codifying → done
- **Skills**: 12 Claude Code skills for full lifecycle coverage
- **Multi-agent**: Parallel terminals with claims-based goal ownership
- **Built**: Copenhagen, active since Dec 2025, v2.11.1 as of Apr 2026
- **GitHub**: [jumbocontext/jumbo.cli](https://github.com/jumbocontext/jumbo.cli)

## Appearances

- [jumbocontext/jumbo.cli](../sources/jumbocontext-jumbo-cli.md) — Primary source: full documentation and changelog ingested via repomix

## Connections

- [Claude Code](claude-code.md) — Primary integration target; hooks, skills, CLAUDE.md generation
- [RuFlo](ruflo.md) — Both are Claude Code orchestration platforms; RuFlo = swarm topologies + multi-agent consensus, Jumbo = goal lifecycle + persistent memory
- [Agentic Workflow Patterns](../concepts/agentic-workflow-patterns.md) — Jumbo implements the most structured variant: 5-phase goal lifecycle with knowledge curation and QA gates
- [Agent Context Orchestration](../concepts/agent-context-orchestration.md) — Jumbo's core innovation: dynamically assembled context packets from entity relations
- [LLM Wiki Pattern](../concepts/llm-wiki-pattern.md) — Complementary approach: wiki compiles prose for synthesis, Jumbo maintains entity graph for operational context

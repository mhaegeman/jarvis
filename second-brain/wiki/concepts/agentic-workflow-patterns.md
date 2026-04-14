---
title: Agentic Workflow Patterns
type: concept
tags: [claude-code, ai-agents, multi-agent, workflow, software-engineering]
---

## Definition

Agentic workflow patterns are structured approaches to decomposing complex tasks across multiple AI sub-agents, each specialised for a phase of the workflow, coordinated by an orchestrator. In the Claude Code context, this means using `.claude/agents/*.md` files to define specialist agents (code reviewer, security auditor, tester, architect) that the orchestrating Claude instance can invoke for focused sub-tasks.

Key patterns observed across ingested repos:

1. **Triage → specialise → validate:** Use a cheap model (Haiku) for triage/pre-checks, a mid-tier model (Sonnet) for summarisation, and an expensive model (Opus) for deep bug analysis — then validate findings before acting.
2. **Parallel sub-agents:** Run multiple review agents simultaneously (e.g., two independent Opus bug-detection agents) and merge their outputs.
3. **Validation gate:** After collecting findings from parallel agents, spawn additional agents to validate each finding before it reaches the user — filtering false positives.
4. **Hooks as guardrails:** Bash hooks that fire on every tool call enforce invariants (no secrets, lint passes, branch protections) without relying on the agent's memory or good judgment.
5. **Layered configuration:** CLAUDE.md → rules → hooks → agents — each layer adds specificity without bloating the root file.

## Why It Matters

Agentic workflows allow Claude Code to tackle tasks that would overwhelm a single context window or require multiple passes of reasoning. By decomposing into specialised, short-context sub-agents, the system remains accurate and cost-efficient.

## Evidence & Examples

- [Superpowers](../entities/superpowers.md) — the most disciplined process-enforcement approach: 13 mandatory skills, rigid brainstorm→spec→plan→subagent-driven-development→review→finish pipeline. Enforces TDD, verification-before-completion, and rationalization prevention. Skills use DOT graphs and Red Flags tables as structural guardrails. See [Skills-Based Agent Extension](skills-based-agent-extension.md) and [Subagent-Driven Development](subagent-driven-development-concept.md).
- [Jumbo](../entities/jumbo.md) — the most structured lifecycle: 5-phase goal workflow (define → refine → implement → review → codify) with dynamically assembled [context packets](agent-context-orchestration.md) from an entity graph. Focuses on knowledge persistence and QA gates rather than swarm coordination.
- [RuFlo](../entities/ruflo.md) — the most comprehensive implementation: 100+ agents, 4 swarm topologies, 5 consensus protocols, self-learning memory, 3-tier intelligent routing, SPARC methodology, claims-based authorization. Implements and extends every pattern listed above.
- [getnao / Nao](../sources/getnao-nao.md) — ships a multi-agent code review skill (Haiku triage → Sonnet summary → parallel Opus bug detection → validation → GitHub comments).
- [Leavitskiy / Claude Agentic Flow](../sources/leavitskiy-claude-agentic-flow.md) — library of domain-specific agent prompt definitions (backend, frontend, code review, refactoring).
- [EduardPetraeus / Claude Code Quickstart](../sources/eduardpetraeus-claude-code-quickstart.md) — full starter kit with 9 agents, 10 hooks, 8 rules, parallel-execution guide.
- [Owl-Listener / Designer Skills](../sources/owl-listener-designer-skills.md) — 50+ designer-specific skills following the same agent pattern.

## Tensions & Counterarguments

- More agents = more latency and cost. The validation-gate pattern adds round-trips.
- Agent skill libraries can become stale if not maintained — a prompt that worked with Claude 3 Sonnet may behave differently with Claude 4.
- Parallel sub-agents with shared output targets (e.g., a single wiki index file) can cause write conflicts — sequencing or locking is needed.
- Agent drift in long-running tasks requires structural mitigations (see [Swarm Coordination Topologies](swarm-coordination-topologies.md) and [Multi-Agent Consensus Protocols](multi-agent-consensus-protocols.md)).

## Related

- [Claude Code](../entities/claude-code.md)
- [RuFlo](../entities/ruflo.md) — full orchestration framework implementing all patterns
- [Swarm Coordination Topologies](swarm-coordination-topologies.md) — structural patterns for agent communication
- [Multi-Agent Consensus Protocols](multi-agent-consensus-protocols.md) — fault-tolerance for agent decisions
- [Self-Learning Agent Architecture](self-learning-agent-architecture.md) — how agents improve over time
- [Intelligent Task Routing](intelligent-task-routing.md) — cost-optimal model selection
- [SPARC Methodology](sparc-methodology.md) — spec-driven development to prevent drift
- [Claims-Based Agent Authorization](claims-based-agent-authorization.md) — agent permission model
- [Agent Context Orchestration](agent-context-orchestration.md) — dynamic context assembly (Jumbo's core concept)
- [Jumbo](../entities/jumbo.md) — goal lifecycle + persistent memory orchestration
- [Skills-Based Agent Extension](skills-based-agent-extension.md) — mandatory workflow enforcement via skill files
- [Subagent-Driven Development](subagent-driven-development-concept.md) — fresh subagent per task + 2-stage review pattern
- [LLM Wiki Pattern](../concepts/llm-wiki-pattern.md)
- [RAG vs Wiki Architecture](../concepts/rag-vs-wiki-architecture.md)

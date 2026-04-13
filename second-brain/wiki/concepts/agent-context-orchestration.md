---
title: Agent Context Orchestration
type: concept
tags: [context-packets, agent-memory, knowledge-persistence, goal-lifecycle, coding-agents]
---

## Definition

Agent context orchestration is the practice of dynamically assembling and delivering curated bundles of project knowledge ("context packets") to coding agents at workflow transitions — so agents receive precisely the information they need for a specific task, neither too much (context bloat, token waste) nor too little (missing constraints, wrong output). It sits between raw persistent memory and the agent's prompt window.

## Why It Matters

Coding agents face two opposing failure modes: (1) **amnesia** — starting every session from zero, wasting time re-establishing context, and (2) **context bloat** — dumping everything into the prompt, diluting focus and wasting tokens. Context orchestration solves both by maintaining a structured knowledge graph and assembling task-specific subsets at the moment they're needed.

The key insight is that different tasks need different context. An agent implementing a rate-limiting feature needs the HTTP middleware components, relevant invariants about API security, and the decision to use token-bucket algorithm — but not the database migration guidelines or the UI design system. Static approaches (single CLAUDE.md, monolithic README) can't make this distinction. Dynamic assembly can.

## Evidence & Examples

- **[Jumbo](../entities/jumbo.md)** is the most complete implementation. It tracks 9 entity types (components, decisions, invariants, guidelines, dependencies, audiences, pains, value propositions) connected by typed relations. During goal refinement, an agent links relevant entities to the goal. At `goal start`, Jumbo assembles these into a context packet containing objective, criteria, scope, architecture, and all linked entities. Each entity includes a description explaining its specific relevance to this goal.
- **[RuFlo](../entities/ruflo.md)** approaches the problem differently — through [intelligent task routing](intelligent-task-routing.md) and [swarm coordination](swarm-coordination-topologies.md) rather than entity-level context assembly.
- **[Boris Cherny's "information mode" principle](../people/boris-cherny.md)** provides the philosophical justification: invest in structured context (that compounds) rather than prompt optimization (that decays).
- The **[LLM Wiki Pattern](llm-wiki-pattern.md)** is a complementary approach: it compiles persistent prose for synthesis and understanding, while context orchestration assembles operational context for task execution.

## Tensions & Counterarguments

- **Overhead vs. value**: Maintaining an entity graph requires upfront investment (registering components, decisions, invariants). For small projects or quick prototypes, a single CLAUDE.md may be sufficient. The entity-graph approach pays off as projects grow and agent sessions accumulate.
- **Refinement as bottleneck**: The quality of context packets depends on the quality of refinement. Vague objectives → vague relations → bloated context. This moves the failure mode from "agent has wrong context" to "agent curated wrong relations."
- **Static vs. dynamic**: CLAUDE.md and wiki pages are human-readable and auditable. Entity graphs with typed relations are more machine-optimal but harder for humans to inspect holistically.
- **Complementarity with wiki**: Context orchestration and wiki compilation are not mutually exclusive. A wiki provides synthesis across sources; context orchestration provides task-scoped operational context. Both solve knowledge persistence but for different purposes.

## Related

- [Agentic Workflow Patterns](agentic-workflow-patterns.md) — Context orchestration enables structured agent workflows by ensuring each phase has the right knowledge
- [LLM Wiki Pattern](llm-wiki-pattern.md) — Complementary persistence approach: compiled prose vs. assembled entity graph
- [Persistent Compounding Knowledge](persistent-compounding-knowledge.md) — Both wiki and entity-graph approaches exhibit this property: each addition enriches related knowledge
- [Intelligent Task Routing](intelligent-task-routing.md) — RuFlo's approach to the same problem space: route tasks to the right agent tier, not assemble context for a single agent

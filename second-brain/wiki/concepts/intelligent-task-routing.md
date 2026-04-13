---
title: Intelligent Task Routing
type: concept
tags: [cost-optimization, model-routing, token-optimization, wasm, ruflo]
---

## Definition

Intelligent task routing is the practice of analyzing incoming tasks and directing them to the cheapest handler that can produce an acceptable result — from zero-cost WASM transforms for trivial edits, through small/medium models for standard work, to the most capable (and expensive) model only for complex reasoning.

## Why It Matters

Without routing, every task — no matter how simple — hits the most expensive model. This wastes tokens, increases latency, and burns through API budgets or Claude Code quotas. RuFlo claims 75% API cost reduction and 30–50% token savings through intelligent routing.

## The Three Tiers

| Tier | Handler | Latency | Cost | Use Cases |
|------|---------|---------|------|-----------|
| **1** | Agent Booster (WASM) | <1ms | $0, 0 tokens | var→const, add-types, remove-console, add-logging, async-await, add-error-handling |
| **2** | Haiku/Sonnet | 500ms–2s | $0.0002–0.003 | Bug fixes, refactoring, feature implementation, test writing |
| **3** | Opus | 2–5s | $0.015 | Architecture design, security analysis, distributed systems, complex reasoning |

### How Routing Works
1. **Q-learning router:** Trained on historical task outcomes. Uses epsilon-greedy exploration to occasionally try cheaper tiers for tasks it's unsure about.
2. **Complexity analysis:** Pre-task hooks analyze the request to estimate complexity.
3. **Hook signals:** The system outputs signals like `[AGENT_BOOSTER_AVAILABLE]` (use WASM, skip LLM) or `[TASK_MODEL_RECOMMENDATION] Use model="haiku"` (downgrade model).

### Token Optimization Stack

| Optimization | Token Savings | Mechanism |
|--------------|---------------|-----------|
| ReasoningBank retrieval | −32% | Fetch relevant patterns instead of full context |
| Agent Booster (WASM) | −15% | Simple edits skip LLM entirely |
| Cache (95% hit rate) | −10% | Reuse embeddings and patterns |
| Optimal batch size | −20% | Group related operations |
| **Combined** | **30–50%** | Stacks multiplicatively |

## Practical Application

For any agent workflow you build, ask:
1. **Can this step be a WASM transform?** If it's a deterministic code modification (rename, convert syntax, strip comments), skip the LLM entirely.
2. **Does this step need Opus?** Only architecture, security, and complex multi-file reasoning need the most capable model. Everything else can use Haiku or Sonnet.
3. **Can I cache this?** If the same query pattern recurs (e.g., "check for security issues in auth code"), the answer from last time may still be relevant.

## Evidence & Examples

- [RuFlo](../entities/ruflo.md) — full 3-tier implementation with Q-learning router, WASM Agent Booster, and token optimizer.
- The pattern parallels the triage→specialise→validate pattern in [Agentic Workflow Patterns](agentic-workflow-patterns.md): use cheap models for triage, expensive models only for deep analysis.

## Tensions & Counterarguments

- Routing adds a decision step — if the router is wrong (sends a complex task to Haiku), the output is bad and needs to be redone, costing more than just using Opus.
- WASM transforms are limited to deterministic code modifications. Anything requiring semantic understanding must use an LLM.
- Token savings claims (30–50%) depend heavily on workload. Research/creative tasks benefit less than repetitive coding tasks.

## Related

- [Agentic Workflow Patterns](agentic-workflow-patterns.md)
- [Self-Learning Agent Architecture](self-learning-agent-architecture.md)
- [RuFlo](../entities/ruflo.md)

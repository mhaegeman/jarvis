---
title: Swarm Coordination Topologies
type: concept
tags: [multi-agent, swarm, coordination, agent-architecture, ruflo]
---

## Definition

Swarm coordination topologies are structural patterns that define how multiple AI agents communicate, delegate, and synchronize their work. Each topology has different trade-offs in terms of control, resilience, scalability, and drift prevention.

## Why It Matters

Choosing the right topology is the single most impactful architectural decision when building multi-agent workflows. The wrong topology causes agent drift (agents going off-task), coordination overhead, or single points of failure. This page is the reference for selecting a topology based on task characteristics.

## The Four Core Topologies

### Hierarchical (Default, Anti-Drift)
```
Queen → Worker 1
      → Worker 2
      → Worker 3
```
- **How it works:** A coordinator (queen) assigns tasks, validates outputs, and enforces alignment. Workers report back to the coordinator.
- **When to use:** Structured development tasks, feature implementation, any task where drift prevention is critical. **This is the default and recommended topology for most coding work.**
- **Anti-drift properties:** Single coordinator validates each output against the goal. Clear authority chain. Fewer agents = less drift surface.
- **Weakness:** Coordinator is a bottleneck and single point of failure.

### Mesh (Peer-to-Peer)
```
Agent ↔ Agent
  ↕         ↕
Agent ↔ Agent
```
- **How it works:** All agents communicate directly with each other. No central coordinator.
- **When to use:** Research and exploration tasks where agents need to share findings freely. Code review where multiple perspectives are equally valid.
- **Strength:** No bottleneck, resilient to individual agent failures.
- **Weakness:** High coordination overhead, prone to drift without strong consensus.

### Ring (Sequential Pipeline)
```
Agent → Agent → Agent → Agent
  ↑                       ↓
  └───────────────────────┘
```
- **How it works:** Each agent processes the output of the previous one and passes it forward. The pipeline loops for iterative refinement.
- **When to use:** Sequential workflows where each step builds on the previous (e.g., SPARC: Specification → Pseudocode → Architecture → Refinement → Completion).
- **Strength:** Clear data flow, each agent has focused context.
- **Weakness:** Slow (sequential), single agent failure blocks the pipeline.

### Star (Centralized Hub)
```
        Agent
          ↑
Agent ← Hub → Agent
          ↓
        Agent
```
- **How it works:** A central hub coordinates all communication. Agents only talk to the hub.
- **When to use:** When one agent needs to aggregate information from multiple sources (e.g., a summarizer collecting findings from parallel analysts).
- **Strength:** Simple coordination, easy to monitor.
- **Weakness:** Hub is a bottleneck and single point of failure.

### Adaptive (Auto-Switching)
- **How it works:** Starts with one topology and switches based on real-time performance metrics (load, drift, latency).
- **When to use:** Unknown task types where the optimal topology isn't clear upfront.
- **Implemented by:** RuFlo's adaptive-coordinator agent.

## When to Use Swarms vs. Single Agent

| Use Swarm | Skip Swarm |
|-----------|------------|
| 3+ files need changes | Single-file edit |
| New feature implementation | Simple bug fix |
| Cross-module refactoring | Documentation update |
| API changes requiring tests | Config change |
| Security audit | Formatting |
| Performance optimization | |

## Evidence & Examples

- [RuFlo](../entities/ruflo.md) — implements all 4 topologies + adaptive, with anti-drift defaults (hierarchical + maxAgents 6–8 + specialized strategy + Raft consensus).
- [Agentic Workflow Patterns](agentic-workflow-patterns.md) — the triage→specialise→validate pattern maps to a hierarchical topology with validation gate.

## Tensions & Counterarguments

- More agents = more cost and latency. The coordination overhead of a swarm may not be justified for tasks that a single well-prompted agent can handle.
- Topology choice is task-dependent, but most real-world coding tasks are best served by hierarchical — the other topologies are for specialized use cases.
- Agent drift in mesh topologies requires consensus protocols to mitigate — see [Multi-Agent Consensus Protocols](multi-agent-consensus-protocols.md).

## Related

- [Multi-Agent Consensus Protocols](multi-agent-consensus-protocols.md)
- [Agentic Workflow Patterns](agentic-workflow-patterns.md)
- [Intelligent Task Routing](intelligent-task-routing.md)
- [RuFlo](../entities/ruflo.md)

---
title: Multi-Agent Consensus Protocols
type: concept
tags: [multi-agent, consensus, fault-tolerance, coordination, ruflo]
---

## Definition

Consensus protocols are algorithms that allow multiple AI agents to agree on shared state, make collective decisions, and continue operating correctly even when some agents fail or produce bad outputs. They are the fault-tolerance layer for multi-agent workflows.

## Why It Matters

Without consensus, multi-agent swarms degrade unpredictably: one agent's bad output can cascade, conflicting decisions go unresolved, and there's no mechanism to recover from failures. Consensus protocols make swarms reliable enough for production use.

## The Five Protocols

### Raft (Leader-Based, Strong Consistency)
- **How it works:** One agent is elected leader. All decisions go through the leader. If the leader fails, a new one is elected.
- **Fault tolerance:** Handles f < n/2 failing agents (majority must be alive).
- **When to use:** Default for coding tasks. The leader (queen) maintains authoritative state and prevents conflicting decisions.
- **Trade-off:** Strong consistency but leader is a bottleneck.

### Byzantine Fault Tolerance (BFT)
- **How it works:** Agents vote on decisions. An output is accepted only if 2/3+ agents agree. Designed to handle agents that are not just failing but actively producing bad results.
- **Fault tolerance:** Handles f < n/3 faulty agents (including adversarial ones).
- **When to use:** When agent outputs can't be trusted blindly — e.g., code review where you want multiple independent assessments to agree before accepting a finding.
- **Trade-off:** High communication overhead (O(n²) messages per decision), but strongest safety guarantee.

### Gossip (Eventual Consistency)
- **How it works:** Agents randomly share state with peers. Information propagates probabilistically. All agents eventually converge on the same state.
- **Fault tolerance:** Extremely resilient — works even with high failure rates.
- **When to use:** Large-scale swarms where strict consistency isn't needed. Research tasks, broad exploration, background monitoring.
- **Trade-off:** No strong consistency — agents may temporarily disagree.

### CRDT (Conflict-Free Replicated Data Types)
- **How it works:** Data structures that can be independently updated on different agents and automatically merged without conflicts. Mathematical guarantee of convergence.
- **Fault tolerance:** Handles arbitrary concurrent updates.
- **When to use:** Shared memory where multiple agents write concurrently (e.g., shared knowledge bases, collaborative documentation).
- **Trade-off:** Only works for specific data structure patterns (counters, sets, maps).

### Quorum (Tunable Consistency)
- **How it works:** Configurable number of agents must agree for a read/write to succeed. Adjust R (read quorum) and W (write quorum) based on needs.
- **Fault tolerance:** Tunable — stricter quorum = stronger consistency = lower availability.
- **When to use:** When you need to balance consistency and availability based on the specific task.
- **Trade-off:** Requires careful tuning.

## Decision Matrix

| Need | Protocol | Why |
|------|----------|-----|
| Default for coding | Raft | Leader prevents conflicts, simple |
| Can't trust agent outputs | BFT | Majority vote catches bad outputs |
| Large-scale exploration | Gossip | Resilient, low overhead |
| Shared memory writes | CRDT | Conflict-free by construction |
| Custom trade-offs | Quorum | Tunable consistency/availability |

## Evidence & Examples

- [RuFlo](../entities/ruflo.md) — implements all 5 protocols, recommends Raft as default for coding with hierarchical topology.
- BFT is the protocol behind RuFlo's Hive-Mind coordination where 3 queen types (Strategic, Tactical, Adaptive) vote on decisions with weighted voting (Queen 3x weight).

## Related

- [Swarm Coordination Topologies](swarm-coordination-topologies.md)
- [Agentic Workflow Patterns](agentic-workflow-patterns.md)
- [Claims-Based Agent Authorization](claims-based-agent-authorization.md)
- [RuFlo](../entities/ruflo.md)

---
title: "ruvnet / RuFlo"
type: source
date_ingested: 2026-04-13
source_file: raw/ruvnet-ruflo.md
source_url: https://github.com/ruvnet/ruflo
tags: [
  github, open-source, mit-license,
  multi-agent-orchestration, claude-code, mcp,
  swarm-coordination, consensus-protocols, fault-tolerance,
  self-learning, reinforcement-learning, sona, ewc,
  vector-search, hnsw, embeddings, knowledge-graph,
  wasm, rust, typescript, node-js,
  cost-optimization, token-optimization, model-routing,
  sparc-methodology, spec-driven-development,
  claims-authorization, agent-security,
  hive-mind, queen-worker-pattern,
  hooks-automation, background-workers,
  reuven-cohen, agentics-foundation,
  agent-workflow-reference
]
---

## Summary

RuFlo (formerly Claude Flow) is a comprehensive multi-agent AI orchestration platform that transforms Claude Code into a coordinated agent development environment. Built by Reuven Cohen (@ruv), it enables deploying 100+ specialized agents in coordinated swarms with self-learning capabilities, fault-tolerant consensus, and enterprise-grade security. At v3.5 with 6,000+ commits, it is the most feature-complete Claude Code agent orchestration framework currently available.

The system operates on three layers: a **CLI** for direct commands (`npx ruflo`), an **MCP server** exposing 313+ tools to Claude Code, and a **skills system** with 137+ pre-built skills. The architecture follows a request flow: User → Router (Q-learning + MoE with 8 experts) → Hooks (pre/post-task automation) → Swarm Coordination (4 topologies, 5 consensus protocols) → Specialized Agents → LLM Providers (Claude, GPT, Gemini, Cohere, Ollama with auto-failover). The intelligence layer (RuVector) adds self-learning via SONA pattern learning, HNSW vector memory, ReasoningBank pattern storage, and 9 RL algorithms.

The platform's core value proposition is enabling Claude Code to go from single-agent isolation to coordinated multi-agent workflows that learn from experience, route tasks to cost-optimal models, and maintain cross-session memory. It directly addresses the problem of agent drift in long-running tasks through hierarchical coordination, consensus protocols, and spec-driven development.

## Tech Stack

- **Runtime:** Node.js 20+, TypeScript
- **WASM kernels:** Rust (policy engine, embeddings, proof system)
- **Agent orchestration:** MCP (Model Context Protocol), hooks system, swarm manager
- **Vector search:** HNSW (sub-millisecond), ONNX Runtime (MiniLM embeddings, 384 dimensions)
- **Databases:** SQLite (cache, WAL mode), AgentDB (persistent memory), RuVector PostgreSQL (77+ SQL functions)
- **Self-learning:** SONA (Self-Optimizing Pattern Learning), EWC++ (catastrophic forgetting prevention), MoE (8 experts), 9 RL algorithms (Q-Learning, SARSA, A2C, PPO, DQN, etc.)
- **Security:** AIDefence (<10ms threat detection), Zod validation, bcrypt, prompt injection detection
- **LLM providers:** Anthropic (Claude), OpenAI (GPT), Google (Gemini), Cohere, Ollama (local)
- **Package:** npm (`ruflo@latest`), also available via curl installer

## Purpose

RuFlo solves the problem of coordinating multiple AI agents working on complex software engineering tasks. It is for developers and teams using Claude Code who need agents to collaborate, share memory, learn from past work, and operate autonomously on large tasks without drifting from their goals. The primary user action is initializing a project with `npx ruflo init`, then using Claude Code normally — the hooks system automatically routes tasks to specialized agents in the background.

## Key Points

### Swarm Coordination
- **4 topologies:** hierarchical (default, anti-drift), mesh (peer-to-peer exploration), ring (sequential pipeline), star (centralized hub)
- **5 consensus protocols:** Raft (leader-based, strong consistency), Byzantine fault tolerance (handles f < n/3 failing agents), Gossip (eventual consistency, large scale), CRDT (conflict-free concurrent updates), Quorum (tunable consistency)
- **Hive-Mind:** Queen-led coordination with 3 queen types (Strategic, Tactical, Adaptive) and 8 worker types (Researcher, Coder, Analyst, Tester, Architect, Reviewer, Optimizer, Documenter)
- **Anti-drift defaults:** hierarchical topology + maxAgents 6-8 + specialized strategy + Raft consensus — coordinator validates each output against the goal

### Agent Architecture
- **100+ specialized agents** spanning: core (coder, planner, researcher, reviewer, tester), consensus (byzantine, raft, gossip, crdt, quorum coordinators), development (backend API, architecture, mobile), operations (CI/CD, GitHub PR, release management), security, performance, and memory management
- **Agent spawning:** `npx ruflo agent spawn -t coder --name my-coder` or via MCP tool `agent_spawn`
- **Claims-based authorization:** granular permissions (read/write/execute/spawn/memory/network/admin) with glob-pattern scoping — e.g., grant write only to `/src/**`
- **Swarm trigger threshold:** use swarms when 3+ files need changes, cross-module refactoring, API changes with tests, security changes. Skip for single-file edits and simple fixes.

### Intelligent Task Routing (3-Tier)
- **Tier 1 — Agent Booster (WASM):** simple code transforms (var→const, add-types, remove-console) in <1ms, $0 cost, zero tokens
- **Tier 2 — Haiku/Sonnet:** bug fixes, refactoring, feature implementation. 500ms–2s, low cost
- **Tier 3 — Opus:** architecture, security design, distributed systems. 2–5s, highest quality
- **Routing mechanism:** Q-learning with epsilon-greedy exploration, sub-millisecond decision latency
- **Result:** 75% API cost reduction, 30–50% token savings via compression + caching

### Self-Learning Memory
- **HNSW vector memory:** sub-millisecond retrieval, 384-dimension embeddings, ONNX Runtime
- **Hierarchical memory tiers:** Working (active context, 1MB limit) → Episodic (recent patterns, importance-ranked) → Semantic (consolidated, persistent)
- **Knowledge graph:** PageRank + community detection identifies influential insights; LearningBridge connects insights to SONA/ReasoningBank
- **Agent-scoped memory:** 3 scopes (project/local/user) with cross-agent transfer (1.25ms)
- **Cross-session persistence:** `session-restore` hook loads previous context; `session-end` saves state + metrics
- **Mandatory memory protocol:** every agent writes status on start, progress after each step, artifacts to `swarm/shared/`, and completion markers

### SPARC Methodology
5-phase structured development workflow: **Specification** → **Pseudocode** → **Architecture** → **Refinement** → **Completion**. Enforced via agent pipeline with 17+ named modes (spec-pseudocode, architect, integration, dev, api, ui, test, refactor). Prevents implementation drift by generating ADRs (Architecture Decision Records) before code.

### Hooks System
- **Pre-operation:** pre-edit (syntax validation, conflict check, agent assignment), pre-bash (safety check, destructive command confirmation), pre-task (auto-spawn agents, load memory, estimate complexity), pre-search (cache check)
- **Post-operation:** post-edit (auto-format, store in memory, train patterns), post-bash (log execution), post-search (cache results)
- **Session hooks:** session-end (saves state), session-restore (loads context)
- Configured in `.claude/settings.json` via `PreToolUse`/`PostToolUse` matchers

### Governance & Security
- **@claude-flow/guidance:** 7-phase governance pipeline (Compile → Retrieve → Enforce → Trust → Prove → Defend → Evolve) that turns CLAUDE.md into runtime policy enforcement
- **4 enforcement gates** the model cannot bypass: destructive ops, tool allowlist, diff size, secrets
- **Per-agent trust accumulation** with privilege tiers and coherence-driven throttling
- **HMAC-SHA256 hash-chained proof envelopes** for cryptographic run auditing
- **AIDefence:** prompt injection, memory poisoning, and inter-agent collusion detection (<10ms)

### MCP Integration
- **313+ MCP tools** exposed to Claude Code
- **Key tools:** `swarm_init`, `agent_spawn`, `memory_search`, `memory_store`, `hooks_route`, `neural_train`, `neural_patterns`, `performance_report`
- **Tool groups:** create, issue, branch, implement, test, fix, optimize, monitor, security, memory
- **Preset modes:** develop, pr-review, devops, triage — controls which tools are loaded
- **Compatible with:** Claude Code, Claude Desktop, VS Code, Cursor, Windsurf, ChatGPT, Google AI Studio, JetBrains IDEs

### Dual-Mode (Claude Code + Codex)
- Claude Code for interactive reasoning + headless Codex workers for parallel background tasks
- Pre-built collaboration templates: feature (architect→coder→tester→reviewer), security (scanner→analyzer→fixer), refactor (analyzer→planner→refactorer→validator)
- 4–8x faster for bulk tasks via parallel execution

## Quotes

> Claude Flow is now Ruflo — named by Ruv, who loves Rust, flow states, and building things that feel inevitable. The "Ru" is the Ruv. The "flo" is the flow. Underneath, WASM kernels written in Rust power the policy engine, embeddings, and proof system.

> You don't need to learn 310+ MCP tools or 26 CLI commands. After running `init`, just use Claude Code normally — the hooks system automatically routes tasks to the right agents, learns from successful patterns, and coordinates multi-agent work in the background.

## Connections

- [Claude Code](../entities/claude-code.md) — RuFlo is built as an extension/orchestration layer on top of Claude Code
- [RuFlo](../entities/ruflo.md) — entity page for the product
- [Agentic Workflow Patterns](../concepts/agentic-workflow-patterns.md) — RuFlo implements and extends every pattern documented there
- [Swarm Coordination Topologies](../concepts/swarm-coordination-topologies.md) — concept page for the 4 topology patterns
- [Multi-Agent Consensus Protocols](../concepts/multi-agent-consensus-protocols.md) — concept page for fault-tolerant coordination
- [Self-Learning Agent Architecture](../concepts/self-learning-agent-architecture.md) — concept page for SONA/EWC++/ReasoningBank
- [Intelligent Task Routing](../concepts/intelligent-task-routing.md) — concept page for 3-tier cost optimization
- [SPARC Methodology](../concepts/sparc-methodology.md) — concept page for spec-driven development
- [Claims-Based Agent Authorization](../concepts/claims-based-agent-authorization.md) — concept page for agent security

## Questions Raised

- How stable is v3.5 in production? The repo has 6,000+ commits but the README's feature claims are ambitious — how much is implemented vs. aspirational?
- What's the actual token overhead of running the MCP server and hooks system? The 30–50% savings claim needs validation against real workloads.
- How does RuFlo compare to the native Claude Code Agent tool for spawning sub-agents? At what complexity threshold does RuFlo's coordination overhead become worthwhile?
- Could RuFlo's swarm patterns be used for GuardRail's automated AI system detection — spawning specialized agents to scan different parts of a codebase in parallel?

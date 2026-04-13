---
title: RuFlo
type: entity
entity_type: product
tags: [multi-agent-orchestration, claude-code, mcp, open-source, agent-framework]
---

## Overview

RuFlo (formerly Claude Flow) is an open-source, MIT-licensed multi-agent AI orchestration platform that extends Claude Code with coordinated swarms, self-learning memory, intelligent task routing, and enterprise-grade security. Built by Reuven Cohen (@ruv) and the Agentics Foundation, it is the most feature-complete Claude Code agent orchestration framework available as of April 2026, with 100+ agents, 137+ skills, 313+ MCP tools, and 6,000+ commits.

## Key Facts

- **GitHub:** [ruvnet/ruflo](https://github.com/ruvnet/ruflo) — MIT license
- **Install:** `npx ruflo@latest init` or curl one-liner
- **Version:** v3.5 (renamed from Claude Flow)
- **Tech:** TypeScript + Rust/WASM kernels + MCP + ONNX Runtime
- **MCP tools:** 313+ tools exposed to Claude Code and other MCP clients
- **Agents:** 100+ specialized types (coder, tester, reviewer, architect, security, etc.)
- **Skills:** 137+ pre-built (swarm, SPARC, GitHub, hive-mind, AgentDB, etc.)
- **Topologies:** hierarchical, mesh, ring, star, adaptive
- **Consensus:** Raft, Byzantine, Gossip, CRDT, Quorum
- **Providers:** Claude, GPT, Gemini, Cohere, Ollama with auto-failover
- **Created by:** Reuven Cohen (@ruv), Agentics Foundation

## Appearances

- [ruvnet / RuFlo](../sources/ruvnet-ruflo.md) — full documentation ingest from GitHub repo

## Connections

- [Claude Code](claude-code.md) — RuFlo is built as an orchestration layer on top of Claude Code via MCP
- [Agentic Workflow Patterns](../concepts/agentic-workflow-patterns.md) — RuFlo implements every observed pattern and adds swarm coordination, consensus, and self-learning
- [Swarm Coordination Topologies](../concepts/swarm-coordination-topologies.md) — core architectural concept
- [Multi-Agent Consensus Protocols](../concepts/multi-agent-consensus-protocols.md) — fault-tolerance layer
- [Self-Learning Agent Architecture](../concepts/self-learning-agent-architecture.md) — intelligence layer
- [Intelligent Task Routing](../concepts/intelligent-task-routing.md) — cost optimization layer
- [SPARC Methodology](../concepts/sparc-methodology.md) — development methodology
- [Claims-Based Agent Authorization](../concepts/claims-based-agent-authorization.md) — security model

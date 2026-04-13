---
title: Claims-Based Agent Authorization
type: concept
tags: [agent-security, authorization, multi-agent, claims, ruflo]
---

## Definition

Claims-based agent authorization is a granular permission system for multi-agent workflows where each agent is granted specific capabilities (claims) scoped to specific resources. It prevents agents from accessing files, spawning sub-agents, or executing commands beyond their assigned role.

## Why It Matters

In a multi-agent swarm, not every agent should have the same permissions. A code reviewer shouldn't be able to write files. A test runner shouldn't be able to push to production. Without authorization, a misbehaving or compromised agent can cause damage proportional to the broadest permissions in the system — violating the principle of least privilege.

## Claim Types

| Claim | Capability |
|-------|-----------|
| `read` | Read files, search code |
| `write` | Create and modify files |
| `execute` | Run shell commands |
| `spawn` | Create sub-agents |
| `memory` | Access shared memory store |
| `network` | Make external API calls |
| `admin` | Full access, manage other agents |

## Security Levels

| Level | Claims | Use Case |
|-------|--------|----------|
| `minimal` | read | Research, exploration, code review |
| `standard` | read, write, execute | Development, bug fixing |
| `elevated` | read, write, execute, spawn, memory | Orchestration, swarm coordination |
| `admin` | all | System administration, deployment |

## Scope Patterns

Claims are scoped using glob patterns:
- `/src/**` — all files under src/
- `/config/*.toml` — only TOML config files
- `memory:patterns` — only the patterns namespace in memory
- `/tests/**` — test files only

## Practical Usage

```bash
# Grant write access to src/ only
npx ruflo claims grant --agent coder-1 --claim write --scope "/src/**"

# Grant read-only access to a reviewer
npx ruflo claims grant --agent reviewer-1 --claim read --scope "/**"

# Check if an agent has a specific claim
npx ruflo claims check --agent coder-1 --claim write

# Revoke access after task completion
npx ruflo claims revoke --agent coder-1 --claim write

# List all claims for an agent
npx ruflo claims list --agent coder-1
```

## When to Use

| Use Claims | Skip Claims |
|------------|-------------|
| Multi-agent swarms with specialized roles | Single-agent local development |
| Sensitive file access (credentials, config) | Open-access sandbox environments |
| Production operations (deployment, DB) | Exploration and prototyping |
| Untrusted or third-party agent skills | Trusted first-party agents only |

## Evidence & Examples

- [RuFlo](../entities/ruflo.md) — full claims implementation with CLI and MCP tool support, integrated with the swarm coordination layer.
- The pattern is analogous to RBAC (Role-Based Access Control) in traditional systems, but adapted for ephemeral AI agents.

## Related

- [Multi-Agent Consensus Protocols](multi-agent-consensus-protocols.md) — consensus is about agreement; claims are about authorization
- [Swarm Coordination Topologies](swarm-coordination-topologies.md) — the coordinator/queen typically has `elevated` or `admin` claims
- [RuFlo](../entities/ruflo.md)

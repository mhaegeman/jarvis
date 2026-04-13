---
title: SPARC Methodology
type: concept
tags: [spec-driven-development, development-methodology, agent-workflow, ruflo]
---

## Definition

SPARC is a 5-phase structured development methodology designed to prevent implementation drift in multi-agent coding workflows. Each phase is a distinct agent pipeline step, ensuring that code is specified and designed before it is written.

**S**pecification → **P**seudocode → **A**rchitecture → **R**efinement → **C**ompletion

## Why It Matters

Complex multi-agent tasks fail when implementation drifts from the original plan. In a swarm of 6–8 agents working in parallel, each agent can independently deviate from the spec. SPARC prevents this by enforcing a phased pipeline where architecture decisions are locked in ADRs (Architecture Decision Records) before any code is written — and agents are validated against the spec at each step.

## The Five Phases

### 1. Specification
- Define requirements, acceptance criteria, constraints.
- Output: clear task definition that all agents can reference.

### 2. Pseudocode
- High-level algorithm design, data flow, key decisions.
- Forces thinking through the approach before committing to implementation details.

### 3. Architecture
- System structure, interfaces, dependencies.
- Generates ADRs (Architecture Decision Records) that become the source of truth.
- DDD bounded contexts define clear boundaries between domains.

### 4. Refinement
- Iterate on design from feedback, user input, or test results.
- Update ADRs as requirements evolve.
- Drift detection: continuous monitoring flags when code diverges from spec.

### 5. Completion
- Tests, documentation, security review.
- Validation gates: `hooks progress` blocks merges that violate specifications.
- Living documentation: ADRs update automatically.

## Named SPARC Modes (17+)

| Mode | Purpose |
|------|---------|
| `spec-pseudocode` | Requirements → algorithm design |
| `architect` | System design, interfaces, ADRs |
| `integration` | Cross-module integration |
| `dev` | General development |
| `api` | API design and implementation |
| `ui` | User interface implementation |
| `test` | Test writing and validation |
| `refactor` | Code restructuring |
| `tdd` | Test-driven development flow |

## Practical Usage

```bash
# Run a SPARC mode for a specific task
npx ruflo sparc run architect "Design the authentication system"

# TDD-first feature development
npx ruflo sparc tdd "Add JWT refresh token rotation"

# Route a task through the full SPARC pipeline
npx ruflo sparc "Implement user onboarding flow"
```

Each phase is routed via hooks: `npx @claude-flow/cli hooks route --task "<phase>: <description>"`

## Evidence & Examples

- [RuFlo](../entities/ruflo.md) — full SPARC implementation with 17+ modes, ADR generation, drift detection, and validation gates.
- RuFlo itself uses 70+ ADRs to define its own system behavior — the methodology is self-hosting.

## Tensions & Counterarguments

- Overhead: for small tasks, the full 5-phase pipeline is overkill. SPARC is most valuable for tasks involving 3+ files or cross-module changes.
- ADRs can become stale if not maintained. The "living documentation" claim depends on the hooks system actually enforcing updates.
- The methodology assumes you can specify requirements upfront. Exploratory/research tasks may not fit a spec-first approach.

## Related

- [Agentic Workflow Patterns](agentic-workflow-patterns.md)
- [Swarm Coordination Topologies](swarm-coordination-topologies.md)
- [RuFlo](../entities/ruflo.md)

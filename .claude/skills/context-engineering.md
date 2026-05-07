---
name: context-engineering
description: Use when structuring context for LLM tasks, designing multi-step agent workflows, optimizing what goes into a context window, or applying systematic reasoning protocols to complex problems.
---

# Context Engineering

## Overview

Context engineering is the discipline of optimizing everything a language model sees beyond the initial prompt. As Andrej Karpathy defines it: *"the delicate art and science of filling the context window with just the right information for the next step."*

This skill covers reasoning protocols, workflow patterns, and structured schemas for getting the best output from LLMs.

Source: [davidkimai/Context-Engineering](https://github.com/davidkimai/Context-Engineering)

## When to Use

- Designing multi-step agent or LLM workflows
- When an LLM task requires systematic, traceable reasoning
- Structuring what context to provide for complex coding or analysis tasks
- When outputs are inconsistent and you need to constrain the reasoning process
- **Not for:** simple one-shot prompts, well-defined tasks with clear specs

## Core Reasoning Protocols

### Systematic Reasoning
For complex problems requiring traceable logic:
1. **Understand** — Restate the problem and clarify goals
2. **Analyze** — Break down into components
3. **Plan** — Design a step-by-step approach
4. **Execute** — Implement methodically
5. **Verify** — Validate against requirements
6. **Refine** — Improve based on verification

### Extended Thinking
For problems requiring deep consideration:
1. **Explore** — Consider multiple perspectives and approaches
2. **Evaluate** — Assess trade-offs of each approach
3. **Simulate** — Test mental models against edge cases
4. **Synthesize** — Integrate insights into coherent solution
5. **Articulate** — Express reasoning clearly

### Self-Reflection
For improving outputs iteratively:
1. **Assess** — completeness, correctness, clarity, effectiveness
2. **Identify** — strengths, weaknesses, implicit assumptions
3. **Improve** — plan and apply specific improvements

## Workflow Patterns

### Explore → Plan → Code → Commit
```
1. Read relevant files and understand the codebase (no code yet)
2. Create detailed implementation plan with alternatives
3. Write code following the plan, verify at each step
4. Commit with clear message and PR details
```

### Iterative UI Development
```
1. Analyze design requirements
2. Implement initial structure (structure before styling)
3. Screenshot and compare against design
4. Refine iteratively
5. Polish and commit with visual documentation
```

## Context Schemas

### Code Understanding
When analyzing a codebase, structure your understanding as:
- **Structure** — key files/directories and their purposes
- **Architecture** — overall architectural pattern
- **Technologies** — frameworks and libraries
- **Entry points** — main application flows
- **Data flow** — how data moves through the system
- **Quality** — strengths, concerns, recurring patterns

### Troubleshooting
When diagnosing issues, structure as:
- **Problem** — symptoms, context, impact
- **Diagnosis** — potential causes, evidence, verification steps
- **Solution** — approach, steps, verification, prevention

## Quick Reference

| Situation | Protocol |
|-----------|----------|
| Complex multi-step problem | Systematic reasoning (Understand → Verify) |
| Ambiguous or open-ended task | Extended thinking (Explore → Articulate) |
| Output needs improvement | Self-reflection (Assess → Improve) |
| Coding task | Explore → Plan → Code → Commit |
| Bug or failure | Bug diagnosis schema |
| Code review | Code analysis schema |

## Common Mistakes

| Problem | Fix |
|---------|-----|
| Jumping straight to implementation | Always explore and plan first |
| Vague context provided to LLM | Use structured schemas to organize inputs |
| Single-pass generation | Apply self-reflection protocol after first output |
| Ignoring edge cases | Explicitly simulate edge cases in planning phase |

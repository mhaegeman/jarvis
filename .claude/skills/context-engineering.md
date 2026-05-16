---
name: context-engineering
description: Use when structuring context for LLM tasks, designing multi-step agent workflows, optimizing what goes into a context window, or applying systematic reasoning protocols to complex problems.
---

# Context Engineering

## Overview

Discipline of optimizing everything LLM sees beyond initial prompt. Karpathy: *"delicate art and science of filling the context window with just the right information for the next step."*

Covers reasoning protocols, workflow patterns, structured schemas.

Source: [davidkimai/Context-Engineering](https://github.com/davidkimai/Context-Engineering)

## When to Use

- Multi-step agent/LLM workflows
- LLM task needs systematic, traceable reasoning
- Structuring context for complex coding/analysis
- Inconsistent outputs → constrain reasoning
- **Not for:** simple one-shot prompts, well-defined tasks w/ clear specs

## Core Reasoning Protocols

### Systematic Reasoning
Complex problems needing traceable logic:
1. **Understand** — restate problem, clarify goals
2. **Analyze** — break into components
3. **Plan** — step-by-step approach
4. **Execute** — implement methodically
5. **Verify** — validate vs requirements
6. **Refine** — improve from verification

### Extended Thinking
Problems needing deep consideration:
1. **Explore** — multiple perspectives/approaches
2. **Evaluate** — trade-offs of each
3. **Simulate** — test mental models vs edge cases
4. **Synthesize** — integrate into coherent solution
5. **Articulate** — express reasoning clearly

### Self-Reflection
Iterative output improvement:
1. **Assess** — completeness, correctness, clarity, effectiveness
2. **Identify** — strengths, weaknesses, implicit assumptions
3. **Improve** — plan + apply specific improvements

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
- **Structure** — key files/dirs + purposes
- **Architecture** — overall pattern
- **Technologies** — frameworks/libs
- **Entry points** — main flows
- **Data flow** — how data moves
- **Quality** — strengths, concerns, patterns

### Troubleshooting
- **Problem** — symptoms, context, impact
- **Diagnosis** — causes, evidence, verification steps
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
| Jumping to implementation | Explore + plan first |
| Vague context to LLM | Use structured schemas |
| Single-pass generation | Apply self-reflection after first output |
| Ignoring edge cases | Simulate edge cases in planning |

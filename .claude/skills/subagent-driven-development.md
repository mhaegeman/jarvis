---
name: subagent-driven-development
description: Use when executing implementation plans with independent tasks in the current session
---

# Subagent-Driven Development

Execute plan by dispatching fresh subagent per task w/ two-stage review after each: spec compliance first, then code quality.

**Why subagents:** Delegate to specialized agents w/ isolated context. Craft instructions/context precisely → they stay focused, succeed. Never inherit your session context — construct exactly what they need. Preserves your context for coordination.

**Core principle:** Fresh subagent per task + two-stage review (spec then quality) = high quality, fast iteration

## When to Use

```dot
digraph when_to_use {
    "Have implementation plan?" [shape=diamond];
    "Tasks mostly independent?" [shape=diamond];
    "Stay in this session?" [shape=diamond];
    "subagent-driven-development" [shape=box];
    "executing-plans" [shape=box];
    "Manual execution or brainstorm first" [shape=box];

    "Have implementation plan?" -> "Tasks mostly independent?" [label="yes"];
    "Have implementation plan?" -> "Manual execution or brainstorm first" [label="no"];
    "Tasks mostly independent?" -> "Stay in this session?" [label="yes"];
    "Tasks mostly independent?" -> "Manual execution or brainstorm first" [label="no - tightly coupled"];
    "Stay in this session?" -> "subagent-driven-development" [label="yes"];
    "Stay in this session?" -> "executing-plans" [label="no - parallel session"];
}
```

## The Process

```dot
digraph process {
    rankdir=TB;

    subgraph cluster_per_task {
        label="Per Task";
        "Dispatch implementer subagent" [shape=box];
        "Implementer asks questions?" [shape=diamond];
        "Answer questions, provide context" [shape=box];
        "Implementer implements, tests, commits, self-reviews" [shape=box];
        "Dispatch spec reviewer subagent" [shape=box];
        "Spec reviewer confirms code matches spec?" [shape=diamond];
        "Implementer fixes spec gaps" [shape=box];
        "Dispatch code quality reviewer subagent" [shape=box];
        "Code quality reviewer approves?" [shape=diamond];
        "Implementer fixes quality issues" [shape=box];
        "Mark task complete in TodoWrite" [shape=box];
    }

    "Read plan, extract all tasks with full text, create TodoWrite" [shape=box];
    "More tasks remain?" [shape=diamond];
    "Dispatch final code reviewer for entire implementation" [shape=box];
    "Read finishing-a-development-branch skill" [shape=box style=filled fillcolor=lightgreen];

    "Read plan, extract all tasks with full text, create TodoWrite" -> "Dispatch implementer subagent";
    "Dispatch implementer subagent" -> "Implementer asks questions?";
    "Implementer asks questions?" -> "Answer questions, provide context" [label="yes"];
    "Answer questions, provide context" -> "Dispatch implementer subagent";
    "Implementer asks questions?" -> "Implementer implements, tests, commits, self-reviews" [label="no"];
    "Implementer implements, tests, commits, self-reviews" -> "Dispatch spec reviewer subagent";
    "Dispatch spec reviewer subagent" -> "Spec reviewer confirms code matches spec?";
    "Spec reviewer confirms code matches spec?" -> "Implementer fixes spec gaps" [label="no"];
    "Implementer fixes spec gaps" -> "Dispatch spec reviewer subagent" [label="re-review"];
    "Spec reviewer confirms code matches spec?" -> "Dispatch code quality reviewer subagent" [label="yes"];
    "Dispatch code quality reviewer subagent" -> "Code quality reviewer approves?";
    "Code quality reviewer approves?" -> "Implementer fixes quality issues" [label="no"];
    "Implementer fixes quality issues" -> "Dispatch code quality reviewer subagent" [label="re-review"];
    "Code quality reviewer approves?" -> "Mark task complete in TodoWrite" [label="yes"];
    "Mark task complete in TodoWrite" -> "More tasks remain?";
    "More tasks remain?" -> "Dispatch implementer subagent" [label="yes"];
    "More tasks remain?" -> "Dispatch final code reviewer for entire implementation" [label="no"];
    "Dispatch final code reviewer for entire implementation" -> "Read finishing-a-development-branch skill";
}
```

## Model Selection

Use least powerful model that handles role → conserve cost, increase speed.

- **Mechanical impl** (isolated fns, clear specs, 1-2 files): fast/cheap model
- **Integration/judgment** (multi-file, pattern matching, debugging): standard model
- **Architecture/design/review**: most capable model

**Complexity signals:**
- 1-2 files w/ complete spec → cheap
- Multi-file w/ integration → standard
- Design judgment / broad codebase understanding → most capable

## Handling Implementer Status

Four statuses:

**DONE:** Proceed to spec compliance review.

**DONE_WITH_CONCERNS:** Read concerns. Correctness/scope → address before review. Observations (e.g., "file getting large") → note, proceed.

**NEEDS_CONTEXT:** Provide missing context, re-dispatch.

**BLOCKED:** Assess:
1. Context problem → more context, re-dispatch same model
2. Needs more reasoning → re-dispatch w/ more capable model
3. Task too large → break into smaller pieces
4. Plan wrong → escalate to user

**Never** ignore escalation or force same model to retry w/o changes.

## Prompt Templates

In `.claude/skills/subagent-driven-development/`:
- `implementer-prompt.md`
- `spec-reviewer-prompt.md`
- `code-quality-reviewer-prompt.md`

## Red Flags

**Never:**
- Start impl on main/master w/o explicit user consent
- Skip reviews (spec OR quality)
- Proceed w/ unfixed issues
- Dispatch multiple implementation subagents in parallel (conflicts)
- Make subagent read plan file (provide full text)
- Skip scene-setting context (subagent needs to know where task fits)
- Ignore subagent questions (answer before proceeding)
- Accept "close enough" on spec compliance
- **Start code quality review before spec compliance ✅** (wrong order)
- Move to next task while either review has open issues

**If reviewer finds issues:**
- Same implementer subagent fixes
- Reviewer re-reviews
- Repeat until approved
- Don't skip re-review

## Integration

**Required workflow skills:**
- **using-git-worktrees** — REQUIRED: isolated workspace before starting
- **writing-plans** — creates plan this skill executes
- **requesting-code-review** — template for reviewer subagents
- **finishing-a-development-branch** — complete after all tasks

**Subagents use:**
- **test-driven-development** — subagents follow TDD per task

---
name: executing-plans
description: Use when you have a written implementation plan to execute in a separate session with review checkpoints
---

# Executing Plans

## Overview

Load plan, review critically, execute tasks, report when done.

**Announce at start:** "I'm using the executing-plans skill to implement this plan."

If subagents available → use subagent-driven-development instead (higher quality via fresh context + two-stage review).

## The Process

### Step 1: Load and Review Plan
1. Read plan file
2. Review critically; identify questions/concerns
3. Concerns → raise w/ user before starting
4. No concerns → TodoWrite + proceed

### Step 2: Execute Tasks

Per task:
1. Mark in_progress
2. Follow steps exactly
3. Run verifications as specified
4. Mark completed

### Step 3: Complete Development

After all tasks done + verified:
- Announce: "I'm using the finishing-a-development-branch skill to complete this work."
- Read `.claude/skills/finishing-a-development-branch.md`
- Follow it → verify tests, present options, execute choice

## When to Stop and Ask for Help

**STOP immediately when:**
- Blocker (missing dep, test fails, unclear instruction)
- Plan has critical gaps
- Don't understand an instruction
- Verification fails repeatedly

**Ask rather than guess.**

## When to Revisit Earlier Steps

**Return to Review (Step 1) when:**
- User updates plan based on feedback
- Approach needs rethinking

**Don't force through blockers** — stop and ask.

## Remember
- Review plan critically first
- Follow steps exactly
- Don't skip verifications
- Stop when blocked, don't guess
- Never start on main/master w/o explicit user consent

## Integration

**Required workflow skills:**
- **using-git-worktrees** — REQUIRED: isolated workspace before start
- **writing-plans** — creates the plan
- **finishing-a-development-branch** — complete after all tasks

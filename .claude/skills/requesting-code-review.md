---
name: requesting-code-review
description: Use when completing tasks, implementing major features, or before merging to verify work meets requirements
---

# Requesting Code Review

Dispatch code-reviewer subagent → catch issues before cascade. Reviewer gets crafted context, not your session history → stays focused on work product.

**Core principle:** Review early, review often.

## When to Request Review

**Mandatory:**
- After each task in subagent-driven dev
- After major feature
- Before merge to main

**Optional but valuable:**
- Stuck (fresh perspective)
- Before refactoring (baseline)
- After fixing complex bug

## How to Request

**1. Get git SHAs:**
```bash
BASE_SHA=$(git rev-parse HEAD~1)  # or origin/main
HEAD_SHA=$(git rev-parse HEAD)
```

**2. Dispatch code-reviewer subagent:**

Use Agent tool (general-purpose), fill template at `.claude/skills/requesting-code-review/code-reviewer.md`

**Placeholders:**
- `{WHAT_WAS_IMPLEMENTED}` — what you built
- `{PLAN_OR_REQUIREMENTS}` — what it should do
- `{BASE_SHA}` — starting commit
- `{HEAD_SHA}` — ending commit
- `{DESCRIPTION}` — brief summary

**3. Act on feedback:**
- Critical → fix immediately
- Important → fix before proceeding
- Minor → note for later
- Push back if reviewer wrong (w/ reasoning)

## Integration with Workflows

**Subagent-Driven Development:**
- Review after EACH task → catch before compound → fix before next task

**Executing Plans:**
- Review after each batch (3 tasks) → feedback → apply → continue

**Ad-Hoc Development:**
- Review before merge / when stuck

## Red Flags

**Never:**
- Skip review b/c "it's simple"
- Ignore Critical
- Proceed w/ unfixed Important

**If reviewer wrong:**
- Push back w/ technical reasoning
- Show code/tests proving it works

See template at: `.claude/skills/requesting-code-review/code-reviewer.md`

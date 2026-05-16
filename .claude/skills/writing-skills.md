---
name: writing-skills
description: Use when creating new skills, editing existing skills, or verifying skills work before deployment
---

# Writing Skills

## Overview

**Writing skills IS Test-Driven Development applied to process documentation.**

**Skills for this repo live in `.claude/skills/`**

Write test cases (pressure scenarios w/ subagents) → watch fail (baseline) → write skill (docs) → watch pass (agents comply) → refactor (close loopholes).

**Core principle:** If you didn't watch an agent fail w/o the skill, you don't know if skill teaches the right thing.

## What is a Skill?

**Skill** = reference guide for proven techniques, patterns, tools. Helps future Claude find + apply effective approaches.

**Skills are:** reusable techniques, patterns, tools, reference guides
**Skills are NOT:** narratives about how you solved a problem once

## TDD Mapping for Skills

| TDD Concept | Skill Creation |
|-------------|----------------|
| **Test case** | Pressure scenario with subagent |
| **Production code** | Skill document (SKILL.md) |
| **Test fails (RED)** | Agent violates rule without skill (baseline) |
| **Test passes (GREEN)** | Agent complies with skill present |
| **Refactor** | Close loopholes while maintaining compliance |

## When to Create a Skill

**Create when:**
- Technique not intuitively obvious
- You'd reference again across projects
- Pattern applies broadly (not project-specific)

**Don't create for:**
- One-off solutions
- Standard practices well-documented elsewhere
- Project-specific conventions (put in CLAUDE.md)

## Directory Structure

```
.claude/skills/
  skill-name.md              # Main reference (flat file for simple skills)
  skill-name/
    skill-name.md            # Or directory for skills with supporting files
    supporting-file.md
```

## SKILL.md Structure

**Frontmatter (YAML):**
- Required: `name`, `description`
- `name`: letters, numbers, hyphens only
- `description`: third-person, describes ONLY when to use (NOT what it does)
  - Start w/ "Use when..." → focus on triggers
  - **NEVER summarize the skill's process or workflow**
  - Keep under 500 chars if possible

```markdown
---
name: skill-name
description: Use when [specific triggering conditions and symptoms]
---

# Skill Name

## Overview
What is this? Core principle in 1-2 sentences.

## When to Use
[Small inline flowchart IF decision non-obvious]
Bullet list with SYMPTOMS and use cases
When NOT to use

## Core Pattern (for techniques/patterns)
Before/after code comparison

## Quick Reference
Table or bullets for scanning common operations

## Common Mistakes
What goes wrong + fixes
```

## Claude Search Optimization (CSO)

**Critical for discovery:** future Claude needs to FIND your skill.

**The trap:** descriptions summarizing workflow create a shortcut Claude takes. Skill body becomes documentation Claude skips.

```yaml
# ❌ BAD: Summarizes workflow
description: Use when executing plans - dispatches subagent per task with code review between tasks

# ✅ GOOD: Just triggering conditions
description: Use when executing implementation plans with independent tasks in the current session
```

**Content:**
- Concrete triggers, symptoms, situations
- Third person
- **NEVER summarize the skill's process or workflow**

## Red Flags in Skill Design

| Problem | Fix |
|---------|-----|
| Description summarizes process | Change to only triggering conditions |
| Skill is project-specific | Move to CLAUDE.md instead |
| Skill duplicates existing skill | Merge or clarify distinction |
| Skill too long | Split into main + supporting files |
| No concrete examples | Add before/after code patterns |

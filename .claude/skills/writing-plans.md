---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans

## Overview

Write comprehensive plans assuming engineer has zero context for codebase + questionable taste. Document everything: which files per task, code, testing, docs to check, how to test. Whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume skilled developer but knows almost nothing about toolset/problem domain. Assume weak test design.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Context:** Run in dedicated worktree (created by brainstorming skill).

**Save plans to:** `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`

## Scope Check

Spec covers multiple independent subsystems → suggest breaking into separate plans, one per subsystem. Each plan produces working, testable software on its own.

## File Structure

Before tasks, map which files created/modified + each one's responsibility.

- Clear boundaries, well-defined interfaces. One responsibility per file.
- Prefer smaller focused files over large ones.
- Files that change together live together.
- Existing codebases → follow established patterns.

## Bite-Sized Task Granularity

**Each step = one action (2-5 min):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Plan Document Header

**Every plan MUST start w/ this header:**

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

## Task Structure

```markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
```

## No Placeholders

Every step contains actual content engineer needs. **Plan failures** — never write:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (w/o actual test code)
- "Similar to Task N" (repeat code — engineer may read out of order)
- Steps describing what w/o showing how (code blocks required for code steps)

## Remember
- Exact file paths always
- Complete code in every step — step changes code → show code
- Exact commands w/ expected output
- DRY, YAGNI, TDD, frequent commits

## Self-Review

After writing complete plan, look at spec w/ fresh eyes, check plan against it.

**1. Spec coverage:** Skim each section/requirement. Point to task that implements it. List gaps.

**2. Placeholder scan:** Search plan for red flags from "No Placeholders" above. Fix.

**3. Type consistency:** Types, method signatures, property names in later tasks match earlier?

Fix inline. No re-review. Spec requirement w/ no task → add task.

## Execution Handoff

After saving, offer execution choice:

**"Plan complete and saved to `docs/superpowers/plans/<filename>.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?"**

**Subagent-Driven chosen:** Read `.claude/skills/subagent-driven-development.md`

**Inline Execution chosen:** Read `.claude/skills/executing-plans.md`

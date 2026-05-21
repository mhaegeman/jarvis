# Code Quality Reviewer Prompt Template

Use when dispatching a code quality reviewer subagent.

**Purpose:** Verify implementation is well-built (clean, tested, maintainable)

**Only dispatch after spec compliance review passes.**

```
Agent tool (general-purpose):
  Use template at .claude/skills/requesting-code-review/code-reviewer.md

  WHAT_WAS_IMPLEMENTED: [from implementer's report]
  PLAN_OR_REQUIREMENTS: Task N from [plan-file]
  BASE_SHA: [commit before task]
  HEAD_SHA: [current commit]
  DESCRIPTION: [task summary]
```

**Beyond standard quality concerns, reviewer should check:**
- Does each file have one clear responsibility w/ well-defined interface?
- Are units decomposed → understood and tested independently?
- Implementation following file structure from plan?
- Did this create new files already large, or significantly grow existing files?

**Code reviewer returns:** Strengths, Issues (Critical/Important/Minor), Assessment

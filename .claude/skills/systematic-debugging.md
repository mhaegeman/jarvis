---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes
---

# Systematic Debugging

## Overview

Random fixes waste time, create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before fixes. Symptom fixes = failure.

**Violating the letter = violating the spirit.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

No Phase 1 → no fixes.

## When to Use

ANY technical issue: test failures, prod bugs, unexpected behavior, perf problems, build failures, integration issues.

**ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- Already tried multiple fixes
- Previous fix didn't work
- Don't fully understand the issue

## The Four Phases

MUST complete each before next.

### Phase 1: Root Cause Investigation

**BEFORE ANY fix:**

1. **Read Error Messages Carefully**
   - Don't skip errors/warnings — often contain exact solution
   - Read stack traces completely
   - Note line numbers, file paths, error codes

2. **Reproduce Consistently**
   - Trigger reliably? Exact steps? Every time?
   - Not reproducible → gather more data, don't guess

3. **Check Recent Changes**
   - What changed? Git diff, recent commits, new deps, config changes

4. **Gather Evidence in Multi-Component Systems**

   **WHEN multiple components:**

   **BEFORE proposing fixes, add diagnostic instrumentation:**
   ```
   For EACH component boundary:
     - Log what data enters component
     - Log what data exits component
     - Verify environment/config propagation
     - Check state at each layer

   Run once to gather evidence showing WHERE it breaks
   THEN analyze evidence to identify failing component
   THEN investigate that specific component
   ```

5. **Trace Data Flow**
   - Where does bad value originate?
   - What called this w/ bad value?
   - Trace up until source. Fix at source, not symptom.

   See `.claude/skills/systematic-debugging/root-cause-tracing.md` for backward tracing technique.

### Phase 2: Pattern Analysis

**Find pattern before fixing:**

1. **Find Working Examples** — similar working code in same codebase
2. **Compare Against References** — read reference COMPLETELY, don't skim
3. **Identify Differences** — list every difference between working/broken
4. **Understand Dependencies** — what other components needed?

### Phase 3: Hypothesis and Testing

**Scientific method:**

1. **Form Single Hypothesis** — "I think X is root cause because Y"
2. **Test Minimally** — SMALLEST change to test. One variable at a time.
3. **Verify Before Continuing** — Worked? Yes → Phase 4. No → NEW hypothesis.
4. **When You Don't Know** — Say "I don't understand X". Don't pretend.

### Phase 4: Implementation

**Fix root cause, not symptom:**

1. **Create Failing Test Case** — simplest reproduction, automated if possible
2. **Implement Single Fix** — root cause, ONE change, no "while I'm here" improvements
3. **Verify Fix** — test passes? Other tests OK? Issue resolved?

4. **If Fix Doesn't Work**
   - STOP
   - Count fixes tried
   - < 3: Return Phase 1, re-analyze w/ new info
   - **≥ 3: STOP and question architecture (step 5)**

5. **If 3+ Fixes Failed: Question Architecture**

   **STOP, question fundamentals:**
   - Pattern fundamentally sound?
   - "Sticking with it through sheer inertia"?
   - Refactor architecture vs. continue fixing symptoms?

   **Discuss w/ user before more fixes**

## Red Flags - STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Here are the main problems: [lists fixes without investigation]"
- **"One more fix attempt" (when already tried 2+)**

**ALL mean: STOP. Return Phase 1.**

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new hypothesis |
| **4. Implementation** | Create test, fix, verify | Bug resolved, tests pass |

## Supporting Techniques

In `.claude/skills/systematic-debugging/`:
- **`root-cause-tracing.md`** — trace bugs backward through call stack
- **`defense-in-depth.md`** — add validation at multiple layers after root cause
- **`condition-based-waiting.md`** — replace arbitrary timeouts w/ condition polling

**Related skills:**
- **test-driven-development** — failing test case (Phase 4, Step 1)
- **verification-before-completion** — verify fix before claiming success

---
name: dispatching-parallel-agents
description: Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies
---

# Dispatching Parallel Agents

## Overview

Delegate tasks to specialized agents w/ isolated context. Craft instructions + context precisely → agents stay focused, succeed. They never inherit your session — construct exactly what they need.

Multiple unrelated failures (different test files, subsystems, bugs) → sequential investigation wastes time. Independent investigations run in parallel.

**Core principle:** One agent per independent problem domain. Concurrent work.

## When to Use

**Use when:**
- 3+ test files failing w/ different root causes
- Multiple subsystems broken independently
- Each problem understandable w/o context from others
- No shared state between investigations

**Don't use when:**
- Failures related (one fix might fix others)
- Need full system state
- Agents would interfere

## The Pattern

### 1. Identify Independent Domains

Group failures by what's broken:
- File A tests: Tool approval flow
- File B tests: Batch completion behavior
- File C tests: Abort functionality

Each domain independent.

### 2. Create Focused Agent Tasks

Each agent gets:
- **Specific scope:** one test file/subsystem
- **Clear goal:** make these tests pass
- **Constraints:** don't change other code
- **Expected output:** summary of findings/fixes

### 3. Dispatch in Parallel

Agent tool multiple times in same message (parallel dispatch):
```
Agent 1 → Fix test-file-a.test.ts failures
Agent 2 → Fix test-file-b.test.ts failures  
Agent 3 → Fix test-file-c.test.ts failures
```

### 4. Review and Integrate

When agents return:
- Read each summary
- Verify fixes don't conflict
- Run full test suite
- Integrate all changes

## Agent Prompt Structure

Good prompts are:
1. **Focused** — one clear problem domain
2. **Self-contained** — all context needed
3. **Specific output** — what should agent return?

```markdown
Fix the 3 failing tests in src/agents/tool-abort.test.ts:

1. "should abort tool with partial output capture" - expects 'interrupted at' in message
2. "should handle mixed completed and aborted tools" - fast tool aborted instead of completed
3. "should properly track pendingToolCount" - expects 3 results but gets 0

These are timing/race condition issues. Your task:

1. Read the test file and understand what each test verifies
2. Identify root cause - timing issues or actual bugs?
3. Fix by:
   - Replacing arbitrary timeouts with event-based waiting
   - Fixing bugs in abort implementation if found

Do NOT just increase timeouts - find the real issue.

Return: Summary of what you found and what you fixed.
```

## Common Mistakes

**❌ Too broad:** "Fix all the tests" — agent lost
**✅ Specific:** "Fix tool-abort.test.ts" — focused scope

**❌ No context:** "Fix the race condition" — agent doesn't know where
**✅ Context:** paste error messages + test names

**❌ No constraints:** agent might refactor everything
**✅ Constraints:** "Do NOT change production code" / "Fix tests only"

**❌ Vague output:** "Fix it" — you don't know what changed
**✅ Specific:** "Return summary of root cause + changes"

## When NOT to Use

- **Related failures:** investigate together first
- **Need full context:** understanding requires whole system
- **Exploratory debugging:** you don't know what's broken
- **Shared state:** agents would interfere (same files/resources)

## Verification

After agents return:
1. **Review each summary** — understand changes
2. **Check conflicts** — same code edited?
3. **Run full suite** — fixes work together
4. **Spot check** — agents make systematic errors

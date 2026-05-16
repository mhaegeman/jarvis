# Condition-Based Waiting

## Overview

Flaky tests guess timing w/ arbitrary delays → race conditions: pass fast machines, fail under load/CI.

**Core principle:** Wait for actual condition, not a guess.

## When to Use

**Use when:**
- Arbitrary delays (`setTimeout`, `sleep`, `time.sleep()`)
- Flaky tests (pass sometimes, fail under load)
- Tests timeout in parallel
- Waiting for async ops

**Don't use when:**
- Testing actual timing behavior (debounce, throttle)
- Always document WHY if using arbitrary timeout

## Core Pattern

```typescript
// ❌ BEFORE: Guessing at timing
await new Promise(r => setTimeout(r, 50));
const result = getResult();
expect(result).toBeDefined();

// ✅ AFTER: Waiting for condition
await waitFor(() => getResult() !== undefined);
const result = getResult();
expect(result).toBeDefined();
```

## Quick Patterns

| Scenario | Pattern |
|----------|---------|
| Wait for event | `waitFor(() => events.find(e => e.type === 'DONE'))` |
| Wait for state | `waitFor(() => machine.state === 'ready')` |
| Wait for count | `waitFor(() => items.length >= 5)` |
| Wait for file | `waitFor(() => fs.existsSync(path))` |
| Complex condition | `waitFor(() => obj.ready && obj.value > 10)` |

## Implementation

Generic polling function:
```typescript
async function waitFor<T>(
  condition: () => T | undefined | null | false,
  description: string,
  timeoutMs = 5000
): Promise<T> {
  const startTime = Date.now();

  while (true) {
    const result = condition();
    if (result) return result;

    if (Date.now() - startTime > timeoutMs) {
      throw new Error(`Timeout waiting for ${description} after ${timeoutMs}ms`);
    }

    await new Promise(r => setTimeout(r, 10)); // Poll every 10ms
  }
}
```

Python equivalent:
```python
import time

def wait_for(condition, description, timeout_ms=5000):
    start = time.time() * 1000
    while True:
        result = condition()
        if result:
            return result
        if time.time() * 1000 - start > timeout_ms:
            raise TimeoutError(f"Timeout waiting for {description} after {timeout_ms}ms")
        time.sleep(0.01)  # Poll every 10ms
```

## Common Mistakes

**❌ Polling too fast:** `setTimeout(check, 1)` — wastes CPU. **✅ Fix:** poll every 10ms
**❌ No timeout:** loops forever. **✅ Fix:** always include timeout w/ clear error
**❌ Stale data:** cache state before loop. **✅ Fix:** call getter inside loop for fresh data

## When Arbitrary Timeout IS Correct

```typescript
// Waiting for timed behavior with known interval
await waitForEvent(manager, 'TOOL_STARTED'); // First: wait for condition
await new Promise(r => setTimeout(r, 200));   // Then: wait for timed behavior (2 ticks at 100ms)
// 200ms = documented and justified
```

**Requirements for arbitrary timeout:**
1. First wait for triggering condition
2. Based on known timing (not guessing)
3. Comment explaining WHY

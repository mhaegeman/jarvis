# Root Cause Tracing

## Overview

Trace bugs backward through call stack → find original trigger.

**Core principle:** Never fix where you see the problem — trace to where it starts.

## The Backward Tracing Technique

Error appears deep in call stack:

### Step 1: Start at the Error

Note exactly what failed:
- Unexpected value?
- Function that threw?
- Line?

### Step 2: Trace Backwards

Per call stack level, ask:
- Who called this function?
- What value did they pass?
- Where did they get that value?

Trace up until you find where bad value ORIGINATES.

```
Error: Cannot read property 'x' of undefined
  at processResult (processor.ts:45)
  at handleResponse (handler.ts:23)
  at fetchData (api.ts:67)

→ processResult received undefined result
→ handleResponse returned undefined result
→ fetchData returned undefined
→ fetchData's HTTP call failed silently
→ ROOT CAUSE: Missing error handling in fetchData (api.ts:67)
```

### Step 3: Fix at Source

Fix root cause, not symptom.

```
❌ Symptom fix: Add null check in processResult
✅ Root cause fix: Handle HTTP errors properly in fetchData
```

## Adding Diagnostic Instrumentation

Root cause not obvious → add logging per layer:

```typescript
// Layer 1: Entry point
console.log('[fetchData] called with:', url);

// Layer 2: After HTTP call
console.log('[fetchData] response status:', response.status);
console.log('[fetchData] response body:', await response.text());

// Layer 3: In handler
console.log('[handleResponse] received result:', result);

// Layer 4: In processor
console.log('[processResult] input:', result);
```

Run once w/ instrumentation → see exactly where bad value enters.

## Common Patterns

### Undefined/null propagation
```
Function A returns undefined when should return value
→ Function B receives undefined, doesn't check
→ Function C fails on undefined
ROOT CAUSE: Fix Function A's return value
```

### Silent failure
```
Operation fails but doesn't throw
→ Returns empty/default
→ Downstream behaves unexpectedly
ROOT CAUSE: Missing error propagation
```

### Wrong data shape
```
API returns { data: [...] }
Code expects [...]
ROOT CAUSE: Unhandled API response wrapper
```

## When to Use This Technique

- Stack traces w/ multiple levels
- "undefined is not a function" errors
- Data mysteriously becoming wrong
- Values that "shouldn't be" a certain way

## Quick Reference

1. Note exact error + location
2. Who called this?
3. What value passed?
4. Where did value come from?
5. Repeat until origin
6. Fix at origin, not symptom

# Defense in Depth

## Overview

After finding a root cause, add validation at multiple layers to prevent similar bugs from propagating silently in the future.

**Core principle:** Don't just fix the one place — make the system harder to break at every boundary.

## When to Use

After completing Phase 4 (Implementation) in systematic-debugging:
- Bug was caused by invalid data reaching a layer that assumed valid data
- Root cause was a missing check at a system boundary
- Fix was at the symptom level and you want to add deeper protection

## The Pattern

For each significant boundary in a multi-layer system, ask:
1. What data enters this layer?
2. What assumptions does this layer make about that data?
3. What happens if those assumptions are violated?
4. Should I add a check here?

## Layer Validation Examples

### API boundary
```typescript
// Validate at the entry point, not deep in processing
function handleRequest(req: Request): Response {
  // Defense: validate input early
  if (!req.body?.userId) {
    return { status: 400, error: 'userId required' };
  }
  return processUser(req.body.userId);
}
```

### Service boundary
```typescript
// Validate when crossing service boundaries
function processUser(userId: string): User {
  // Defense: assert invariant
  if (typeof userId !== 'string' || userId.length === 0) {
    throw new Error(`Invalid userId: ${JSON.stringify(userId)}`);
  }
  return db.findUser(userId);
}
```

### Data transformation
```typescript
// Validate shape after transformation
function transformApiResponse(raw: unknown): ProcessedData {
  const data = raw as ApiResponse;
  // Defense: verify expected shape
  if (!Array.isArray(data.items)) {
    throw new Error(`Expected items array, got: ${typeof data.items}`);
  }
  return data.items.map(transformItem);
}
```

## Calibration: When NOT to Add Defense

Don't add defensive checks everywhere:
- Internal functions called only by other internal functions with known-good data
- Hot paths where validation cost is significant
- When TypeScript/type system already enforces the invariant

Add defense at:
- External inputs (HTTP, file, env vars)
- Cross-service/cross-module boundaries
- After deserialization/parsing
- Where bugs have historically occurred

## Quick Reference

| Layer | What to validate |
|-------|-----------------|
| HTTP entry | Required fields, types, ranges |
| Service calls | Non-null, expected type, format |
| Data parsing | Shape matches expected schema |
| DB results | Not null when required, expected count |
| Config loading | Required env vars, valid values |

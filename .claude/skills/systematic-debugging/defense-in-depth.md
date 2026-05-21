# Defense in Depth

## Overview

After finding root cause, add validation at multiple layers → prevent similar bugs propagating silently.

**Core principle:** Don't just fix one place — make system harder to break at every boundary.

## When to Use

After Phase 4 (Implementation) in systematic-debugging:
- Bug caused by invalid data reaching layer that assumed valid data
- Root cause = missing check at system boundary
- Fix at symptom level → want deeper protection

## The Pattern

Per significant boundary in multi-layer system, ask:
1. What data enters this layer?
2. What assumptions does layer make about data?
3. What if assumptions violated?
4. Add a check?

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

Don't defend everywhere:
- Internal functions called only by other internal functions w/ known-good data
- Hot paths where validation cost significant
- Type system already enforces invariant

Add defense at:
- External inputs (HTTP, file, env vars)
- Cross-service/cross-module boundaries
- After deserialization/parsing
- Where bugs historically occurred

## Quick Reference

| Layer | What to validate |
|-------|-----------------|
| HTTP entry | Required fields, types, ranges |
| Service calls | Non-null, expected type, format |
| Data parsing | Shape matches expected schema |
| DB results | Not null when required, expected count |
| Config loading | Required env vars, valid values |

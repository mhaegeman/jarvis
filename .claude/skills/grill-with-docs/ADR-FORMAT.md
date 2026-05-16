# ADR Format

ADRs live in `docs/adr/`, sequential numbering: `0001-slug.md`, `0002-slug.md`, etc.

Create `docs/adr/` lazily — only when first ADR needed.

## Template

```md
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

That's it. ADR can be a single paragraph. Value = recording *that* a decision was made and *why* — not filling sections.

## Optional sections

Include only when they add genuine value. Most ADRs won't need them.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) — when decisions revisited
- **Considered Options** — when rejected alternatives worth remembering
- **Consequences** — when non-obvious downstream effects must be called out

## Numbering

Scan `docs/adr/` for highest existing number, +1.

## When to offer an ADR

All three must be true:

1. **Hard to reverse** — cost of changing mind is meaningful
2. **Surprising w/o context** — future reader wonders "why on earth did they do it this way?"
3. **Real trade-off** — genuine alternatives existed; picked one for specific reasons

Easy to reverse → skip. Not surprising → nobody wonders. No real alternative → nothing to record beyond "we did the obvious thing."

### What qualifies

- **Architectural shape.** "Monorepo." "Write model event-sourced, read model projected into Postgres."
- **Integration patterns between contexts.** "Ordering and Billing communicate via domain events, not synchronous HTTP."
- **Tech choices w/ lock-in.** Database, message bus, auth provider, deployment target. Not every library — just ones that'd take a quarter to swap.
- **Boundary/scope decisions.** "Customer data owned by Customer context; others reference by ID only." Explicit no-s as valuable as yes-s.
- **Deliberate deviations from obvious path.** "Manual SQL instead of an ORM because X." Anything where reasonable reader would assume opposite. Stops next engineer from "fixing" something deliberate.
- **Constraints not visible in code.** "Can't use AWS — compliance." "Response times <200ms — partner API contract."
- **Rejected alternatives when rejection non-obvious.** Considered GraphQL, picked REST for subtle reasons → record, else someone suggests GraphQL again in 6 months.

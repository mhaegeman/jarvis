---
name: grill-with-docs
description: Grilling session that challenges your plan against the existing domain model, sharpens terminology, and updates documentation (CONTEXT.md, ADRs) inline as decisions crystallise. Use when user wants to stress-test a plan against their project's language and documented decisions.
---

<what-to-do>

Interview me relentlessly about every aspect of this plan until we reach shared understanding. Walk each branch of design tree, resolving dependencies between decisions one-by-one. For each question, provide recommended answer.

Ask questions one at a time, waiting for feedback on each before continuing.

If a question can be answered by exploring the codebase, explore the codebase instead.

</what-to-do>

<supporting-info>

## Domain awareness

During codebase exploration, also look for existing documentation:

### File structure

Most repos have a single context:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

If `CONTEXT-MAP.md` exists at root → repo has multiple contexts. Map points to each:

```
/
├── CONTEXT-MAP.md
├── docs/
│   └── adr/                          ← system-wide decisions
├── src/
│   ├── ordering/
│   │   ├── CONTEXT.md
│   │   └── docs/adr/                 ← context-specific decisions
│   └── billing/
│       ├── CONTEXT.md
│       └── docs/adr/
```

Create files lazily — only when you have something to write. No `CONTEXT.md` → create when first term resolved. No `docs/adr/` → create when first ADR needed.

## During the session

### Challenge against the glossary

User uses term conflicting w/ existing language in `CONTEXT.md` → call out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

User uses vague/overloaded terms → propose precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

Domain relationships discussed → stress-test w/ specific scenarios. Invent scenarios probing edge cases, forcing precision about boundaries between concepts.

### Cross-reference with code

User states how something works → check whether code agrees. Contradiction → surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Update CONTEXT.md inline

Term resolved → update `CONTEXT.md` right there. Don't batch — capture as they happen. Use format in [CONTEXT-FORMAT.md](./grill-with-docs/CONTEXT-FORMAT.md).

Don't couple `CONTEXT.md` to implementation details. Only terms meaningful to domain experts.

### Offer ADRs sparingly

Offer ADR only when all three true:

1. **Hard to reverse** — cost of changing mind later is meaningful
2. **Surprising without context** — future reader wonders "why this way?"
3. **Result of real trade-off** — genuine alternatives existed, picked one for specific reasons

Any of three missing → skip ADR. Use format in [ADR-FORMAT.md](./grill-with-docs/ADR-FORMAT.md).

</supporting-info>

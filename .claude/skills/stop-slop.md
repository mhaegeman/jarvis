---
name: stop-slop
description: Use when writing, editing, or reviewing prose that may contain AI-generated patterns, filler phrases, passive constructions, or formulaic AI writing tells.
---

# Stop Slop

## Overview

Eliminate predictable AI writing patterns. AI prose has tells — phrases, structures, rhythms marking it as machine-generated. Remove them.

Source: [hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop) (MIT)

## When to Use

- Writing/editing prose for external communication
- Reviewing content before publishing
- Text feels vague, hedged, formulaic
- **Not for:** internal technical docs, code comments, structured data

## Core Rules

1. **Cut filler** — Remove throat-clearing openers ("Certainly!", "It's worth noting that"), emphasis crutches ("absolutely", "truly"), all adverbs.
2. **Break formulaic structures** — Avoid binary contrasts ("Not just X, but Y"), negative listings, dramatic fragmentation, rhetorical setups, false agency.
3. **Active voice** — Every sentence needs human subject doing something. No passive.
4. **Be specific** — Drop vague declaratives, lazy extremes ("every", "always", "never"). Use concrete details.
5. **Reader in the room** — Replace distant abstraction w/ immediacy. Prefer "you".
6. **Vary rhythm** — Mix sentence lengths. Two beats three. End paragraphs differently. No em dashes.
7. **Trust readers** — Present facts plainly. No softening, no hedging.
8. **Cut quotables** — Rewrite anything resembling pull-quote/soundbite.

## Quick Checks

Before finalizing, scan for:

- Adverbs (delete most)
- Passive voice (`was [verb]ed by`)
- Inanimate actors doing human things
- `wh-` starters
- Throat-clearing openers
- False contrasts (`not X, but Y`)
- Uniform sentence length
- Em dashes
- Vague quantifiers (`very`, `many`, `some`)
- Narrator distance
- Meta-commentary about the text

## Scoring

Rate each dimension 1–10. Total <35/50 → revise.

| Dimension   | What to check                        |
|-------------|--------------------------------------|
| Directness  | No hedging, no throat-clearing       |
| Rhythm      | Varied sentence length and structure |
| Trust       | Unfiltered facts, no softening       |
| Authenticity| Human subject, active voice          |
| Density     | No filler, high signal per word      |

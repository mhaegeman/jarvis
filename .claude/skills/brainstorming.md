---
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."
---

# Brainstorming Ideas Into Designs

Turn ideas into designs/specs via collaborative dialogue. Understand project context → ask questions one at a time → present design → get approval.

<HARD-GATE>
Do NOT invoke implementation skill, write code, scaffold, or take implementation action until design presented AND user approved. Applies to EVERY project regardless of perceived simplicity.
</HARD-GATE>

## Anti-Pattern: "Too Simple To Need A Design"

Every project goes through this — todo list, single-fn utility, config change. "Simple" projects = where unexamined assumptions cause most wasted work. Design can be short (few sentences) but MUST be presented and approved.

## Checklist

MUST create task for each, complete in order:

1. **Explore project context** — files, docs, recent commits
2. **Ask clarifying questions** — one at a time; purpose/constraints/success criteria
3. **Propose 2-3 approaches** — w/ trade-offs + recommendation
4. **Present design** — sections scaled to complexity, get approval per section
5. **Write design doc** — `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, commit
6. **Spec self-review** — inline check: placeholders, contradictions, ambiguity, scope
7. **User reviews written spec** — before proceeding
8. **Transition to implementation** — read writing-plans skill

## The Process

**Understanding:**
- Check project state first (files, docs, commits)
- Assess scope before detailed Qs: multiple independent subsystems → flag immediately, decompose first
- Too large for single spec → decompose into sub-projects, each gets own spec→plan→impl cycle
- Ask one question at a time, prefer multiple choice
- Focus: purpose, constraints, success criteria

**Exploring approaches:**
- Propose 2-3 approaches w/ trade-offs
- Lead w/ recommended option + why

**Presenting design:**
- Scale sections to complexity (few sentences → 200-300 words if nuanced)
- Ask after each section if right
- Cover: architecture, components, data flow, error handling, testing

**Design for isolation/clarity:**
- Break into smaller units w/ one purpose, well-defined interfaces, independently testable
- Smaller well-bounded units = easier to reason about

**Existing codebases:**
- Explore structure first, follow existing patterns
- Existing code problems affecting work → include targeted improvements in design
- No unrelated refactoring

## After the Design

**Documentation:**
- Write spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, commit

**Spec Self-Review** (fresh eyes):
1. **Placeholder scan:** "TBD"/"TODO"/incomplete/vague? Fix.
2. **Internal consistency:** Sections contradict?
3. **Scope check:** Focused enough for single plan?
4. **Ambiguity:** Any requirement interpretable 2 ways? Pick one, make explicit.

Fix inline. No re-review.

**User Review Gate:**
After self-review passes, ask user to review spec:

> "Spec written and committed to `<path>`. Please review it and let me know if you want to make any changes before we start writing out the implementation plan."

Wait for response. Proceed only on approval.

**Implementation:**
- Read writing-plans skill (`.claude/skills/writing-plans.md`)

## Key Principles

- **One question at a time**
- **Multiple choice preferred**
- **YAGNI ruthlessly** — remove unnecessary features
- **Explore alternatives** — 2-3 approaches before settling
- **Incremental validation** — approval before moving on

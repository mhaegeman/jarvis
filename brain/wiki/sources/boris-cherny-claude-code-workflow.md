---
title: Boris Cherny — How Claude Code's Creator Starts Every Project
type: source
date_ingested: 2026-04-12
source_file: raw/boris-cherny.md
tags: [
  claude-code, anthropic, ai-tools, llm-workflow, productivity, software-development,
  plan-mode, claude-md, verification-loop, inner-loops, slash-commands, parallel-sessions,
  prompt-engineering, ai-workflow, agentic-coding,
  bitter-lesson, rich-sutton, model-improvement,
  boris-cherny, video-transcript
]
---

## Summary

A YouTube video transcript in which the narrator researches and synthesizes [Boris Cherny](../people/boris-cherny.md)'s publicly shared Claude Code workflow — drawn from interviews, tweets, and public appearances. Boris Cherny is the creator of [Claude Code](../entities/claude-code.md) at Anthropic.

The video distills six actionable principles Boris uses consistently. The through-line is deliberate discipline over reactive speed: plan before building, keep instructions minimal, close verification loops, parallelise with fresh context, systematise repeated tasks as slash commands, and assume models will keep improving so don't over-invest in scaffolding that will be obsolete in six months.

Note: the transcript contains some speech-to-text artifacts ("Clawude", "Churnney", "quadm") that have been cleaned up in this summary.

## Key Points — Boris's Six Principles

### 1. Plan Mode — Move Slow to Move Fast
- ~80% of Boris's sessions start in plan mode (activated with Shift+Tab twice in the terminal).
- Once a good plan is locked in, execution is "almost automatic."
- The risk without planning: AI is optimised to solve problems quickly, not necessarily correctly. It will solve the problem it thinks you want, not always the one you mean.
- **Interview prompt before building:** *"Interview me about this. What is the core problem this solves? Who is this for? What does success look like? And what should this not do? Summarize it back to me before you write any code."*

### 2. Minimal CLAUDE.md — Less Is More
- Boris's own CLAUDE.md is ~couple thousand tokens — deliberately short.
- Pattern: when a mistake happens, update CLAUDE.md so it doesn't recur.
- If the file gets bloated: **delete the whole thing and start fresh.** His rationale: with every model generation, fewer explicit instructions are needed because capabilities are built in. Over-instructing causes Claude to get confused and miss the instructions that actually matter.
- Alternative middle ground (narrator's approach): *"Update my CLAUDE.md to remove anything that's no longer needed, contradictory, duplicate, or unnecessary bloat impacting effectiveness."*
- **Principle**: do the minimal possible thing to get the model on track; add back only when it goes off track.

### 3. Verification — The 2–3x Multiplier
- From a Boris tweet: *"Give Claude a way to verify its work. If Claude has that feedback loop, it will 2 to 3x the quality of the final result."*
- Two steps: (1) give Claude a tool to see the output of its work; (2) tell Claude about that tool. "Claude will figure out the rest."
- Practical applications: browser testing for web projects; brand-guideline review for content; workflow output matching for automations.
- Can add to CLAUDE.md: *"Before you do any work, mention how you could verify that work."* Claude will then state its verification plan upfront.
- Cleanup prompt: *"Please go back and verify all of your work so far. Make sure you use best practices, were efficient, and didn't introduce any issues."*

### 4. Multiply Yourself — Parallel Sessions with Partitioned Tasks
- Boris runs multiple Claude sessions simultaneously, each focused on non-overlapping tasks.
- Key principle: two context windows that don't know about each other tend to get better results than one session that accumulates context.
- Fresh context sees problems without baggage; a second session can spot something obvious the first missed because it was "too deep in the weeds."
- For robust engineering: git worktrees (Boris uses these, not covered in depth here). For individuals: simply open a new Claude Code window and start fresh.

### 5. Inner Loops — Slash Commands and Skills
- Boris uses slash commands for every repeated workflow he does many times a day.
- Quote: *"I use slash commands for every inner loop workflow that I end up doing many times a day. This saves me from repeated prompting."*
- Analogy: a prompt is telling a player to dribble; a Claude skill is the specific play to run (e.g., pick and roll) — AI knows exactly how to execute it every time.
- Starter prompt: *"Based on the project I'm working on, what Claude skills should I create?"*

### 6. Build for the Future — Never Bet Against the Model
- Boris keeps a **framed copy of Rich Sutton's Bitter Lesson on the wall.**
- The Bitter Lesson thesis: the more general model will always beat the more specific model. Applied: every scaffold, micro-tweak, and optimised prompt you create to improve model output will likely be unnecessary in the next 6 months.
- This is not a reason not to build — it's a reason to invest in **"information mode"**: the context, system design, and information structures you feed the model (like this wiki), rather than prompt optimisation.
- Quote: *"AI will never be as bad as it is today."*

## Quotes

> "Probably 80% of my sessions I start in plan mode. And once the plan is good, it just stays on track and it'll just do the thing exactly right almost every time."

> "If you hit this [bloated CLAUDE.md], my recommendation would be delete your CLAUDE.md and just start fresh. Do the minimal possible thing in order to get the model on track."

> "Give Claude a way to verify its work. If Claude has that feedback loop, it will 2 to 3x the quality of the final result."

> "Two context windows that don't know about each other tend to get better results."

> "I use slash commands for every inner loop workflow that I end up doing many times a day."

> "We have a framed copy of the Bitter Lesson on the wall. Never bet against the model."

## Connections

- [Boris Cherny](../people/boris-cherny.md) — creator of Claude Code; the subject of this source
- [Claude Code](../entities/claude-code.md) — the tool his workflow is built around
- [LLM Wiki Pattern](../concepts/llm-wiki-pattern.md) — this wiki is itself an instance of "information mode" thinking; Boris's Principle 6 directly validates the wiki approach over prompt optimisation
- [Persistent Compounding Knowledge](../concepts/persistent-compounding-knowledge.md) — the "information mode" concept maps directly onto persistent compounding knowledge

## Questions Raised

- What does Boris's own CLAUDE.md actually contain? Is it public?
- How does Plan Mode interact with agentic tasks that are inherently exploratory (no known plan upfront)?
- Does Boris use the wiki pattern or anything analogous for knowledge management?
- At what session complexity does parallel partitioning pay off vs. the overhead of managing multiple windows?

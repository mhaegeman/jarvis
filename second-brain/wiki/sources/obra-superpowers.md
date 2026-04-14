---
title: obra/superpowers — Coding Agent Skills Plugin
type: source
date_ingested: 2026-04-14
source_file: raw/obra-superpowers.md
source_url: https://github.com/obra/superpowers
tags: [
  github, open-source, javascript, markdown, shell,
  claude-code, coding-agents, ai-workflows,
  skills-based-agent-extension, subagent-driven-development,
  tdd, brainstorming, plan-driven-development,
  multi-platform, plugin-system, agentskills-io,
  jesse-vincent, prime-radiant,
  workflow-automation, developer-tooling, mit-license
]
---

## Summary

Superpowers is a complete software development workflow plugin for AI coding agents, built as a library of composable **skills** — markdown files with YAML frontmatter that inject structured processes into agent sessions. When installed, the plugin fires a `session-start` hook that bootstraps the agent with a context injection, making it aware of every available skill and obligating it to invoke the relevant one before taking any action.

The core philosophy: agents are undisciplined without guardrails. Left to their own devices, they skip planning, avoid testing, and hallucinate completion. Superpowers forces a disciplined pipeline — brainstorm → spec → plan → subagent-driven implementation → review → finish — where each phase is governed by a rigid skill. Because skills load at session start via hook injection, the agent cannot skip this structure without explicitly rationalizing its way out (which the skills explicitly guard against with "Red Flags" rationalization tables).

The project is built and maintained by Jesse Vincent / [Prime Radiant](../entities/prime-radiant.md). It is zero-dependency, MIT-licensed, and supports six platforms: [Claude Code](../entities/claude-code.md), Cursor, Codex, OpenCode, Gemini CLI, and GitHub Copilot CLI. Current version as of 2026-04-14: **v5.0.7**.

The project has a stated 94% PR rejection rate. Its CLAUDE.md is notably hostile to low-quality agent-submitted PRs, explicitly warning AI agents about the consequences of submitting unvalidated work.

## Tech Stack

- **Skill format:** Markdown files with YAML frontmatter (`name`, `description`) + prose body; Graphviz DOT notation for process flow diagrams inside skills
- **Session start mechanism:** Shell hook (`hooks/session-start`) firing on `startup`, `clear`, `compact` — outputs context injection in platform-specific format (`hookSpecificOutput.additionalContext` for Claude Code, `additional_context` for others)
- **Brainstorm server:** Zero-dependency Node.js server (v5.0.2+) using built-in `http`, `fs`, `crypto`; custom WebSocket (RFC 6455), `fs.watch()` for file watching; serves HTML screens to browser during brainstorming
- **OpenCode plugin:** Node.js/ESM module with custom `use_skill` and `find_skills` tools + `session.started` hook; installed as npm git package
- **Languages:** Shell (hooks), Node.js (server + OpenCode plugin), Markdown (skills)
- **Runtime deps:** None — explicitly zero-dependency by policy
- **Platforms:** Claude Code (official marketplace), Cursor (plugin.json), Codex (symlink + CLI script), OpenCode (npm plugin), Gemini CLI (gemini-extension.json + GEMINI.md @imports), GitHub Copilot CLI (COPILOT_CLI env var detection)
- **Skills standard:** Compliant with [agentskills.io](https://agentskills.io) specification

## Purpose

Superpowers solves the core problem of undisciplined AI coding agents — those that skip planning, hallucinate test results, and declare completion without verification. It imposes a structured, mandatory development lifecycle on any supported coding agent by injecting skill definitions at session start. The primary user action is installing the plugin once; thereafter the agent self-activates the relevant skill for each task type.

## Key Points

- **13 core skills:** `brainstorming`, `using-git-worktrees`, `writing-plans`, `subagent-driven-development`, `executing-plans`, `test-driven-development`, `requesting-code-review`, `receiving-code-review`, `dispatching-parallel-agents`, `systematic-debugging`, `verification-before-completion`, `finishing-a-development-branch`, `writing-skills`, `using-superpowers`
- **Skill invocation rule:** If there is even a 1% chance a skill applies, the agent MUST invoke it — "This is not negotiable. This is not optional."
- **Subagent-Driven Development (SDD):** Fresh subagent per plan task + two-stage review (spec compliance first, then code quality); implementer reports DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT
- **Brainstorming HARD-GATE:** Zero code before an approved spec. Applies to every project regardless of perceived simplicity.
- **Plan format:** Checkbox-syntax steps (2–5 minutes each), exact file paths, complete code, verification steps; saved to `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`
- **Spec format:** Saved to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`; spec self-review checklist before user review gate
- **v5.0.6 key change:** Inline self-review replaces subagent review loops for specs and plans — same quality, 25-minute faster
- **Priority hierarchy:** User CLAUDE.md/AGENTS.md > Superpowers skills > default system prompt
- **`<SUBAGENT-STOP>` block:** Subagents dispatched for specific tasks skip `using-superpowers` entirely to avoid activating full skill workflows recursively
- **Visual brainstorming companion:** Optional Node.js WebSocket server + browser window for mockups and diagrams during brainstorming (opt-in per-question)
- **Zero-dep enforcement:** No third-party npm dependencies — server.js uses only built-in Node.js modules
- **Verification-before-completion:** Explicit "Iron Law" — no completion claims without fresh verification evidence; 24 failure memories documented in the skill

## Quotes

> "It's not uncommon for Claude to be able to work autonomously for a couple hours at a time without deviating from the plan you put together."

> "Skills are not prose — they are code that shapes agent behavior."

> "The agent checks for relevant skills before any task. Mandatory workflows, not suggestions."

> "Write the plan as clear enough for an enthusiastic junior engineer with poor taste, no judgement, no project context, and an aversion to testing to follow."

> "[The] 94% PR rejection rate. Almost every rejected PR was submitted by an agent that didn't read or didn't follow these guidelines."

> "Claiming work is complete without verification is dishonesty, not efficiency."

## Connections

- [Claude Code](../entities/claude-code.md) — primary supported platform; uses official plugin marketplace and Skill tool natively
- [Skills-Based Agent Extension](../concepts/skills-based-agent-extension.md) — the core concept Superpowers implements
- [Subagent-Driven Development](../concepts/subagent-driven-development-concept.md) — the SDD workflow is the key implementation pattern
- [Agentic Workflow Patterns](../concepts/agentic-workflow-patterns.md) — Superpowers documents and enforces many of these patterns
- [Jesse Vincent](../people/jesse-vincent.md) — creator and primary maintainer
- [Prime Radiant](../entities/prime-radiant.md) — company behind Superpowers
- [SPARC Methodology](../concepts/sparc-methodology.md) — similar phase-driven agentic dev philosophy; Superpowers is an independent implementation
- [RuFlo](../entities/ruflo.md) — different approach: emphasizes multi-agent swarms and 100+ agents vs Superpowers' process discipline
- [Jumbo](../entities/jumbo.md) — also targets coding agent context; Jumbo manages context packets, Superpowers manages workflows

## Questions Raised

- How does Superpowers interact with CLAUDE.md files that define their own workflows — does it conflict or compose?
- Is the brainstorm-first hard-gate practical for micro-tasks or bug fixes, or does it need overrides for experienced users?
- What is the `agentskills.io` specification and how does Superpowers' skill format relate to it?
- How does the 94% PR rejection rate compare to other OSS projects — is this reflecting high agent-spam or high standards?
- Will Superpowers be compatible with Claude Code's own skill system (this wiki uses a similar SKILL.md pattern)?

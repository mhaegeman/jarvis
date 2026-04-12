---
title: "EduardPetraeus / Claude Code Quickstart"
type: source
date_ingested: 2026-04-12
source_file: raw/eduardpetraeus-claude-code-quickstart.md
source_url: https://github.com/EduardPetraeus/claude-code-quickstart
tags: [
  github, open-source, claude-code, ai-tooling,
  developer-workflow, project-template, starter-kit,
  agents, rules, hooks, bash, markdown,
  code-review, security, testing, python,
  agentic-engineering, multi-agent, adversarial-review,
  workshop, education
]
---

## Summary

Claude Code Quickstart is an opinionated, battle-tested starter kit for Claude Code that provides everything needed to get productive in 60 seconds. Rather than being a link collection or config dump, it is a progressive learning framework that teaches the patterns that matter — from writing a first CLAUDE.md to automating guardrails and running AI-powered code review.

The core structure layers project configuration: a root CLAUDE.md (always loaded), topic-specific rule files (`.claude/rules/*.md`), bash hooks (`.claude/hooks/*.sh`) that fire on every tool call, and specialist agent definitions (`.claude/agents/*.md`). This separation prevents the main CLAUDE.md from becoming bloated while still allowing deep context injection.

The repo ships with 8 rules (git workflow, code style, session discipline, testing, Python conventions, web safety, session end, security), 10 hooks (auto-lint, branch protection, critical file protection, pre-push review gate, secret scanning, context monitoring, test reminders), 9 agents (code reviewer, security reviewer, explorer, quality gate, unit/integration/data/UAT/regression testers), 2 slash commands (`/handover`, `/reflect`), 8 prompt templates (including 5 divergent-thinking frameworks), and a Gemini-powered external code-review CLI tool.

The repo also powers a 2.5-hour hands-on workshop with timed presenter blocks, demo scripts, and four exercises from beginner to advanced.

## Tech Stack

- **Platform:** Claude Code (CLAUDE.md, .claude/ directory)
- **Format:** Markdown (rules, agents, commands, prompts), Bash (hooks)
- **Language:** Agnostic (examples for Python, TypeScript, non-coders)
- **External tool:** Gemini CLI (for adversarial code review)
- **License:** MIT

## Purpose

Give any developer (or non-coder) a production-ready Claude Code project setup — with enforced guardrails, specialist agents, and reusable prompts — in under 60 seconds, and teach the underlying patterns through structured guides and exercises.

## Key Points

- Four-layer architecture: CLAUDE.md → rules → hooks → agents; each layer adds structure without overloading the core file.
- Hooks enforce guardrails automatically (secret scanning, lint, branch protection) without requiring the user to remember them.
- 9 specialist agents cover the full testing pyramid: unit, integration, data, UAT, regression.
- Adversarial review pattern: uses both Claude and Gemini to independently review code, surfacing disagreements.
- Parallel execution patterns are documented as a guide — running multiple sub-agents concurrently.
- Includes a non-coder CLAUDE.md template (for HR, analysts, writers).
- 5 divergent-thinking prompt frameworks: constraint-kill, cross-pollinate, metaphor-reframe, reverse-think, strategy-diverge.

## Quotes

> "This is not a link collection or a config dump. It's an opinionated, progressive setup that teaches you the patterns that actually matter."

> "CLAUDE.md is the entry point — Claude reads it automatically. Rules add depth without bloating the main file. Hooks enforce guardrails you don't have to think about."

## Connections

- [Claude Code](../entities/claude-code.md) — the platform this starter kit configures.
- [Agentic Workflow Patterns](../concepts/agentic-workflow-patterns.md) — this repo is a reference implementation of multi-agent and hook-based workflow patterns.
- [Owl-Listener / Designer Skills](owl-listener-designer-skills.md) — designer-specific skill library using the same Claude Code skills system.
- [Leavitskiy / Claude Agentic Flow](leavitskiy-claude-agentic-flow.md) — another collection of Claude Code agent prompts.

## Questions Raised

- How do the 10 hooks interact with the agents — do hooks trigger agent sub-processes?
- Is the adversarial Gemini review pattern practical for CI/CD integration?

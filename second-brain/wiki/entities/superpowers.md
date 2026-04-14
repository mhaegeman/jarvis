---
title: Superpowers
type: entity
entity_type: product
tags: [claude-code, coding-agents, skills, open-source, workflow-automation]
---

## Overview

Superpowers (`obra/superpowers`) is an open-source plugin for AI coding agents that imposes a structured, mandatory development workflow via composable **skills**. It is built and maintained by [Jesse Vincent](../people/jesse-vincent.md) at [Prime Radiant](../entities/prime-radiant.md). MIT-licensed. Current version: v5.0.7 (2026-03-31).

The plugin works by injecting skill context at session start. A shell hook fires when the agent starts and loads the `using-superpowers` skill, which obliges the agent to check for and invoke relevant skills before any action. Skills are Markdown files with YAML frontmatter that define rigid or flexible workflows for every phase of software development.

## Key Facts

- **13 core skills** covering the full dev cycle: brainstorming → spec → plan → implementation → review → finish
- **Platforms:** Claude Code (official marketplace), Cursor, Codex, OpenCode, Gemini CLI, GitHub Copilot CLI
- **Install (Claude Code):** `/plugin install superpowers@claude-plugins-official`
- **Zero-dependency** by policy — no npm packages at runtime
- **Skills standard:** [agentskills.io](https://agentskills.io) specification compliant
- **Community:** Discord at discord.gg/35wsABTejz; release notifications at primeradiant.com/superpowers/

## Appearances

- [obra/superpowers source](../sources/obra-superpowers.md) — full ingestion

## Connections

- [Jesse Vincent](../people/jesse-vincent.md) — creator and maintainer
- [Prime Radiant](../entities/prime-radiant.md) — company behind it
- [Claude Code](../entities/claude-code.md) — primary supported platform
- [Skills-Based Agent Extension](../concepts/skills-based-agent-extension.md) — the concept it implements
- [Subagent-Driven Development](../concepts/subagent-driven-development-concept.md) — key workflow pattern

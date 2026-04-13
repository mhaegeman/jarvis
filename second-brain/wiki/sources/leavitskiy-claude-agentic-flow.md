---
title: "Leavitskiy / Claude Agentic Flow"
type: source
date_ingested: 2026-04-12
source_file: raw/leavitskiy-claude-agentic-flow.md
source_url: https://github.com/Leavitskiy/claude-agentic-flow
tags: [
  github, open-source, claude-code, ai-agents,
  agentic-workflow, developer-workflow, python-backend,
  react-native, frontend, fastapi, uv,
  code-review, refactoring, software-architecture,
  prompt-engineering, markdown-prompts
]
---

## Summary

Claude Agentic Flow is a curated collection of Claude Code agent prompt definitions (YAML-frontmatter markdown files) organized into three domains: backend, frontend, and shared. Each file defines a specialist agent persona with instructions for how Claude should behave when performing domain-specific tasks.

The repository includes: **backend-feature-designer** (designs comprehensive backend features with phased implementation plans), **python-backend-engineer** (implements Python backend systems using modern tooling like `uv`, FastAPI, SQLAlchemy, asyncio), **frontend-feature-designer** (designs frontend features with implementation specifications), **react-native-engineer** (builds React Native mobile UIs), **ui-engineer** (creates frontend UIs), **agent-code-reviewer** (reviews PR code for bugs and CLAUDE.md compliance, using a multi-agent approach), and **refactoring-planner** (plans and executes code refactors).

A notable standout is the `claude-code-project-setup.md` file, which provides initial project scaffolding instructions. The code-reviewer agent is particularly well-developed: it uses Haiku for triage, Sonnet for PR summarisation, and parallel Opus agents for bug detection — with a validation step before posting inline GitHub comments, mirroring the pattern in the getnao/nao repo.

## Tech Stack

- **Platform:** Claude Code (agents system)
- **Format:** Markdown with YAML frontmatter (agent spec files)
- **Backend stack referenced:** Python, FastAPI, SQLAlchemy, uv, asyncio, pytest
- **Frontend stack referenced:** React Native, TypeScript
- **Code review integration:** GitHub CLI (`gh`), MCP GitHub inline comments
- **Language:** None (prompt-only)

## Purpose

Provide reusable, domain-specific Claude Code agent definitions for software teams — covering backend architecture, Python implementation, frontend design, mobile development, code review, and refactoring.

## Key Points

- Backend-feature-designer agent outputs a full markdown implementation plan file to `/outputs/implementation_plan_[component].md`.
- Python-backend-engineer agent recommends `uv` for dependency management — signals modern Python tooling preferences.
- Code-reviewer agent pipeline: Haiku triage → Sonnet summarise → parallel Opus bug agents → validation → filtered high-signal GitHub inline comments.
- The design guidelines embedded in the backend-feature-designer emphasise layered architecture: endpoint → service → repository → model.
- Attribution note: python-backend-engineer agent credited to `@hesreallyhim` from `a-list-of-claude-code-agents`.
- The repo demonstrates community-driven accumulation of Claude Code agents — similar to how npm packages accumulate utility functions.

## Quotes

> "CRITICAL: We only want HIGH SIGNAL issues. Flag issues where: the code will fail to compile or parse, the code will definitely produce wrong results, or clear, unambiguous CLAUDE.md violations."

## Connections

- [Claude Code](../entities/claude-code.md) — the platform these agents are built for.
- [Agentic Workflow Patterns](../concepts/agentic-workflow-patterns.md) — the code-reviewer pipeline is a concrete reference for multi-agent validation.
- [EduardPetraeus / Claude Code Quickstart](eduardpetraeus-claude-code-quickstart.md) — complementary repo with similar agent definitions plus rules/hooks.
- [getnao / Nao](getnao-nao.md) — uses nearly identical multi-agent code-review architecture.

## Questions Raised

- Is there a registry or index of community-published Claude Code agent libraries (analogous to npm or PyPI)?
- How do these agent definitions interact with Claude Code's built-in memory and task management?

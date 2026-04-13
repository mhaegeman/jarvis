---
title: Claude Code
type: entity
entity_type: product
tags: [anthropic, ai-tools, agentic-coding, cli, software-development, llm-workflow]
---

## Overview

Claude Code is Anthropic's agentic coding CLI — a terminal-based tool that gives Claude direct access to a codebase (file reads/writes, shell commands, git operations) to complete software engineering tasks autonomously. Created by [Boris Cherny](../people/boris-cherny.md). Activated in a project directory via `claude` in the terminal.

## Key Facts

- **Creator**: [Boris Cherny](../people/boris-cherny.md) at Anthropic
- **Type**: CLI / agentic coding assistant
- **Key feature — Plan Mode**: activated with Shift+Tab twice; Claude plans before executing. Boris starts ~80% of sessions here.
- **Key feature — CLAUDE.md**: a project-level instruction file read at the start of every session; governs how Claude behaves for that project. Boris keeps his at ~couple thousand tokens (deliberately minimal).
- **Slash commands**: user-defined reusable workflows callable directly in the CLI; Boris uses these for every repeated ("inner loop") task
- **Parallel sessions**: multiple Claude Code windows can run simultaneously on partitioned tasks for higher throughput
- **Verification loop**: can be given tools (e.g., browser, test runner) to check its own output; Boris reports this 2–3x's result quality

## Appearances

- [Boris Cherny — How Claude Code's Creator Starts Every Project](../sources/boris-cherny-claude-code-workflow.md) — workflow principles from the creator
- [EduardPetraeus / Claude Code Quickstart](../sources/eduardpetraeus-claude-code-quickstart.md) — battle-tested starter kit with rules, hooks, agents, prompts
- [Leavitskiy / Claude Agentic Flow](../sources/leavitskiy-claude-agentic-flow.md) — library of domain-specific agent prompt definitions
- [Owl-Listener / Designer Skills](../sources/owl-listener-designer-skills.md) — 50+ designer-specific Claude Code skills
- [getnao / Nao](../sources/getnao-nao.md) — ships a multi-agent code-review skill

## Connections

- [Boris Cherny](../people/boris-cherny.md) — creator
- [LLM Wiki Pattern](../concepts/llm-wiki-pattern.md) — this wiki runs inside Claude Code; CLAUDE.md is the schema file governing the wiki agent's behaviour
- [Persistent Compounding Knowledge](../concepts/persistent-compounding-knowledge.md) — the wiki is an instance of "information mode" thinking Boris advocates as the right investment vs. prompt optimisation
- [Agentic Workflow Patterns](../concepts/agentic-workflow-patterns.md) — multiple repos demonstrate advanced Claude Code agent/hook/rule patterns

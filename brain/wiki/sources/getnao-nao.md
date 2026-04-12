---
title: "getnao / Nao"
type: source
date_ingested: 2026-04-12
source_file: raw/getnao-nao.md
source_url: https://github.com/getnao/nao
tags: [
  github, open-source, ai-tooling, data-analysis,
  natural-language-queries, duckdb, sql, text-to-sql,
  full-stack, typescript, python, fastapi,
  react, tanstack, bun, trpc, sqlite,
  claude-code, claude-code-skills
]
---

## Summary

Nao is a full-stack AI-powered data analysis platform that lets users query databases using natural language. It combines a TypeScript backend (Fastify + tRPC + Bun), a React/Vite frontend (TanStack Router & Query, Tailwind CSS), and a Python FastAPI sidecar that handles the actual AI data analysis against a configured project directory.

The architecture is a monorepo with three runnable services: the backend API (port 5005), the frontend UI (port 3000), and the FastAPI Python sidecar (port 8005). The example dataset uses DuckDB with a `jaffle_shop` demo database. SQLite is the default persistence layer for the app itself. Authentication is handled by `better-auth`.

Notably, the repo ships with a Claude Code code-review skill (`.claude/skills/code-review/SKILL.md`), demonstrating how AI-assisted code review can be integrated directly into developer tooling. The skill uses a multi-agent approach: Haiku for triage, Sonnet for summarisation, and Opus for bug detection — with parallel sub-agents and a validation step to filter false positives.

## Tech Stack

- **Backend:** Fastify, tRPC, Bun (TypeScript/Node.js runtime), better-auth
- **Frontend:** React, Vite, TanStack Router, TanStack Query, Tailwind CSS
- **Python sidecar:** FastAPI, Python 3.13
- **Database (app):** SQLite (default), Drizzle ORM
- **Database (data):** DuckDB, with MySQL connector optional
- **Testing:** Vitest (backend + frontend)
- **Linting:** ESLint, Prettier, TypeScript, ruff, ty (Python)
- **Claude Code skill:** multi-agent code review (Haiku + Sonnet + Opus)

## Purpose

Provide a deployable, open-source platform for querying structured data (DuckDB/SQL databases) in natural language — targeted at data teams wanting AI-assisted analytics without leaving their existing data infrastructure.

## Key Points

- Three-service monorepo: Fastify/tRPC backend, Vite/React frontend, FastAPI Python sidecar.
- DuckDB as the primary analytical query engine; SQLite for app persistence.
- The Claude Code skill included is a sophisticated multi-agent code review pipeline: parallelise bug detection, validate findings, filter false positives before posting GitHub comments.
- The code-review skill demonstrates using Haiku/Sonnet/Opus at different quality/cost tiers based on task complexity.
- Example database is the classic `jaffle_shop` dataset (customers, orders, payments).
- Python version pinned at 3.13; Node at v22.14.0.

## Quotes

> "We only want HIGH SIGNAL issues. Flag issues where the code will fail to compile, produce wrong results, or violate CLAUDE.md rules — clearly and unambiguously."

## Connections

- [Claude Code](../entities/claude-code.md) — includes a production-quality Claude Code skill.
- [DuckDB](../entities/duckdb.md) — primary analytical database engine.
- [Agentic Workflow Patterns](../concepts/agentic-workflow-patterns.md) — the multi-agent code-review skill is a concrete reference implementation.

## Questions Raised

- Does Nao expose a natural language → SQL translation layer, or does the FastAPI sidecar call an LLM directly?
- Is the product commercially available or purely open-source?

---
title: qmd
type: entity
entity_type: product
tags: [tooling, search, markdown, llm]
---

## Overview

qmd is a local search engine for markdown files, recommended as an optional upgrade to the index.md navigation approach in the LLM Wiki Pattern when the wiki grows large enough that the index file becomes unwieldy.

## Key Facts

- Hybrid search: combines BM25 (keyword) and vector (semantic) search with LLM re-ranking. All on-device.
- Dual interface: CLI (LLM can shell out to it) and MCP server (LLM can use it as a native tool).
- The idea file suggests it as the natural next tool once index.md outgrows usefulness — estimated at ~100+ sources / hundreds of pages.
- Alternative: build a simpler naive search script with LLM assistance, then upgrade to qmd as needed.

## Appearances

- [LLM Wiki — Idea File](../sources/llm-wiki-idea-file.md) — recommended as optional tooling for larger wikis.

## Connections

- [LLM Wiki Pattern](../concepts/llm-wiki-pattern.md) — optional extension for search at scale
- [RAG vs Wiki Architecture](../concepts/rag-vs-wiki-architecture.md) — qmd adds search capability without full RAG infrastructure
- [Obsidian](obsidian.md) — complementary tool (Obsidian for browsing, qmd for search)

---
title: LLM Wiki — Idea File
type: source
date_ingested: 2026-04-12
source_file: raw/llm-wiki-idea-file.md
tags: [
  knowledge-management, pkm, second-brain, compounding-knowledge, persistent-knowledge,
  llm, ai-tools, claude,
  architecture, pattern, workflow, information-retrieval,
  rag, anti-rag, markdown, indexing, synthesis,
  obsidian, qmd,
  vannevar-bush, memex,
  meta
]
---

## Summary

The LLM Wiki pattern is a method for building a persistent, compounding personal knowledge base using LLMs — distinct from standard RAG. Instead of re-deriving answers from raw documents at query time, the LLM incrementally builds a structured wiki of markdown files that sits between the user and their sources. Each new source is integrated into the existing structure: entity pages updated, concepts cross-referenced, contradictions flagged. The synthesis is done once and kept current, not repeated on every query.

The system has three layers: immutable raw sources, an LLM-owned wiki, and a schema file (CLAUDE.md or AGENTS.md) that governs how the LLM operates. The human curates sources and asks questions; the LLM does all the maintenance — the bookkeeping that causes humans to abandon wikis. The workflow pairs an LLM agent with Obsidian: the LLM edits files, the user browses results in real time.

The idea connects to Vannevar Bush's 1945 Memex concept — a private, curated knowledge store with associative trails — but solves Bush's unsolved problem of who maintains it: the LLM does.

## Key Points

- This is **not RAG**: knowledge is compiled once into the wiki, not re-derived per query. The wiki is a persistent compounding artifact.
- Three layers: **raw sources** (immutable), **wiki** (LLM-owned markdown), **schema** (CLAUDE.md governs behavior).
- Three core operations: **ingest** (read source → update wiki), **query** (search wiki → synthesize answer → optionally file as analysis), **lint** (health-check for contradictions, orphans, gaps).
- Two special files: **index.md** (content catalog, replaces embedding-based search at small scale) and **log.md** (append-only operation history).
- Workflow: LLM agent on one side, Obsidian on the other. "Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."
- Good query answers should be **filed back** into the wiki — explorations compound just like ingested sources.
- Optional tooling: **qmd** for hybrid BM25/vector search when index.md outgrows usefulness. **Obsidian Web Clipper** for capturing web articles. **Marp** for slide decks. **Dataview** for querying frontmatter.

## Quotes

> "The wiki is a persistent, compounding artifact. The cross-references are already there. The contradictions have already been flagged."

> "Humans abandon wikis because the maintenance burden grows faster than the value. LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass."

> "Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."

> "The part [Bush] couldn't solve was who does the maintenance. The LLM handles that."

## Connections

- [LLM Wiki Pattern](../concepts/llm-wiki-pattern.md) — this source is the origin document for the core concept
- [Persistent Compounding Knowledge](../concepts/persistent-compounding-knowledge.md) — the key differentiator from RAG
- [RAG vs Wiki Architecture](../concepts/rag-vs-wiki-architecture.md) — explicit contrast drawn in this source
- [Vannevar Bush / Memex](../entities/vannevar-bush.md) — historical precedent cited
- [Obsidian](../entities/obsidian.md) — recommended UI pairing
- [qmd](../entities/qmd.md) — recommended search tool for larger wikis

## Questions Raised

- At what scale does index.md break down and qmd become necessary?
- How should contradictions between sources be resolved — human decision always, or can the LLM resolve some automatically?
- What does the schema look like for team/business wikis where multiple humans are adding sources?
- How does lint frequency scale with wiki size?

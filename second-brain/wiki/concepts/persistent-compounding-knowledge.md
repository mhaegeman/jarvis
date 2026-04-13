---
title: Persistent Compounding Knowledge
type: concept
tags: [knowledge-management, second-brain, compounding]
---

## Definition

A property of a knowledge base in which each addition enriches all related existing knowledge rather than simply adding an isolated new record. In a compounding knowledge base:
- New sources update existing pages (entities, concepts, summaries).
- Contradictions between old and new information are flagged and resolved.
- Queries add their answers back as new pages, which then benefit future queries.
- Cross-references are built once and reused.

The opposite is a flat accumulation: documents pile up but each query must re-derive connections from scratch.

## Why It Matters

Compounding knowledge is what makes a second brain valuable over time. A RAG system at 100 documents is not meaningfully more capable than at 10 documents — the LLM still re-derives the answer from scratch. A compounding wiki at 100 sources has 100x more connections, syntheses, and cross-references than at 10 sources — each new ingest benefits from and enriches all previous work.

This is why humans abandon flat wikis: the maintenance cost grows faster than the value, until the burden exceeds the benefit. An LLM-maintained wiki inverts this: maintenance cost is near-zero, so the compounding benefit always wins.

## Evidence & Examples

- [LLM Wiki — Idea File](../sources/llm-wiki-idea-file.md): "The wiki keeps getting richer with every source you add and every question you ask."
- Analogous to compound interest: the rate of return increases as the base grows.
- Fan wikis (e.g., Tolkien Gateway) demonstrate what compounding human curation produces at scale — the LLM Wiki Pattern aims to produce the same result with one person and an LLM.

## Tensions & Counterarguments

- Compounding requires discipline: if the LLM writes inaccurate pages early, errors propagate and compound negatively. Quality control in early ingests is important.
- Very different topics in the same wiki may not compound well — the benefit is stronger when sources share entities and concepts.

## Related

- [LLM Wiki Pattern](llm-wiki-pattern.md) — the architecture that enables this property
- [RAG vs Wiki Architecture](rag-vs-wiki-architecture.md) — RAG lacks this property

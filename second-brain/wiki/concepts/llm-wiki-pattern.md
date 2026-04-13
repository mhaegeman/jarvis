---
title: LLM Wiki Pattern
type: concept
tags: [knowledge-management, architecture, llm, second-brain]
---

## Definition

A method for building a personal knowledge base in which an LLM incrementally builds and maintains a structured wiki of markdown files from curated source documents. The LLM owns the wiki layer entirely — creating pages, updating them as new sources arrive, maintaining cross-references, and resolving contradictions. The human curates sources and directs analysis; the LLM does all maintenance.

## Why It Matters

Most LLM-document workflows are RAG: retrieve-then-generate at query time, with no accumulation. The LLM Wiki Pattern is structurally different: knowledge is compiled once and kept current. The result is a compounding artifact — each ingest enriches every related page, and each query can add its answer back into the knowledge base. The synthesis deepens over time rather than being reconstructed from scratch each session.

## Evidence & Examples

- [LLM Wiki — Idea File](../sources/llm-wiki-idea-file.md) — origin document defining the pattern
- Use cases: personal self-improvement tracking, research deep-dives, book companion wikis, business internal knowledge bases, competitive analysis, trip planning.

## Tensions & Counterarguments

- Requires a capable LLM that can reliably write structured markdown, maintain cross-references, and not hallucinate. Weaker models may degrade wiki quality over time.
- The schema (CLAUDE.md) must be maintained and evolved — it's a configuration artifact that itself requires upkeep.
- For very large wikis (hundreds of sources), index.md as the navigation mechanism may become unwieldy — may need to add tooling like [qmd](../entities/qmd.md).
- Human supervision during ingest is recommended (at least for early sessions) to catch errors before they propagate across many pages.

## Related

- [RAG vs Wiki Architecture](rag-vs-wiki-architecture.md) — the key structural contrast
- [Agent Context Orchestration](agent-context-orchestration.md) — complementary approach: wiki compiles prose for synthesis, context orchestration assembles entity graphs for task execution
- [Jumbo](../entities/jumbo.md) — entity-graph persistence as an alternative/complement to wiki compilation
- [Persistent Compounding Knowledge](persistent-compounding-knowledge.md) — the property that makes this valuable
- [Vannevar Bush / Memex](../entities/vannevar-bush.md) — 1945 historical precedent
- [Obsidian](../entities/obsidian.md) — recommended UI pairing for browsing the wiki

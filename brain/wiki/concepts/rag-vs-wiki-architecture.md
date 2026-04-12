---
title: RAG vs Wiki Architecture
type: concept
tags: [knowledge-management, rag, architecture, llm]
---

## Definition

Two distinct architectures for LLM-powered document knowledge bases:

**RAG (Retrieval-Augmented Generation):** Source documents are chunked and embedded into a vector store. At query time, relevant chunks are retrieved and passed to the LLM to generate an answer. Knowledge is never accumulated — the LLM re-derives answers from raw sources every time.

**Wiki Architecture (LLM Wiki Pattern):** An LLM reads source documents and compiles their knowledge into a persistent structured wiki. At query time, the LLM reads wiki pages (not raw chunks) and synthesizes answers. Knowledge accumulates: each ingest updates existing pages, adds cross-references, and flags contradictions.

## Why It Matters

The choice between these architectures determines whether a knowledge base compounds over time or stays static. RAG systems (NotebookLM, ChatGPT file uploads) are easier to set up but provide no accumulation. The wiki architecture requires upfront schema design and LLM maintenance work, but produces a knowledge base that grows richer with every source added and every question asked.

## Evidence & Examples

- [LLM Wiki — Idea File](../sources/llm-wiki-idea-file.md) draws this contrast explicitly: "the LLM is rediscovering knowledge from scratch on every question. There's no accumulation."
- RAG examples: NotebookLM, ChatGPT file uploads, most enterprise document Q&A tools.
- **Advanced RAG example**: [RAG-Anything](../entities/rag-anything.md) ([source](../sources/hkuds-rag-anything.md)) represents the most capable end of the RAG design space: a multimodal knowledge graph that fuses vector search with graph traversal. It handles images, tables, and equations — capabilities the wiki pattern currently lacks. But it still re-derives answers at query time from indexed content rather than compiled synthesis.
- Wiki architecture: this wiki itself.

## Tensions & Counterarguments

- RAG scales to very large document collections without a growing maintenance burden. Wiki architecture becomes harder to maintain at very large scale.
- RAG preserves the raw source verbatim; wiki architecture involves LLM interpretation which may introduce errors or bias.
- Advanced RAG systems like [RAG-Anything](../entities/rag-anything.md) narrow the gap significantly by building knowledge graphs and cross-modal indexes at ingest time — blurring the line between "compile once" and "retrieve per query."
- Hybrid approaches are possible: use RAG for retrieval within the wiki (e.g., [qmd](../entities/qmd.md)) while keeping the compiled wiki as the primary knowledge layer.

## Related

- [LLM Wiki Pattern](llm-wiki-pattern.md) — the alternative being advocated
- [Persistent Compounding Knowledge](persistent-compounding-knowledge.md) — the property RAG lacks
- [Multimodal RAG](multimodal-rag.md) — the most capable subtype of RAG; narrows the gap with wiki architecture for non-text content
- [RAG-Anything](../entities/rag-anything.md) — leading open-source multimodal RAG implementation
- [qmd](../entities/qmd.md) — a tool that can add search capability to the wiki without full RAG infrastructure

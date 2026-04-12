---
title: RAG-Anything (HKUDS)
type: source
date_ingested: 2026-04-12
source_file: raw/hkuds-rag-anything.md
source_url: https://github.com/HKUDS/RAG-Anything
tags: [
  rag, multimodal-rag, knowledge-graph, graph-rag, hybrid-retrieval, information-retrieval,
  llm, ai-tools, document-processing, pdf-parsing, ocr, vlm,
  python, open-source, github, technical-reference, documentation,
  lightrag, rag-anything, hkuds, mineru, vllm,
  vector-search, embeddings, knowledge-management,
  production-deployment, self-hosted
]
---

## Summary

RAG-Anything is an all-in-one multimodal RAG framework from HKUDS (Hong Kong University of Science and Technology research group), built on top of [LightRAG](../entities/lightrag.md). It extends standard text RAG to handle diverse content types — PDFs, Office documents, images, tables, mathematical equations, and charts — through a unified pipeline. The core architectural differentiator over basic RAG is its **knowledge graph index**: rather than pure vector similarity search, RAG-Anything extracts entities and cross-modal relationships from documents and stores them in a graph, enabling structural reasoning alongside semantic retrieval.

The system is backed by arXiv paper 2510.12323 and has surpassed 1,000 GitHub stars. It is designed for researchers and engineers who need to query heterogeneous document collections without building separate specialized tools for each content modality.

This source is directly relevant to this wiki's own architecture: RAG-Anything represents the most capable public implementation of the [RAG pattern](../concepts/rag-vs-wiki-architecture.md) this wiki deliberately avoids — making it a useful benchmark for understanding what that choice costs and what it gains.

## Key Points

- **Five-stage pipeline**: Document Parsing → Multimodal Content Understanding → Multimodal Analysis Engine → Knowledge Graph Index → Modality-Aware Retrieval.
- **Knowledge graph over pure vectors**: Entities and relationships are extracted across modalities; retrieval fuses vector similarity with graph traversal. This is the key differentiator from standard RAG.
- **Three parser options**: MinerU (primary — PDF, image, Office, OCR), Docling (Office-optimized), PaddleOCR (OCR-focused).
- **Three query modes**: pure text, VLM-enhanced (auto-analyzes images in context), multimodal (explicit equation/table/image queries).
- **Context-aware multimodal processing**: When analyzing an image or table, the system automatically provides the LLM with surrounding text context (configurable window of pages or chunks). This substantially improves description accuracy.
- **Direct content insertion**: Pre-parsed content lists (text + images + tables + equations) can be inserted directly, bypassing the document parser entirely.
- **Production-grade LLM backends**: Supports OpenAI, Ollama, Azure, vLLM. vLLM integration is first-class — dedicated doc covers PagedAttention, tensor parallelism, speculative decoding, multi-GPU setup.
- **Flexible storage**: PostgreSQL, Neo4j (graph), MongoDB, Milvus/Qdrant (vectors), Redis (cache). Configurable via env vars.
- **Batch processing**: Concurrent document processing with configurable workers (2–8 depending on file size), async support, `BatchProcessingResult` for error tracking.
- **Offline operation**: Requires a pre-cached tiktoken directory (`tiktoken_cache/`) since LightRAG's dependency on tiktoken makes a network call at init time.
- **PDF generation from markdown**: Built-in enhanced markdown→PDF via WeasyPrint or Pandoc.

## Quotes

> "Rather than requiring separate specialized tools, it provides seamless processing and querying across all content modalities within one integrated framework."

> "Modality-Aware Retrieval — Vector-graph fusion combining semantic embeddings with structural relationships."

> "Context helps AI understand the purpose and meaning of multimodal content." (on context-aware processing)

## Connections

- [RAG-Anything](../entities/rag-anything.md) — the product entity page
- [LightRAG](../entities/lightrag.md) — the underlying graph-based RAG framework RAG-Anything is built on
- [Multimodal RAG](../concepts/multimodal-rag.md) — the core concept this repo instantiates
- [RAG vs Wiki Architecture](../concepts/rag-vs-wiki-architecture.md) — RAG-Anything is a concrete example of the most capable end of the RAG design space

## Questions Raised

- How does knowledge graph construction quality degrade for heavily visual or equation-dense documents?
- At what document collection scale does the graph become a bottleneck vs. a benefit?
- Is LightRAG's graph approach (vs. simple vector RAG) worth the added infrastructure complexity for typical use cases?
- How does context-aware multimodal processing compare to dedicated multimodal models that jointly encode text and image?
- The offline tiktoken issue suggests LightRAG wasn't designed for air-gapped environments — what other hidden network dependencies exist?

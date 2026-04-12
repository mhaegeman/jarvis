---
title: RAG-Anything
type: entity
entity_type: product
tags: [rag, multimodal-rag, python, open-source, document-processing, knowledge-graph]
---

## Overview

RAG-Anything is an open-source multimodal RAG framework from [HKUDS](https://github.com/HKUDS) (Hong Kong University of Science and Technology research group), built on top of [LightRAG](lightrag.md). It handles text, images, tables, equations, and charts through a single unified pipeline backed by a multimodal knowledge graph. The project has 1,000+ GitHub stars and an arXiv technical report (2510.12323).

## Key Facts

- **Repo**: https://github.com/HKUDS/RAG-Anything
- **Install**: `pip install raganything` or `pip install 'raganything[all]'`
- **Built on**: [LightRAG](lightrag.md)
- **Parsers**: MinerU (primary), Docling (Office), PaddleOCR (OCR)
- **Query modes**: pure text, VLM-enhanced, multimodal (table/equation/image)
- **Knowledge graph storage**: Neo4j supported; entities and cross-modal relationships extracted automatically
- **Vector storage**: Milvus or Qdrant
- **LLM backends**: OpenAI, Ollama, Azure, vLLM (all via OpenAI-compatible API)
- **Embedding default**: `bge-m3:latest` via Ollama, 1024-dim
- **Context-aware processing**: provides surrounding document text to LLM when analyzing multimodal content
- **Batch processing**: async-capable, 2–8 configurable workers
- **Offline mode**: requires pre-cached tiktoken directory (see `scripts/create_tiktoken_cache.py`)
- **Paper**: arXiv 2510.12323

## Appearances

- [RAG-Anything (HKUDS)](../sources/hkuds-rag-anything.md) — primary source page; full pipeline and configuration details

## Connections

- [LightRAG](lightrag.md) — parent framework; provides graph-based RAG core
- [Multimodal RAG](../concepts/multimodal-rag.md) — the concept this product instantiates
- [RAG vs Wiki Architecture](../concepts/rag-vs-wiki-architecture.md) — RAG-Anything is the most capable end of the RAG design space; useful for understanding the tradeoffs this wiki's architecture makes

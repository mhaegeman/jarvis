---
title: LightRAG
type: entity
entity_type: product
tags: [rag, knowledge-graph, graph-rag, python, open-source, information-retrieval]
---

## Overview

LightRAG is an open-source graph-based RAG framework, also from HKUDS, that serves as the foundation for [RAG-Anything](rag-anything.md). Its core architectural choice is building a **knowledge graph** from ingested documents and fusing graph traversal with vector similarity at retrieval time — rather than pure vector search as in standard RAG. [RAG-Anything](rag-anything.md) extends LightRAG specifically to handle multimodal content.

## Key Facts

- **From**: HKUDS (Hong Kong University of Science and Technology research group)
- **Role in RAG-Anything**: provides the graph index, vector storage abstraction, retrieval engine, and the tiktoken-dependent tokenizer
- **Retrieval approach**: hybrid vector + graph traversal (vs. pure vector search in standard RAG)
- **Hidden dependency**: uses OpenAI's tiktoken at initialization, requiring a network call or pre-cached tokenizer files for offline deployments
- **Storage abstractions**: supports Neo4j, PostgreSQL, MongoDB, Milvus/Qdrant, Redis

## Appearances

- [RAG-Anything (HKUDS)](../sources/hkuds-rag-anything.md) — described as the underlying framework; tiktoken offline issue documented

## Connections

- [RAG-Anything](rag-anything.md) — the multimodal extension built on LightRAG
- [Multimodal RAG](../concepts/multimodal-rag.md) — the broader concept LightRAG's graph approach enables
- [RAG vs Wiki Architecture](../concepts/rag-vs-wiki-architecture.md) — LightRAG is a concrete implementation of graph-augmented RAG

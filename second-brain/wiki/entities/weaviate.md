---
title: Weaviate
type: entity
entity_type: product
tags: [vector-database, rag, embeddings, open-source, ai-infrastructure]
---

## Overview

Weaviate is an open-source vector database designed for storing and retrieving embeddings at scale. It supports hybrid search (vector + keyword), multi-modal data types, and integrates natively with popular embedding models and LLM frameworks (LangChain, LlamaIndex). Commonly used as the retrieval layer in RAG architectures.

## Key Facts

- Used by Ask Astro as the vector database for storing Airflow/Astronomer documentation embeddings.
- Apache Airflow provider available: `apache-airflow-providers-weaviate==1.3.0`.
- Supports hybrid search: dense vector similarity + BM25 keyword fallback.

## Appearances

- [Ask Astro source page](../sources/astronomer-ask-astro.md) — primary vector store for the RAG pipeline.

## Connections

- [Astronomer](../entities/astronomer.md) — built Ask Astro using Weaviate.
- [Apache Airflow](../entities/apache-airflow.md) — Airflow DAGs ingest data into Weaviate.
- [RAG-Anything](../entities/rag-anything.md) — alternative multimodal RAG system; uses different vector storage.

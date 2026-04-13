---
title: "Astronomer / Ask Astro"
type: source
date_ingested: 2026-04-12
source_file: raw/astronomer-ask-astro.md
source_url: https://github.com/astronomer/ask-astro
tags: [
  github, open-source, rag, llm-application,
  apache-airflow, astronomer, weaviate, vector-db,
  langchain, openai, google-firestore, slack-bot,
  streamlit, python, airflow-dags,
  a16z-architecture, reference-implementation,
  document-ingestion, qa-bot
]
---

## Summary

Ask Astro is Astronomer's open-source reference implementation of the a16z LLM Application Architecture — an end-to-end RAG-based Q&A system specifically designed to answer questions about Apache Airflow and the Astro platform. It demonstrates how to build a production-quality LLM application from ingestion to user-facing interfaces.

The ingestion layer uses Apache Airflow DAGs to scrape and process documentation from multiple sources (GitHub repos, Slack, Stack Overflow, web pages), chunk the text, generate embeddings with OpenAI, and store them in Weaviate (vector database). The API layer exposes a FastAPI service deployed on Google Cloud Run, backed by Google Firestore for feedback and conversation storage. The frontend supports both a Slack bot and a Streamlit web app.

The system prompt instructs Ask Astro to stay strictly on-topic (Airflow/Astronomer only), use context documents as the primary source, and acknowledge uncertainty when context is insufficient — a strong example of grounded RAG prompting. LangChain is used for retrieval orchestration.

## Tech Stack

- **Ingestion:** Apache Airflow DAGs, Python
- **Vector DB:** Weaviate (apache-airflow-providers-weaviate)
- **Embeddings:** OpenAI
- **Retrieval / orchestration:** LangChain
- **API:** FastAPI (Python), deployed on Google Cloud Run
- **Storage:** Google Firestore, Snowflake (optional)
- **Frontend 1:** Streamlit
- **Frontend 2:** Slack bot (apache-airflow-providers-slack)
- **Monitoring:** LangSmith, custom latency dashboards
- **Other:** html2text, pypandoc, markdownify, tiktoken, firebase-admin

## Purpose

Provide a fully open, production-grade reference implementation of a domain-specific RAG Q&A bot — demonstrating every layer of the LLM application stack from data ingestion to multi-channel user interfaces.

## Key Points

- Follows the [Andreessen Horowitz LLM Application Architecture](https://a16z.com/emerging-architectures-for-llm-applications/) — a recognised reference design for LLM apps.
- Data ingestion is driven entirely by Airflow DAGs, making the pipeline schedulable, observable, and reproducible.
- Two user-facing interfaces: a Slack bot (primary) and a Streamlit web UI.
- System prompt design is strict: bot refuses to answer off-topic questions and explicitly references source documents.
- Monitoring uses LangSmith for LLM traces and custom dashboards for latency/feedback loops.
- Feedback loop is built in: Firestore stores user thumbs-up/down ratings per answer.

## Quotes

> "Ask Astro is an open-source reference implementation of Andreessen Horowitz's LLM Application Architecture built by Astronomer."

> "Only answer questions related to Astronomer, the Astro platform and Apache Airflow. If you don't know the answer, just say that you don't know."

## Connections

- [Astronomer](../entities/astronomer.md) — the company that built and maintains Ask Astro.
- [Apache Airflow](../entities/apache-airflow.md) — the orchestration platform Ask Astro is built on and answers questions about.
- [Weaviate](../entities/weaviate.md) — vector database for storing embeddings.
- [RAG vs Wiki Architecture](../concepts/rag-vs-wiki-architecture.md) — Ask Astro is a canonical RAG implementation for comparison.
- [RAG-Anything](../entities/rag-anything.md) — alternative multi-modal RAG approach.
- [Multimodal RAG](../concepts/multimodal-rag.md) — Ask Astro is text-only RAG; contrast with multimodal.

## Questions Raised

- What is the ingestion frequency — how often do the Airflow DAGs re-embed updated documentation?
- Is Ask Astro still actively maintained, or primarily archived as a reference?

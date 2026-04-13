---
title: "IAmTomShaw / Document Chatbot Offline"
type: source
date_ingested: 2026-04-12
source_file: raw/iamtomshaw-document-chatbot-offline.md
source_url: https://github.com/IAmTomShaw/document-chatbot-offline
tags: [
  github, open-source, offline-llm, local-ai,
  pdf-chatbot, rag, streamlit, python,
  windows-ai-foundry, phi-3, edge-ai,
  document-qa, no-cloud, privacy-first
]
---

## Summary

Document Chatbot Offline is a minimal Streamlit application that lets users upload a PDF and chat with its contents using a locally hosted LLM — without any cloud dependency. The entire pipeline runs on the user's machine: PDF text extraction via PyPDF2, session-managed conversation history via Streamlit, and LLM inference via Windows AI Foundry Local (an on-device model server from Microsoft).

The key technical integration is `FoundryLocalManager`, which the app uses to retrieve the local model's endpoint URL and API key, then communicates with it through an OpenAI-compatible client. The suggested model is `phi-3.5-mini`, deployed locally by Foundry Local. The app maintains a simple full-document-in-context RAG approach: the entire PDF text is passed in the system prompt alongside the user's question, rather than using chunked vector retrieval.

This repo is notable as a practical, working example of on-device LLM inference for document Q&A on Windows — using Microsoft's AI Foundry stack. It is intentionally minimal and educational.

## Tech Stack

- **UI:** Streamlit
- **PDF extraction:** PyPDF2
- **LLM runtime:** Windows AI Foundry Local (Microsoft)
- **Model:** phi-3.5-mini (on-device)
- **LLM client:** OpenAI-compatible SDK (foundry-local-sdk)
- **Language:** Python 3.8+
- **Platform:** Windows (primary target)

## Purpose

Demonstrate a fully offline, privacy-preserving document Q&A chatbot on Windows using Microsoft's Foundry Local as the on-device LLM server — no API keys, no cloud calls.

## Key Points

- Zero cloud dependency: all inference is local via Windows AI Foundry Local.
- Uses a full-document-in-context approach (entire PDF in prompt) rather than chunked vector search.
- OpenAI-compatible API client makes the app easily portable to other local servers (Ollama, LM Studio, etc.).
- Conversation history is managed client-side in Streamlit session state.
- Created by Tom Shaw (tomshaw.dev) — educational/demo project.

## Connections

- [Offline LLM Inference](../concepts/offline-llm-inference.md) — demonstrates the offline-first document Q&A pattern.
- [Windows AI Foundry](../entities/windows-ai-foundry.md) — the on-device model server this app depends on.

## Questions Raised

- How does the full-document approach compare to chunked RAG for longer PDFs — at what page count does phi-3.5-mini context window become a bottleneck?
- Could this be adapted for Ollama or llama.cpp as the backend instead of Foundry Local?

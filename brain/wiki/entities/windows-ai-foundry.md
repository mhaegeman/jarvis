---
title: Windows AI Foundry Local
type: entity
entity_type: product
tags: [microsoft, on-device-ai, local-llm, edge-inference, windows, phi-3]
---

## Overview

Windows AI Foundry Local is Microsoft's on-device LLM runtime for Windows. It provides an OpenAI-compatible API endpoint running entirely on the local machine, enabling privacy-preserving LLM inference without cloud connectivity. It ships with models like phi-3.5-mini and is managed through `FoundryLocalManager`.

## Key Facts

- Exposes an OpenAI-compatible REST API, making existing OpenAI SDK code portable.
- `FoundryLocalManager` provides the local endpoint URL and API key programmatically.
- Default model: phi-3.5-mini (small, efficient on-device model).
- Python SDK: `foundry-local-sdk`.
- Used by the document-chatbot-offline project for fully offline PDF Q&A.

## Appearances

- [IAmTomShaw / Document Chatbot Offline](../sources/iamtomshaw-document-chatbot-offline.md) — core dependency for on-device LLM inference.

## Connections

- [Offline LLM Inference](../concepts/offline-llm-inference.md) — the concept this product enables.

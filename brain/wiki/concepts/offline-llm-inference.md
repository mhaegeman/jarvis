---
title: Offline LLM Inference
type: concept
tags: [local-ai, edge-ai, privacy, on-device-llm, llama-cpp, ollama, foundry-local, quantization]
---

## Definition

Offline LLM inference is the practice of running language model inference entirely on local hardware — no internet connection, no cloud API call, no data leaving the machine. The model weights are stored locally; the runtime executes inference on CPU, consumer GPU, or Apple Silicon.

Key enabling technologies:

- **llama.cpp:** C++ runtime for GGUF-quantised models; runs on any CPU.
- **Ollama:** User-friendly wrapper around llama.cpp with a REST API.
- **Windows AI Foundry Local:** Microsoft's on-device LLM server for Windows, OpenAI API-compatible.
- **LM Studio:** GUI for running local models on Mac/Windows.
- **Quantisation:** Makes large models fit in consumer hardware memory.

## Why It Matters

Offline inference provides: (1) privacy — sensitive documents never leave the device; (2) cost — no per-token API fees; (3) latency — no network round-trip; (4) availability — works without internet. Relevant for enterprise data compliance, personal productivity, and edge deployment.

## Evidence & Examples

- [IAmTomShaw / Document Chatbot Offline](../sources/iamtomshaw-document-chatbot-offline.md) — concrete implementation using Windows AI Foundry Local + phi-3.5-mini for fully offline PDF Q&A.
- [mlabonne / LLM Course](../sources/mlabonne-llm-course.md) — covers GGUF/llama.cpp quantisation and AutoQuant tools for producing local-inference-ready model files.
- [LLM Quantization](../concepts/llm-quantization.md) — the technique that makes offline inference tractable for large models.

## Tensions & Counterarguments

- Local models lag behind frontier API models in quality — phi-3.5-mini vs. GPT-4 is not a fair comparison for complex tasks.
- Hardware requirements: running Llama-70B locally still needs 32–64 GB RAM even with 4-bit quantisation.
- Offline models require manual updates; cloud APIs auto-update.

## Related

- [LLM Quantization](../concepts/llm-quantization.md)
- [Windows AI Foundry](../entities/windows-ai-foundry.md)
- [LLM Fine-Tuning](../concepts/llm-fine-tuning.md) — fine-tuned models can be quantised for local deployment.

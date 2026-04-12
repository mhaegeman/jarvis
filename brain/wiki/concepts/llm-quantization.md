---
title: LLM Quantization
type: concept
tags: [llm, quantization, gptq, gguf, exl2, awq, hqq, qlora, inference, edge-ai, mlabonne]
---

## Definition

LLM quantization reduces model weight precision from 32-bit/16-bit floats to lower bit-widths (8-bit, 4-bit, or fewer), dramatically shrinking model size and inference memory requirements with acceptable quality loss. The dominant formats are:

- **GGUF (llama.cpp):** CPU-optimised; runs on any machine; supports Q2 through Q8 quantisation levels.
- **GPTQ:** GPU-optimised 4-bit quantisation using approximate second-order weight correction.
- **EXL2 (ExLlamaV2):** Fast GPU inference with mixed-precision per-layer quantisation.
- **AWQ:** Activation-Aware Weight Quantisation — preserves important weight channels.
- **HQQ:** Optimised for speed of quantisation (not inference speed).
- **QLoRA:** LoRA adapters on top of a quantised (4-bit NF4) base model for fine-tuning.

## Why It Matters

Full-precision Llama-70B requires ~140 GB of GPU VRAM. 4-bit GGUF reduces this to ~35 GB, making it runnable on a single high-end consumer GPU. Quantisation is the key enabler for running large models locally (on-device) without cloud infrastructure.

## Evidence & Examples

- [mlabonne / LLM Course](../sources/mlabonne-llm-course.md) — dedicated quantisation section with notebooks for GPTQ, GGUF, EXL2 (all runnable on Colab).
- [IAmTomShaw / Document Chatbot Offline](../sources/iamtomshaw-document-chatbot-offline.md) — uses phi-3.5-mini (a small, quantisation-friendly model) for fully offline inference via Windows AI Foundry.
- Rule of thumb: GGUF for CPU/local, GPTQ/EXL2 for GPU inference, QLoRA for fine-tuning.

## Tensions & Counterarguments

- Quantisation introduces quality degradation — lower bit-widths lose nuance, especially on complex reasoning.
- GGUF and GPTQ are not interchangeable: GGUF is CPU-first, GPTQ is GPU-first.
- Quantisation research is evolving rapidly — formats from 2023 may be superseded.

## Related

- [LLM Fine-Tuning](../concepts/llm-fine-tuning.md) — QLoRA combines quantisation with fine-tuning.
- [Offline LLM Inference](../concepts/offline-llm-inference.md) — quantisation is what makes offline inference feasible.
- [Maxime Labonne](../people/maxime-labonne.md) — primary source author covering all major quantisation formats.

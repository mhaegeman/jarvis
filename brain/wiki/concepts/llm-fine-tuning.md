---
title: LLM Fine-Tuning
type: concept
tags: [llm, fine-tuning, sft, qlora, dpo, orpo, unsloth, axolotl, hugging-face, mlabonne]
---

## Definition

LLM fine-tuning is the process of adapting a pre-trained large language model to a specific task or domain by continuing training on a curated dataset. Methods range from full fine-tuning (all weights updated) to parameter-efficient techniques (PEFT) that train only a small fraction of parameters, enabling fine-tuning on consumer hardware.

Key techniques in the current (2024–2026) landscape:

- **SFT (Supervised Fine-Tuning):** Train on (instruction, response) pairs to teach a desired behaviour.
- **QLoRA:** LoRA adapters applied to a quantised base model — enables fine-tuning on a single consumer GPU (16–24 GB VRAM).
- **DPO (Direct Preference Optimisation):** Align model with human preferences without a reward model; more stable than RLHF.
- **ORPO (Odds Ratio Preference Optimisation):** Single-stage SFT + preference alignment; cheaper than DPO (no reference model needed).

## Why It Matters

Pre-trained models (Llama, Mistral) are general-purpose. Fine-tuning adapts them to a specific persona, domain vocabulary, output format, or safety policy without the cost of training from scratch.

## Evidence & Examples

- [mlabonne / LLM Course](../sources/mlabonne-llm-course.md) — comprehensive curriculum covering SFT, QLoRA, DPO, ORPO with runnable notebooks for Llama 2/3, Mistral-7b.
- Preferred tools: Unsloth (efficient SFT in Colab), Axolotl (advanced pipeline), TRL (Hugging Face).
- DPO/ORPO are displacing RLHF for alignment due to simpler training dynamics.

## Tensions & Counterarguments

- Fine-tuned models can lose general capability ("catastrophic forgetting") if the fine-tuning dataset is narrow.
- QLoRA reduces VRAM requirements but takes longer to train than full fine-tuning on large-memory systems.
- DPO/ORPO quality depends heavily on the preference dataset — garbage in, garbage out.

## Related

- [LLM Quantization](../concepts/llm-quantization.md) — quantisation enables fine-tuning larger models on limited hardware.
- [Maxime Labonne](../people/maxime-labonne.md) — author of the primary source on this topic.

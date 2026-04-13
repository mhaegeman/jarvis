---
title: "mlabonne / LLM Course"
type: source
date_ingested: 2026-04-12
source_file: raw/mlabonne-llm-course.md
source_url: https://github.com/mlabonne/llm-course
tags: [
  github, open-source, llm, education, course,
  fine-tuning, quantization, rag, llm-engineering,
  llm-scientist, hugging-face, google-colab,
  python, pytorch, transformers,
  unsloth, axolotl, mergekit, gptq, gguf, qlora, dpo, orpo,
  model-merging, moe, abliteration, knowledge-graph,
  beam-search, neural-networks
]
---

## Summary

The LLM Course by Maxime Labonne is a free, comprehensive curriculum for learning how to build and deploy large language models. It is organised into three tracks: **LLM Fundamentals** (optional prerequisites — maths, Python, neural networks), **The LLM Scientist** (training and fine-tuning LLMs with the latest techniques), and **The LLM Engineer** (building and deploying LLM-based applications). The course is supplemented by Labonne's co-authored book "LLM Engineer's Handbook" (Packt, 2024).

Content is delivered primarily as Jupyter notebooks runnable on Google Colab. Topics span the full ML/LLM stack: supervised fine-tuning (SFT), direct preference optimisation (DPO/ORPO), quantisation (GPTQ, GGUF, EXL2, AWQ, HQQ), model merging with MergeKit, mixture-of-experts (MoE) creation, abliteration (removing refusal behaviour), knowledge-graph augmentation, RAG, and evaluation frameworks.

The course is heavily practical: each topic comes with a runnable notebook, an article link, and a tooling recommendation (e.g., Unsloth for efficient fine-tuning, Axolotl for advanced fine-tuning pipelines, llama.cpp for GGUF quantisation, ExLlamaV2 for fast inference). As of 2026 it is one of the most widely referenced free LLM engineering curricula.

## Tech Stack

- **Language:** Python
- **Frameworks:** PyTorch, Hugging Face Transformers, TRL (fine-tuning)
- **Fine-tuning tools:** Unsloth, Axolotl, PEFT (QLoRA)
- **Quantisation:** GPTQ, GGUF/llama.cpp, EXL2/ExLlamaV2, AWQ, HQQ
- **Model merging:** MergeKit
- **Evaluation:** LLM AutoEval (RunPod)
- **Serving:** Gradio, ZeroGPU
- **Notebooks:** Google Colab
- **Models covered:** Llama 2/3/3.1, Mistral-7b, CodeLlama

## Purpose

Provide a free, end-to-end curriculum teaching the skills required to become an LLM engineer — from mathematical foundations through to fine-tuning, quantisation, RAG, and deployment.

## Key Points

- Three-track structure: Fundamentals → Scientist (build/train LLMs) → Engineer (deploy/productionise).
- Covers DPO and ORPO as preference-optimisation alternatives to RLHF.
- Quantisation section covers GPTQ (4-bit), GGUF (llama.cpp), EXL2, AWQ, HQQ — matching hardware from consumer GPU to CPU.
- Model merging via MergeKit enables creating custom models without any GPU training.
- Abliteration technique lets you fine-tune out refusal behaviour using weight direction removal.
- Knowledge graph augmentation of ChatGPT is covered as a practical RAG extension.

## Quotes

> "The LLM course is divided into three parts: LLM Fundamentals (optional), The LLM Scientist, and The LLM Engineer."

## Connections

- [Maxime Labonne](../people/maxime-labonne.md) — author and creator of the course.
- [LLM Fine-Tuning](../concepts/llm-fine-tuning.md) — core concept extensively covered in this course.
- [LLM Quantization](../concepts/llm-quantization.md) — key technique for deploying LLMs on consumer hardware.
- [RAG-Anything](../entities/rag-anything.md) — RAG is covered in the Engineer track; RAG-Anything is a related project.

## Questions Raised

- Which sections of this course are most relevant for Maxime Haegeman's data/ML engineering background?
- Is the Scientist track (fine-tuning) or Engineer track (deployment, RAG) more applicable to practical use cases?

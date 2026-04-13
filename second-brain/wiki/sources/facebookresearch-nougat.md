---
title: "facebookresearch / Nougat"
type: source
date_ingested: 2026-04-12
source_file: raw/facebookresearch-nougat.md
source_url: https://github.com/facebookresearch/nougat
tags: [
  github, open-source, neural-ocr, pdf-parsing,
  academic-documents, latex, math-ocr,
  vision-transformer, pytorch, hugging-face,
  document-ai, scientific-papers, markdown-output,
  meta-ai, facebook-research, python,
  onnx, docker, api, arxiv
]
---

## Summary

Nougat (Neural Optical Understanding for Academic Documents) is Meta AI Research's open-source model for parsing academic PDF documents into structured Markdown, with accurate handling of LaTeX mathematical equations and tables — areas where standard OCR and PDF parsers fail badly.

The model is based on a Vision Transformer (ViT) encoder/Donut decoder architecture. It converts PDF pages to images, processes them visually (no text extraction layer), and outputs Mathpix-compatible `.mmd` (Mathpix Markdown) format. Two checkpoint sizes are available: `0.1.0-small` and `0.1.0-base`. The model is available on PyPI as `nougat-ocr` and on Hugging Face.

Usage is via a CLI (`nougat path/to/file.pdf -o output_dir`), a Python API, or a FastAPI REST server. Docker support is provided for GPU deployments. The repo also includes tooling to generate the training dataset from paired PDF/HTML (LaTeXML) sources.

Limitations: works best on English scientific papers (arXiv/PMC-style); other languages and non-scientific documents produce poor results.

## Tech Stack

- **Model architecture:** Vision Transformer (ViT encoder) + Donut decoder
- **Framework:** PyTorch (Python 3.9+)
- **Model distribution:** Hugging Face, GitHub Releases, PyPI (`nougat-ocr`)
- **API:** FastAPI (optional, via `nougat-ocr[api]`)
- **Inference:** CPU and GPU (CUDA); bfloat16 by default
- **Export:** ONNX (for cross-platform inference)
- **Deployment:** Docker (NVIDIA CUDA/CuDNN required for GPU)
- **Output format:** Mathpix Markdown (.mmd), compatible with LaTeX tables
- **License:** Code MIT; model weights CC-BY-NC

## Purpose

Convert academic PDF documents (particularly scientific papers) into machine-readable Markdown with correctly typeset mathematical formulas and tables — enabling downstream LLM ingestion, search, and analysis of scientific literature.

## Key Points

- Purely visual model: reads page images directly, no underlying PDF text layer needed.
- Handles LaTeX math and complex tables accurately — major gap in conventional PDF parsers.
- Output format is `.mmd` (Mathpix Markdown), compatible with Mathpix Markdown renderer.
- Known issue: failure detection heuristic can produce `[MISSING_PAGE]` on CPU/older GPUs — use `--no-skipping` flag as workaround.
- Built on top of the [Donut](https://github.com/clovaai/donut/) repository architecture.
- Model weights are CC-BY-NC (non-commercial only), codebase is MIT.
- ArXiv paper: 2308.13418 — "Nougat: Neural Optical Understanding for Academic Documents" (Blecher et al., 2023).

## Quotes

> "This is the official repository for Nougat, the academic document PDF parser that understands LaTeX math and tables."

## Connections

- [Meta AI Research](../entities/meta-ai-research.md) — the lab that created Nougat.
- [Neural Document OCR](../concepts/neural-document-ocr.md) — the core capability Nougat exemplifies.
- [Segment Anything](facebookresearch-segment-anything.md) — another Meta AI Research foundational model; different domain (vision segmentation).
- [RAG-Anything](../entities/rag-anything.md) — Nougat output (.mmd) could feed into multimodal RAG pipelines.

## Questions Raised

- Does Nougat's output quality degrade for non-English papers or handwritten equations?
- How does it compare to more recent document-parsing models (GPT-4V, Gemini Vision, Mathpix API)?

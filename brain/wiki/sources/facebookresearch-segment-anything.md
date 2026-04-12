---
title: "facebookresearch / Segment Anything (SAM)"
type: source
date_ingested: 2026-04-12
source_file: raw/facebookresearch-segment-anything.md
source_url: https://github.com/facebookresearch/segment-anything
tags: [
  github, open-source, computer-vision, segmentation,
  foundation-model, zero-shot, promptable-segmentation,
  vision-transformer, pytorch, onnx, react, wasm,
  meta-ai, facebook-research, python,
  sa-1b-dataset, coco-format, image-segmentation,
  sam2, video-segmentation
]
---

## Summary

Segment Anything Model (SAM) is Meta AI Research (FAIR)'s foundational model for zero-shot image segmentation. Given any input prompt — a point, a bounding box, or free-form text — SAM produces high-quality object masks for the target in an image. It can also run automatically to generate masks for all objects in an image without any prompt.

SAM was trained on the SA-1B dataset: 11 million images with 1.1 billion manually annotated masks — the largest segmentation dataset ever collected at time of release. Three model variants are available by backbone size: ViT-H (default), ViT-L, and ViT-B. The model architecture uses a Vision Transformer encoder with a lightweight mask decoder.

The repo provides Python API, CLI, ONNX export for cross-platform inference, and a React + WebAssembly demo for in-browser mask prediction using ONNX Runtime Web with multi-threading via SharedArrayBuffer. A SAM 2 successor extends the model to video segmentation.

## Tech Stack

- **Model architecture:** Vision Transformer (ViT-H/L/B encoder) + mask decoder
- **Framework:** PyTorch (Python 3.8+, pytorch≥1.7)
- **Export:** ONNX (quantized QUInt8 for browser inference)
- **Browser demo:** React, TypeScript, Webpack, ONNX Runtime Web, WebAssembly (WASM), SharedArrayBuffer
- **Optional deps:** opencv-python, pycocotools, matplotlib, onnxruntime, onnx
- **Dataset format:** COCO RLE (mask format), JSON
- **License:** Apache 2.0

## Purpose

Provide a universal, promptable image segmentation model — a "foundation model for segmentation" — enabling zero-shot mask generation for any object in any image, without task-specific fine-tuning.

## Key Points

- Zero-shot: SAM generalises to unseen objects and domains without fine-tuning.
- Three prompt modalities: points (click), bounding boxes, and automatic (no prompt).
- SA-1B dataset: 11M images, 1.1B masks — released alongside the model.
- Lightweight ONNX-exported mask decoder runs in the browser via WASM + SharedArrayBuffer multithreading.
- SAM 2 (separate repo: facebookresearch/segment-anything-2) extends to video with streaming memory for real-time processing.
- Authors include Alexander Kirillov, Nikhila Ravi, Ross Girshick, Piotr Dollár (all from Meta AI / FAIR).

## Quotes

> "The Segment Anything Model (SAM) produces high quality object masks from input prompts such as points or boxes, and it can be used to generate masks for all objects in an image."

> "It has been trained on a dataset of 11 million images and 1.1 billion masks, and has strong zero-shot performance on a variety of segmentation tasks."

## Connections

- [Meta AI Research](../entities/meta-ai-research.md) — FAIR lab created SAM.
- [Promptable Visual Segmentation](../concepts/promptable-visual-segmentation.md) — the core concept SAM introduces.
- [Nougat](facebookresearch-nougat.md) — another Meta AI Research model; document domain vs. image segmentation.

## Questions Raised

- How is SAM used in practice for data pipelines — e.g., automated image annotation or segmentation-based filtering?
- What are SAM 2's performance characteristics on video compared to frame-by-frame SAM 1?

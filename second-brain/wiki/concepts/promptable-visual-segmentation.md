---
title: Promptable Visual Segmentation
type: concept
tags: [computer-vision, segmentation, foundation-model, zero-shot, sam, meta-ai]
---

## Definition

Promptable visual segmentation is the ability to segment (isolate) any object in an image by specifying it through a prompt — a point click, a bounding box, or free-form description — without task-specific training. The model generalises from its training distribution to any object in any domain at inference time.

SAM (Segment Anything Model) by Meta AI Research is the defining implementation. Given a user-provided spatial hint (point or box), SAM's lightweight mask decoder generates a precise binary mask for the indicated object in milliseconds. In automatic mode, SAM generates masks for all objects in an image without any prompt.

## Why It Matters

Traditional segmentation models required separate fine-tuning for each object category (people, cars, trees, etc.). Promptable segmentation enables a single model to serve any segmentation task — from medical imaging to satellite imagery — making it a true "foundation model for vision" analogous to GPT being a foundation model for text.

## Evidence & Examples

- [Segment Anything (SAM)](../sources/facebookresearch-segment-anything.md) — trained on 11M images / 1.1B masks (SA-1B dataset); ViT-H/L/B backbone sizes.
- SAM 2 extends prompting to video frames, maintaining object identity across time.
- The ONNX-exported SAM mask decoder runs in-browser via WebAssembly, enabling real-time interactive segmentation.

## Tensions & Counterarguments

- SAM segments but does not classify — it produces masks without semantic labels.
- Performance degrades on microscopy, satellite, and non-photographic images not well-represented in SA-1B.
- SAM 2 has superseded SAM 1 for most use cases; SAM 1 is effectively legacy.

## Related

- [Meta AI Research](../entities/meta-ai-research.md)
- [Neural Document OCR](../concepts/neural-document-ocr.md) — different visual AI task (document understanding vs. segmentation).

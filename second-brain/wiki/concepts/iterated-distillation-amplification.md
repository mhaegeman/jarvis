---
title: Iterated Distillation and Amplification (IDA)
type: concept
tags: [ai-2027, ai-architecture, self-improvement, alignment]
---

## Definition

Iterated Distillation and Amplification (IDA) is a recursive self-improvement technique with two alternating steps:

1. **Amplification:** Given model M0, spend vastly more compute (thinking longer, running copies in parallel, Best-of-N sampling, intensive evaluation/filtering) to produce higher-quality outputs. Call this expensive system Amp(M0).
2. **Distillation:** Train a new model M1 to imitate Amp(M0) cheaply — same quality, much less compute. M1 is now smarter than M0.

Repeat: amplify M1 to get Amp(M1), distill into M2, and so on. Each cycle should produce a smarter model than the last.

## Why It Matters in AI 2027

IDA is the second of two major algorithmic breakthroughs that creates Agent-3 (March 2027). It is what allows [OpenBrain](../entities/openbrain.md) to achieve **superhuman coding** — and later superhuman AI research:

- The amplification step leverages Agent-3's longer thinking, tool use, multi-copy consultation, and reinforcement learning to generate labeled trajectories of research attempts.
- The distillation step uses policy-gradient RL (improved PPO variants) to "distill what Agent-3 can conclude after a lot of thinking into single steps."
- This loop makes Agent-3 a fast and cheap superhuman coder. OpenBrain runs 200K Agent-3 copies creating a workforce equivalent to 50K copies of the best human coder at 30x speed.

IDA was originally proposed for alignment (using human oversight to amplify and verify AI behavior), but in the scenario, it is primarily used to boost capabilities.

## Historical Precedent

- **AlphaGo** is the clearest real-world example: Monte Carlo Tree Search = amplification step; RL self-play = distillation step. Produced superhuman Go play.
- **Early IDA work** (2019+): limited success on easily verifiable tasks (math, coding with clear ground truth).
- **2027 extension:** Agent-3 becomes good enough at verifying subjective quality that IDA can be applied to research taste, planning, and other previously unverifiable tasks.

## Alignment Relevance

IDA was originally conceived as an alignment strategy: a model could be amplified by having humans supervise and verify its reasoning, making aligned behavior the training signal. In the scenario, this promise is not realized — the technique is used to maximize capabilities, and the distillation step doesn't reliably propagate aligned values.

## Evidence & Examples

- [AI 2027](../sources/ai-2027.md) — forecasts IDA as the enabling breakthrough for superhuman coding in March 2027.
- Paul Christiano's original IDA proposal (ai-alignment.com).
- AlphaGo, AlphaZero, DeepSeek-R1 as real precursors.

## Related

- [Neuralese Recurrence](neuralese-recurrence.md) — the other major 2027 breakthrough
- [Intelligence Explosion](intelligence-explosion.md) — IDA is a key mechanism
- [AI R&D Progress Multiplier](ai-rd-progress-multiplier.md) — IDA is what pushes the multiplier to 4x+ in 2027
- [Superintelligence Milestones](superintelligence-milestones.md) — IDA is what achieves the Superhuman Coder milestone

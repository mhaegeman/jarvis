# Hot Topics
_Short-term memory primer. Keywords only. ≤500 words. Updated: 2026-04-14._

---

## 2026-04-14

**airbnb/chronon** — open-source **Feature Platform** for ML. Airbnb + Stripe co-maintained. Apache 2.0. Powers all major ML at Airbnb, major use cases at Stripe. Python API (`GroupBy` / `Join` / `StagingQuery`) → Thrift → Spark (batch) + Flink (streaming) + online `Fetcher` (Scala/Java) + Vert.x REST service. KV store pluggable (MongoDB in quickstart). Airflow control plane, one DAG per team per Join.

Core guarantees:
- **Point-in-Time Correctness** — Sawtooth Windows algorithm (sliding head + hopping tail), naive JOIN is quadratic
- **Online/Offline Consistency** — measurement framework: log fetches → re-backfill → compare via equality/numeric (SMAPE)/sequence (Levenshtein)/map. ReqSketch >2× faster than t-digest
- **Accuracy modes**: SNAPSHOT (midnight) vs TEMPORAL (realtime)
- **Sources**: EventSource (log+Kafka) vs EntitySource (snapshots+mutations CDC)

Architecture shifts:
- **Tiled Architecture** (Stripe-contributed, PRs #523/#531) — Flink stateful window op writes pre-aggregated IRs as tiles to KV store. O(tiles) reads vs O(events). 33% latency cut. Opt-in `enable_tiling=true`
- **CHIP-1** — Caffeine IR + GetRequest caching. 22–35% batch latency cut. `isComplete` tiles cacheable, monoid-aware merge
- **CHIP-2** — Bazel migration (hermetic, Scala 2.12/2.13 matrix), replace SBT, monorepo reorg
- **Old name**: Zipline. Metrics still `ai.zipline.*`

Hot-path Scala rules: no `for`/`foreach`/ranges/`Option`/`Tuple`/immutable collections; naked Arrays; branches in control path.

Governance: 13-seat PMC (8 Airbnb + 5 Stripe), CHIP process, Apache-style lazy consensus. dev@chronon.ai.

**Ships `.claude/`** — CLAUDE.md + 10 slash commands (4 user: groupby/join/staging-query/debug; 6 dev: architecture/integrate + 4 specialists aggregator/join-backfill/feature-serving/streaming). Major OSS treating Claude Code as first-class.

New concepts: feature-platform, point-in-time-correctness, online-offline-consistency, tiled-feature-aggregation.

## 2026-04-13

**Jumbo** — memory + context orchestration CLI for coding agents. Event-sourced entity graph (.jumbo/). 5-phase lifecycle: define→refine→implement→review→codify. **Context packet** assembly. Agent-agnostic (Claude Code, Copilot, Gemini, Cursor, Codex, Vibe). 12 Claude Code skills. Concept: **Agent Context Orchestration** vs static CLAUDE.md.

**nexos.ai competitor intel** — NOT compliance competitor. "Guardrails" = PII filtering. "Governance" = token spend. $350M, NordVPN founders.

**RuFlo** — multi-agent orchestration for Claude Code. 100+ agents, 137 skills, 313 MCP tools. Topologies hierarchical/mesh/ring/star. Consensus Raft/BFT/Gossip/CRDT/Quorum. SONA/EWC++/ReasoningBank self-learning. WASM→Haiku→Opus routing, 75% cost cut. SPARC. Claims auth 7 types / 4 levels.

**GuardRail team** — Maxime (ML), Harsh (UX), Karoline (legal/EU AI Act), Fabio (AI agents)

## Wiki state
80 pages | 21 sources | 8 people | 20 entities | 28 concepts | 0 analyses

---
_Deep dive: [overview](overview.md) | Full catalog: [index](index.md) | History: [log](log.md)_

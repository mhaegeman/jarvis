---
title: Tiled Feature Aggregation
type: concept
tags: [ml-infra, feature-serving, streaming, flink, kv-store, latency-optimization]
---

## Definition

**Tiled feature aggregation** is an online-serving architecture in which a streaming job pre-aggregates events into fixed-size time-bucket **tiles** (Intermediate Representations, or IRs) and writes these tiles — rather than raw events — to the KV store. At fetch time, the serving layer retrieves `O(tiles)` tiles within the window, merges their IRs, and returns the final feature value. This trades a stateful streaming write path for dramatically cheaper reads.

## Why It Matters

The traditional (untiled) architecture stores individual events and aggregates on read. For a 12-hour window on a stream producing 10 events/sec/key, serving one fetch means iterating over **432,000 events**. With 1-hour tiles, the same fetch merges **12–13 pre-aggregated tiles** instead. This collapses the common case for hot keys from a scan into a constant-factor merge.

Stripe reported a **33% reduction in serving latency** after their initial tiled implementation. The pattern is especially important for orgs with (a) hot-key traffic distributions, (b) KV stores without range-query support (e.g. Cassandra), or (c) tight p99 latency SLOs.

## Evidence & Examples

- [Chronon](../entities/chronon.md)'s Tiled Architecture (`docs/source/Tiled_Architecture.md`) — Flink-only; opt-in via `enable_tiling=true` in a GroupBy's `customJson`. Open-sourced by [Stripe](../entities/stripe.md) via PRs #523/#531.
- **Flink tile operators** (5-stage pipeline):
  1. **Source** — read events from Kafka/etc. (Proto/Thrift/Avro-typed).
  2. **Spark expression evaluation** — project/filter using `CatalystUtil` inside Flink.
  3. **Window operator** (stateful) — accumulate IRs per key per tile bucket; emit on every event for freshness.
  4. **Avro conversion** — encode IR bytes into a `PutRequest`.
  5. **KV store sink** — async write via `AsyncDataStream`.
- **`isComplete` flag**: each tile carries a completeness marker; Flink sets it when the tile bucket is finalized. This is critical for CHIP-1's streaming-IR cache — only `isComplete` tiles are safely cacheable, so consecutive completed tiles can be merged into a single cached entry.
- **Monoid-aware caching (CHIP-1)**: completed consecutive tiles are combined in-memory before caching, so the cache stores one merged IR per contiguous complete range instead of N small tiles. GetRequest bounds are rewritten on cache hits to fetch only the uncached tail: "if it's 17:00 UTC and your cache contains [0:00, 13:00), we modify the `GetRequest` to fetch only [13:00, …)".
- Chronon's Sawtooth Windows algorithm is the **offline analog** — a hopping tail of pre-aggregated buckets + a sliding head. Tiles are Sawtooth's write-side cousin, materialized in the KV store for online serving.

## Tensions & Counterarguments

- **Flink dependency**: tiled architecture requires Flink for the stateful window operator. Orgs without Flink cannot adopt it without also building Flink infrastructure — a significant commitment.
- **Write amplification**: tiles are emitted on every event (for freshness), so the KV-store write rate doesn't drop. The win is on reads.
- **Windowless aggregations and very cold keys**: if your hottest keys see <~1,000 events/day, the untiled approach is already cheap enough and tiling adds operational complexity for no gain.
- **Tile size tradeoff**: smaller tiles = fresher reads but more tiles per fetch; larger tiles = fewer fetches but staler initial values. Chronon's quickstart uses 1-hour tiles; this is a deployment-specific knob.

## Related

- [Chronon](../entities/chronon.md) — the canonical tiled feature-serving implementation.
- [Stripe](../entities/stripe.md) — open-sourced the tiled architecture to Chronon.
- [Feature Platform](feature-platform.md) — tiling is a scaling solution for feature-platform serving layers.
- [Point-in-Time Correctness](point-in-time-correctness.md) — the offline Sawtooth algorithm is the PITC analog of tiling on the online side.
- [Online/Offline Consistency](online-offline-consistency.md) — tile completeness interacts with consistency: incomplete tiles cache differently and affect what "consistent" means during the current tile bucket.

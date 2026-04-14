---
title: Online/Offline Consistency
type: concept
tags: [ml-infra, feature-engineering, data-quality, training-serving-skew, observability]
---

## Definition

**Online/offline consistency** is the property that a feature value computed offline (in a training pipeline from warehouse data) equals the value served online (from a KV store at inference time) for the same `(keys, timestamp)`. When violated, it produces **training-serving skew** — the model sees different inputs at train-time vs serve-time, silently degrading production performance.

A system is said to have **measured** online/offline consistency when it automatically logs fetch requests, re-runs the offline computation against those same `(keys, ts)`, and reports quantified discrepancies per feature.

## Why It Matters

Training-serving skew is one of the hardest ML bugs to diagnose because offline metrics look fine and production metrics drift slowly. Measuring consistency converts a silent failure mode into an observable one.

## Evidence & Examples

- [Chronon](../entities/chronon.md) treats online/offline consistency as a core, named guarantee — not a nice-to-have. Every `Join` can set `check_consistency=True` and `sample_percent=X` to enable a DAG (`online_offline_comparison_<team>_<join>`) that runs the measurement pipeline.
- **Causes of inconsistency identified by Chronon's docs**: (1) realtime features have inherent stream latency — Kafka at-least-once writes + KV-store put latency adds ms-to-seconds; (2) batch features have a midnight refresh window — minutes-to-hours of drift after upstream data lands; 100% consistency is acknowledged as infeasible. The framework measures, it doesn't eliminate.
- **Measurement pipeline**:
  1. Sample fetches are logged with `key_bytes`, `value_bytes`, `ts_millis`, partitioned by `ds` and `join_name`. Sampling is key-hash-based (not random) so bloom filters on the backfill stay small.
  2. Keys and timestamps are fed back as the `left` side of a Join backfill.
  3. Logged values are compared to backfilled values per feature and per type.
- **Metric types**:
  - **Equality** (all types): mismatch rate, missing rate, extra rate.
  - **Numeric**: SMAPE, delta distribution, logged and backfilled distributions.
  - **Sequence**: length distributions, Levenshtein edit distance (inserts/deletes counted separately; no replacements).
  - **Map**: missing/extra/mismatched keys, plus nested value comparison. (TODO in Chronon.)
- **Quantile sketch choice**: Chronon uses **ReqSketch** over t-digest for aggregating feature distributions — ReqSketch has proven error bounds at all ranges and is >2× faster to update, serialize, deserialize; the 0.1 KB space penalty doesn't matter at one sketch per feature per executor.

## Tensions & Counterarguments

- **You can't backfill out of inconsistency for realtime features**: stream latency is physical. The best you can do is quantify it and decide if it's tolerable for a given model.
- **Sampling bias**: logging 10% of requests may miss rare keys that matter most. Chronon's hash-based sampling captures all instances of a sampled-key subset, trading breadth for depth.
- **Log-table lifecycle**: Chronon's log-flattener "closes" a partition when it runs; if you re-fetch on the same day and re-flatten, earlier fetches are overwritten unless you drop and reload.

## Related

- [Chronon](../entities/chronon.md) — the canonical implementation.
- [Point-in-Time Correctness](point-in-time-correctness.md) — the offline-side prerequisite; without PITC, consistency measurements are meaningless.
- [Feature Platform](feature-platform.md) — consistency guarantees are what distinguishes a real feature platform from a pair of pipelines.
- [Tiled Feature Aggregation](tiled-feature-aggregation.md) — tiling changes the shape of possible inconsistencies (completed vs in-progress tiles) and affects caching strategies.

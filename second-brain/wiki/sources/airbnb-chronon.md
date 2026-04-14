---
title: airbnb / Chronon
type: source
date_ingested: 2026-04-14
source_file: raw/airbnb-chronon.md
source_url: https://github.com/airbnb/chronon
tags: [
  feature-platform, feature-store, ml-infra, data-engineering,
  point-in-time-correctness, online-offline-consistency,
  windowed-aggregations, tiling, sawtooth-windows,
  apache-spark, apache-flink, kafka, avro, thrift, scala, python,
  bazel, sbt, airflow-orchestration,
  github, open-source, airbnb, stripe, apache-2-0
]
---

## Summary

Chronon is an open-source end-to-end feature platform for ML, jointly maintained by Airbnb and Stripe. It is the production feature-engineering substrate behind all major ML applications at Airbnb and major use cases at Stripe. A single Python definition (`GroupBy` / `Join` / `StagingQuery`) drives four outputs: scalable historical backfills for training, real-time streaming updates, low-latency online serving, and automated online/offline consistency metrics. The central guarantee is that the feature value a model sees at inference time is identical — temporally and semantically — to the value used during training, eliminating training-serving skew.

The engine is a layered JVM stack: a Python API compiles Thrift configs that are executed by a Spark driver for batch/backfill work, a Flink job for streaming, and an online Fetcher (Scala/Java, plus an optional Vert.x REST service) that reads from a pluggable KV store. An aggregator module shared across all three engines implements the Sawtooth Windows algorithm, reversible and non-reversible aggregations, and sketch-based distinct-count/quantile approximations (HyperLogLog, KLL, t-digest, ReqSketch). Airflow DAGs orchestrate the control plane — one DAG per team for batch uploads and one per Join for consistency checks.

Two major architectural initiatives are in flight: (1) **Tiled Architecture** — pre-aggregated "tiles" (Intermediate Representations) stored in the KV store instead of raw events, reducing fetch work from O(events) to O(tiles) and cutting serving latency ~33% at Stripe; requires Flink. (2) **Bazel migration** (CHIP-2) — moving from SBT to hermetic Bazel builds for reproducibility, parallel caching, and multi-Scala/Spark matrix builds. CHIP-1 adds Caffeine-based IR + GetRequest caching in the Fetcher for additional latency cuts on hot keys. Governance is formalized: a 13-seat PMC (8 Airbnb, 5 Stripe), CHIP process modeled on Kafka/Flink improvement proposals, and Apache 2.0 licensing.

The repo also ships a full Claude Code integration layer (`.claude/CLAUDE.md` plus user and dev specialist slash commands) — evidence that the project treats LLM-assisted development as first-class rather than an afterthought.

## Tech Stack

- **Languages**: Scala 2.12, Java, Python 3.10+
- **Compute engines**: Apache Spark (batch backfills, uploads), Apache Flink (streaming, tiled write path), Spark Streaming (legacy streaming path)
- **Serialization & IDL**: Apache Thrift (config IDL, generated to Python/Scala/Java), Apache Avro (KV store wire format)
- **Orchestration**: Apache Airflow (control plane — one DAG per team/Join, triggers: upstream-data-landing, continuous, daily)
- **Online serving**: Scala `Fetcher` / Java `JavaFetcher` libraries; Vert.x feature service (`service/`) — HTTP + gRPC; StatsD/Micrometer metrics; Caffeine (proposed in CHIP-1) for batch/tile IR caching
- **KV store**: Pluggable via `Api.KVStore` trait; MongoDB used in the Docker quickstart; docs reference Cassandra-style stores and tile-friendly backends
- **Streaming**: Kafka (sources); Flink stateful window operator (tiled); Spark expression evaluation inside Flink via `CatalystUtil`
- **Aggregation primitives**: Sawtooth Windows (sliding head + hopping tail), reversible aggregations (sum/count/avg/histogram), sketches (HyperLogLog for distinct count, KLL/ReqSketch/t-digest for quantiles)
- **Build systems**: SBT (current primary), Bazel (CHIP-2 migration target — hermetic, language-agnostic)
- **Packaging**: Maven Central (Scala/Java artifacts), PyPI as `chronon-ai` (Python API)
- **Docs**: Sphinx site at chronon.ai
- **Tooling**: `.claude/CLAUDE.md` + 4 user commands (`groupby`, `join`, `staging-query`, `debug`) + 6 dev commands (`architecture`, `integrate`, 4 specialists: `aggregator`, `feature-serving`, `join-backfill`, `streaming`)

## Purpose

Chronon solves training-serving skew for ML feature engineering by making a single feature definition authoritative across batch training, real-time streaming, online serving, and consistency monitoring. The target user is a Data Scientist or ML engineer at a company large enough that "log features in production and wait for enough data" is too slow and "rebuild online features in a second codebase" is too error-prone. The primary user action is: author a `GroupBy` or `Join` in Python, run `compile.py` then `run.py --mode backfill/upload/fetch`, and let Airflow keep feature values up-to-date in the KV store and training tables in Hive thereafter. Point-in-time-correct backfills — guaranteed by the Sawtooth algorithm and the `left`-side timestamp contract of Join — are what make this consistency tractable.

## Key Points

- **Two core API objects**: `GroupBy` = aggregations over a Source keyed by one or more entities (SUM/COUNT/AVG/LAST_K/APPROX_UNIQUE over configurable Windows); `Join` = combine N GroupBys on a `left` source defining the (keys, timestamp) timeline for point-in-time backfills.
- **Source types**: `EventSource` (log table ± Kafka topic, has timestamps) vs `EntitySource` (daily snapshot table + optional mutations stream for CDC).
- **Accuracy modes**: `SNAPSHOT` (midnight-accurate, batch-refreshed) vs `TEMPORAL` (real-time, streaming-updated).
- **Control plane**: Airflow DAGs per team (`chronon_group_by_batch_{team}`, `chronon_group_by_streaming_{team}`, `chronon_staging_query_batch_{team}`) and per Join (`chronon_join_{team}__{join_id}`, `chronon_online_offline_comparison_{join_id}`) plus a daily `chronon_metadata_upload`.
- **run.py modes**: `backfill`, `upload`, `streaming`, `metadata-upload`, `fetch`, `analyze`, `consistency-metrics-compute`, `log-flattener`, `local-streaming`.
- **Sawtooth Windows algorithm**: combines a sliding head (full-precision recent events) with a hopping tail (pre-aggregated hops) — this is what enables efficient O(tiles) online aggregation while preserving backfill accuracy.
- **Reversible vs non-reversible aggregations**: Sum/Count/Average/Histogram are reversible (delete = subtract/decrement), enabling mutations processing; Min/Max/Variance/ApproxDistinctCount/First/Last are non-reversible.
- **Online/offline consistency measurement**: fetch requests are logged, then the same (keys, ts) is fed back into a Join backfill; the system computes equality, numeric (SMAPE, delta), sequence (Levenshtein), and map-level comparisons. Quantile sketch: ReqSketch chosen over t-digest for >2× faster update at equal space.
- **Tiled Architecture**: pre-aggregated IRs written to KV store as tiles by a stateful Flink operator; O(tiles) reads instead of O(events); 33% latency reduction at Stripe; opt-in via `enable_tiling=true` in GroupBy `customJson`; requires Flink.
- **CHIP-1 (IR + GetRequest caching)**: Caffeine caches on batch IRs and tile IRs keyed by (dataset, keyBytes, batchEndTs, batchDataLandingTime); observed 22–35% batch-side latency reduction at Stripe.
- **CHIP-2 (Bazel migration)**: 3-phase plan — add Bazel alongside SBT, switch CI to Bazel and drop SBT, then reorganize repo into colocated `ai/chronon/{api,aggregator,service,online,flink,spark,airflow}/` monorepo structure.
- **Governance**: PMC with 13 allocated seats (8 Airbnb + 5 Stripe), CHIP process required before major changes, Apache 2.0 license, dev@chronon.ai mailing list, `+1` GitHub approval counts as binding committer vote.
- **Scala hot-path rules** (`Code_Guidelines.md`): no `for`, no ranges (`foreach`/`until`/`to`), no `Option`/`Tuple`, no immutable collections, preallocate naked Arrays, push branches out of the inner loop via schema-driven dispatch.
- **Python package is `chronon-ai`** on PyPI; service module is built with Vert.x and exposes `/v1/features/join/{name}` and `/v1/features/groupby/{name}` bulkGet endpoints returning a `results[]` array with `status`/`entityKeys`/`features` per lookup.
- **Feature-serving service endpoints** emit metrics under `ai.zipline.*` (old project name was Zipline — still used in some code paths and docs).

## Quotes

> "Chronon is a platform that abstracts away the complexity of data computation and serving for AI/ML applications. Users define features as transformation of raw data, then Chronon can perform batch and streaming computation, scalable backfills, low-latency serving, guaranteed correctness and consistency."
> — README

> "It's currently used to power all major ML applications within Airbnb, as well as major use cases at Stripe. Airbnb and Stripe jointly manage and maintain the project."
> — `docs/source/getting_started/Introduction.md`

> "At scale, aggregating O(n) events per request can become computationally expensive. For example, with an event stream generating 10 events/sec for a specific key, each feature request with a 12-hour window requires fetching and aggregating 432,000 events. […] A request for feature values in this architecture would only fetch and merge 12 or 13 1-hour tiles."
> — `docs/source/Tiled_Architecture.md`

> "Hot path is in sense the 'inner loop' of the larger program. […] Don't use scala `for` loops. Don't use ranges. Don't use `Option`s and `Tuple`s. Don't use immutable collections. Create naked Arrays when the size is known ahead of time."
> — `docs/source/Code_Guidelines.md`

## Connections

- [Chronon](../entities/chronon.md) — the product entity.
- [Airbnb](../entities/airbnb.md) — originator and co-maintainer.
- [Stripe](../entities/stripe.md) — co-maintainer; drove the Tiled Architecture and CHIP-1 caching work.
- [Apache Airflow](../entities/apache-airflow.md) — Chronon's default orchestrator; generates one DAG per team and per Join.
- [Feature Platform](../concepts/feature-platform.md) — the product category Chronon instantiates.
- [Point-in-Time Correctness](../concepts/point-in-time-correctness.md) — the backfill guarantee that makes training-serving consistency tractable.
- [Online/Offline Consistency](../concepts/online-offline-consistency.md) — the core guarantee and the measurement framework.
- [Tiled Feature Aggregation](../concepts/tiled-feature-aggregation.md) — pre-aggregated IRs in the KV store; the architecture shift Stripe open-sourced.
- [Claude Code](../entities/claude-code.md) — Chronon ships a `.claude/` directory with CLAUDE.md and 10 specialist/user slash commands; another datapoint in the Claude Code ecosystem trend.

## Questions Raised

- How does Chronon compare concretely to Feast, Tecton, and Hopsworks on (a) point-in-time-correctness guarantees, (b) streaming primitives, and (c) online/offline consistency measurement? The repo claims uniqueness but doesn't benchmark.
- Is the Zipline → Chronon rebrand complete, or are internal Airbnb systems still calling it Zipline? Metrics namespace is still `ai.zipline.*`.
- What KV stores are production-proven beyond MongoDB (quickstart) and implied Cassandra? Is there a reference implementation for Redis, DynamoDB, or RocksDB?
- CHIP-2 targets a monorepo reorganization. What's the expected completion date, and does it block downstream adopters from upgrading?
- The `.claude/` directory suggests maintainers are using Claude Code themselves. What's the adoption pattern — individual maintainers or team-wide? Could this be a template for other OSS projects?

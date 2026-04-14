---
title: Chronon
type: entity
entity_type: product
tags: [feature-platform, ml-infra, open-source, airbnb, stripe]
---

## Overview

Chronon is an open-source feature platform for machine learning, jointly created and maintained by Airbnb and Stripe. It lets ML teams define features once in Python and have Chronon produce point-in-time-correct historical backfills, real-time streaming updates, low-latency online serving, and automated online/offline consistency measurements — all from the same definition. It powers all major ML applications at Airbnb and major use cases at Stripe.

## Key Facts

- **License**: Apache 2.0. Source: [github.com/airbnb/chronon](https://github.com/airbnb/chronon). Docs: chronon.ai.
- **Packages**: `chronon-ai` on PyPI (Python API); Scala/Java artifacts on Maven Central.
- **Original name**: Zipline. Renamed to Chronon; the `ai.zipline.*` metrics namespace and some internal references persist.
- **Core API objects**: `GroupBy` (aggregations on a Source keyed by entities), `Join` (combine GroupBys on a left-side timestamp timeline), `StagingQuery` (SQL-based data prep), `Source` (`EventSource` or `EntitySource`).
- **Engines**: Spark (batch backfill/upload), Flink (streaming + tiled write path), Spark Streaming (legacy), online `Fetcher` library (Scala/Java), `service/` Vert.x REST/gRPC shim.
- **KV store**: Pluggable via `Api.KVStore` trait. MongoDB used in the Docker quickstart.
- **Orchestrator**: Apache Airflow (default). One DAG per team for batch/streaming, one DAG per Join for computation and consistency.
- **Key algorithm**: Sawtooth Windows — sliding head + hopping tail — enables efficient online aggregation with backfill-accurate semantics.
- **Tiled Architecture**: pre-aggregated IRs stored as tiles in the KV store; O(tiles) reads; 33% latency cut at Stripe; Flink-only; opt-in via `enable_tiling=true` in GroupBy `customJson`.
- **Governance**: 13-seat PMC (8 Airbnb + 5 Stripe), CHIP process for major changes, dev@chronon.ai mailing list.
- **Build systems**: SBT (current primary), Bazel migration in progress (CHIP-2).
- **Languages**: Scala 2.12, Java, Python 3.10+.
- **Ships LLM tooling**: `.claude/CLAUDE.md` and 10 Claude Code slash commands (4 user + 6 developer/specialist) — data scientists get `groupby`/`join`/`staging-query`/`debug`, platform integrators get `architecture`/`integrate` plus specialists for aggregator/join-backfill/feature-serving/streaming.

## Appearances

- [airbnb/chronon source page](../sources/airbnb-chronon.md) — the ingested repo; full detail on API, architecture, governance, and CHIPs.

## Connections

- [Airbnb](airbnb.md) — creator and co-maintainer; 8 PMC seats.
- [Stripe](stripe.md) — co-maintainer; 5 PMC seats; drove the Tiled Architecture and CHIP-1 caching.
- [Apache Airflow](apache-airflow.md) — default control-plane orchestrator for Chronon's generated DAGs.
- [Claude Code](claude-code.md) — Chronon's repo ships a `.claude/` directory with CLAUDE.md and specialist slash commands; example of Claude Code adoption by a major OSS project.
- [Feature Platform](../concepts/feature-platform.md) — product category.
- [Point-in-Time Correctness](../concepts/point-in-time-correctness.md) — Chronon's core backfill guarantee.
- [Online/Offline Consistency](../concepts/online-offline-consistency.md) — the central promise and measurement framework.
- [Tiled Feature Aggregation](../concepts/tiled-feature-aggregation.md) — the architecture shift open-sourced by Stripe.

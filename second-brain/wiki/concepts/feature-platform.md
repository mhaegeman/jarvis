---
title: Feature Platform
type: concept
tags: [ml-infra, feature-store, data-engineering]
---

## Definition

A **feature platform** is ML infrastructure that lets teams define a feature once and automatically produces (1) historical, point-in-time-correct training datasets, (2) up-to-date feature values available via low-latency lookup for online inference, (3) streaming and/or batch pipelines that keep the online values fresh, and (4) observability over freshness, drift, and consistency between the online and offline values. It is a superset of a "feature store" — the store is the serving cache; the platform is the authoring, compute, orchestration, and consistency system around it.

## Why It Matters

Most ML systems end up maintaining two implementations of every feature: one in the data warehouse (for training) and one in a service (for serving). Training-serving skew — the divergence between these two — is a leading cause of silent model degradation in production. A feature platform collapses both into a single definition and guarantees they compute the same thing, which removes a whole class of errors and enables teams to ship more models faster.

## Evidence & Examples

- [Chronon](../entities/chronon.md) — the open-source feature platform jointly built by Airbnb and Stripe. Authors `GroupBy`/`Join`/`StagingQuery` in Python; compiles to Thrift; runs on Spark (batch) and Flink (streaming); serves via a Fetcher library from a pluggable KV store. Provides [point-in-time correctness](point-in-time-correctness.md) and [online/offline consistency measurement](online-offline-consistency.md) as core guarantees.
- The [airbnb/chronon README](../sources/airbnb-chronon.md) frames the problem in three approaches: (1) **log-and-wait** (log features in prod, accumulate, train) — simple but slow to bootstrap and can't do big warehouse aggregations; (2) **replicate offline-online** (build warehouse features, re-implement in the online stack) — error-prone; (3) **feature platform** — define once, let the system handle both contexts.

## Tensions & Counterarguments

- **Scope creep risk**: Feature platforms can grow to swallow orchestration, data quality, lineage, and discovery — becoming mini data platforms in their own right. Chronon explicitly does this (its control plane is Airflow DAGs it generates). Whether this is value or bloat depends on an org's existing tooling.
- **Streaming is hard**: The "same definition for batch and streaming" promise requires real work — Chronon uses a stateful Flink operator running Spark's Catalyst engine inside Flink via `CatalystUtil` to evaluate the same SQL expression both sides.
- **Consistency is asymptotic, not absolute**: Chronon's own docs acknowledge that realtime features can never be 100% consistent with batch due to network and KV-store write latencies (ms–seconds) and midnight batch-refresh windows (minutes–hours). The platform measures inconsistency rather than eliminating it.

## Related

- [Chronon](../entities/chronon.md) — the canonical open-source example.
- [Point-in-Time Correctness](point-in-time-correctness.md) — the training-side guarantee.
- [Online/Offline Consistency](online-offline-consistency.md) — the serving-side guarantee.
- [Tiled Feature Aggregation](tiled-feature-aggregation.md) — a scaling pattern that makes feature platforms viable at high read QPS and hot-key traffic.

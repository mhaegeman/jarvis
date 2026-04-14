---
title: Stripe
type: entity
entity_type: org
tags: [tech-company, payments, ml-infra, open-source, feature-platform]
---

## Overview

Stripe is the US payments-infrastructure company that co-maintains Chronon with Airbnb. Stripe adopted Chronon internally for major ML use cases and contributed back the two most significant recent architectural advances: the Tiled Architecture (pre-aggregated IRs in the KV store, open-sourced via PRs #523/#531) and CHIP-1 (Caffeine-based IR and GetRequest caching in the Fetcher).

## Key Facts

- Adopted Chronon for major ML use cases; uses the tiled implementation in production.
- Holds 5 of 13 PMC seats on Chronon (Airbnb holds the other 8).
- Open-sourced the Tiled Architecture — reported 33% serving-latency reduction after initial implementation.
- Authored CHIP-1 (online IR and GetRequest caching); reported 22–35% latency reduction from BatchIr caching in load tests with shared 20K-element cache across 10–15 GroupBys.
- Runs Flink for streaming because the Tiled Architecture depends on a stateful Flink window operator.

## Appearances

- [airbnb/chronon source page](../sources/airbnb-chronon.md) — co-maintainer; Tiled Architecture and CHIP-1 contributor.

## Connections

- [Chronon](chronon.md) — co-maintained feature platform.
- [Airbnb](airbnb.md) — co-maintainer.
- [Tiled Feature Aggregation](../concepts/tiled-feature-aggregation.md) — the architecture Stripe contributed.

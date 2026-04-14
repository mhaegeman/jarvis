---
title: Point-in-Time Correctness
type: concept
tags: [ml-infra, feature-engineering, data-quality, backfill]
---

## Definition

**Point-in-time correctness (PITC)** is the guarantee that a historical feature value computed at time `t` uses only data that was available at time `t` — no future leakage. For every row `(key, t)` in a training dataset, every windowed aggregation (e.g. `purchase_sum_30d`) is computed exactly as it would have been if the system had been queried at that `t`.

## Why It Matters

Without PITC, training data silently leaks future information into features, which inflates offline metrics and causes models to underperform the moment they hit production — the classic "great offline, terrible online" failure. PITC is also what makes [online/offline consistency](online-offline-consistency.md) meaningful: if the offline value isn't point-in-time correct, it can't be compared to what was served online at that moment.

## Evidence & Examples

- [Chronon](../entities/chronon.md)'s core backfill contract: in a `Join`, the `left` source defines `(keys, timestamp)` pairs; every `GroupBy` on the right is computed as-of that timestamp. Per the docs: "if one of the rows on the left was for `user_id = 123` and `ts = 2023-10-01 10:11:23.195`, then the `purchase_price_avg_30d` feature would be computed for that user with a precise 30 day window ending on that timestamp."
- Chronon implements PITC efficiently via the **Sawtooth Windows** algorithm (`docs/source/window_tiling.md`): pre-aggregated hops for the window tail + a sliding head for the last hop. The naive SQL approach — `JOIN views ON view.ts < query.ts AND view.ts >= query.ts - window` — is quadratic and blows up on skewed keys; Sawtooth reduces this to near-linear.
- **Mutations handling**: for `EntitySource`s (dimension data with updates/deletes), Chronon requires a mutations stream + midnight snapshots to reconstruct historical state. Reversible aggregations (Sum/Count/Avg/Histogram) make this efficient; non-reversible ones (Min/Max/Variance/ApproxDistinctCount) cannot efficiently replay deletes.

## Tensions & Counterarguments

- PITC has a compute cost. Some orgs settle for **midnight-accurate aggregations** — features as of the most recent midnight, not the request timestamp — because it's dramatically cheaper. Chronon supports this explicitly as the `SNAPSHOT` accuracy mode.
- PITC only applies to historical backfills. Online serving has its own temporal semantics (realtime streaming + batch refresh) that can deviate; that's precisely what [online/offline consistency measurement](online-offline-consistency.md) quantifies.

## Related

- [Chronon](../entities/chronon.md) — the canonical PITC implementation.
- [Online/Offline Consistency](online-offline-consistency.md) — PITC is the offline side of the consistency equation.
- [Tiled Feature Aggregation](tiled-feature-aggregation.md) — the online-side equivalent of Sawtooth's hopping tail.
- [Feature Platform](feature-platform.md) — PITC is the defining requirement of any real feature platform.

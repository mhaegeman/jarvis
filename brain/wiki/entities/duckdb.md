---
title: DuckDB
type: entity
entity_type: product
tags: [database, analytical-sql, olap, embedded-database, python, data-engineering]
---

## Overview

DuckDB is an in-process OLAP SQL database designed for analytical workloads. It runs embedded inside a process (no separate server needed), supports Parquet, CSV, and JSON directly, and provides columnar storage for high-performance analytics. Increasingly popular as a lightweight alternative to Spark for local or single-node analytical SQL.

## Key Facts

- Zero-setup: no server process; runs embedded in Python, R, Java, etc.
- Reads Parquet, CSV, JSON, Arrow formats natively.
- Used by Nao as the primary analytical query engine for the `jaffle_shop` demo database.
- OLAP-optimised: much faster than SQLite for analytical aggregations on large datasets.

## Appearances

- [getnao / Nao source page](../sources/getnao-nao.md) — DuckDB is the analytical database powering Nao's data analysis capabilities.

## Connections

- [getnao / Nao](../sources/getnao-nao.md) — the platform that uses DuckDB as its data engine.

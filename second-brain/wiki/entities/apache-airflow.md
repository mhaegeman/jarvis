---
title: Apache Airflow
type: entity
entity_type: product
tags: [workflow-orchestration, data-engineering, dag, python, open-source, apache]
---

## Overview

Apache Airflow is the dominant open-source workflow orchestration platform for data engineering. Pipelines are defined as Directed Acyclic Graphs (DAGs) in Python, making them version-controllable and testable. Airflow is widely used in data teams for ETL, ML pipelines, and any multi-step data workflow.

## Key Facts

- DAG-based pipeline definition: each task is a node, dependencies are edges.
- Extensible via providers (connectors to external services: databases, APIs, cloud platforms).
- Ask Astro uses Airflow DAGs for its data ingestion pipeline (embedding, chunking, vector DB upload).
- Chronon uses Airflow as its default control-plane orchestrator — auto-generated DAGs per team (batch, streaming, staging-query) and per Join (computation, consistency) plus a daily metadata upload.
- Managed by Astronomer on the Astro platform; also available on AWS MWAA, GCP Cloud Composer.

## Appearances

- [Ask Astro source page](../sources/astronomer-ask-astro.md) — Ask Astro's ingestion layer is built on Airflow DAGs; the bot answers questions about Airflow.
- [airbnb/chronon source page](../sources/airbnb-chronon.md) — Chronon generates Airflow DAGs from Python feature definitions; the control plane is entirely Airflow-driven.

## Connections

- [Astronomer](../entities/astronomer.md) — company that provides managed Airflow (Astro) and created Ask Astro.
- [Weaviate](../entities/weaviate.md) — Ask Astro uses Airflow DAGs to ingest data into Weaviate.
- [Chronon](../entities/chronon.md) — feature platform whose control plane runs as Airflow DAGs (one per team, one per Join).

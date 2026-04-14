# Wiki Log
_Append-only. Newest entries at the top._
_Parse tip: `grep "^## \[" log.md | head -10` for recent entries._

---

## [2026-04-14] ingest | airbnb/chronon — Open-Source ML Feature Platform

**Operation:** ingest
**Summary:** Ingested GitHub repo airbnb/chronon via repomix (docs-only, excluded SVG/binaries/lockfiles; 464KB, 109K tokens, 66 files). Chronon is the canonical open-source feature platform for ML, co-maintained by Airbnb (8 PMC seats) and Stripe (5 PMC seats), Apache 2.0. One Python definition (`GroupBy`/`Join`/`StagingQuery`) drives four outputs: point-in-time-correct historical backfills on Spark, realtime streaming updates on Flink, low-latency online serving via a Scala/Java `Fetcher` against a pluggable KV store, and automated online/offline consistency measurement. Core algorithms: Sawtooth Windows (sliding head + hopping tail) for PITC, and the Tiled Architecture (Stripe-contributed) for O(tiles) online reads vs O(events) — 33% latency cut. Also: CHIP-1 (Caffeine IR + GetRequest caching, 22–35% batch latency cut), CHIP-2 (Bazel migration, monorepo reorg), and a full `.claude/` directory with CLAUDE.md + 10 specialist slash commands. Created 1 source page, 3 entity pages (Chronon, Airbnb, Stripe), and 4 concept pages (Feature Platform, Point-in-Time Correctness, Online/Offline Consistency, Tiled Feature Aggregation). Updated Apache Airflow entity (Chronon uses Airflow as default orchestrator), Claude Code entity (Chronon as major OSS adopter), overview.md (Theme 12 on feature platforms + 2 new open questions), hot.md (rewritten), and index.md (80 pages).
**Pages touched:** [sources/airbnb-chronon.md](sources/airbnb-chronon.md), [entities/chronon.md](entities/chronon.md), [entities/airbnb.md](entities/airbnb.md), [entities/stripe.md](entities/stripe.md), [concepts/feature-platform.md](concepts/feature-platform.md), [concepts/point-in-time-correctness.md](concepts/point-in-time-correctness.md), [concepts/online-offline-consistency.md](concepts/online-offline-consistency.md), [concepts/tiled-feature-aggregation.md](concepts/tiled-feature-aggregation.md), [entities/apache-airflow.md](entities/apache-airflow.md), [entities/claude-code.md](entities/claude-code.md), [hot.md](hot.md), [overview.md](overview.md), [index.md](index.md)

---

## [2026-04-13] ingest | jumbocontext/jumbo.cli — Memory & Context Orchestration for Coding Agents

**Operation:** ingest
**Summary:** Ingested GitHub repo jumbocontext/jumbo.cli via repomix (docs-only, 55K tokens, 49 files). Jumbo is a CLI tool for memory and context orchestration for coding agents — it solves agent amnesia via a local event-sourced entity graph (.jumbo/) and delivers dynamically assembled context packets at workflow transitions. Core innovation is the 5-phase goal lifecycle (define → refine → implement → review → codify) where refinement links relevant entities to goals and implementation receives precisely scoped context. Agent-agnostic: supports Claude Code, Copilot, Gemini, Cursor, Codex, Vibe. Ships 12 Claude Code skills. Created 1 source page, 1 entity page (Jumbo), and 1 concept page (Agent Context Orchestration). Updated Agentic Workflow Patterns to reference Jumbo as the most structured lifecycle variant. Updated Claude Code entity and LLM Wiki Pattern concept with cross-references. Added Theme 11 to overview. Index updated to 72 pages.
**Pages touched:** [sources/jumbocontext-jumbo-cli.md](sources/jumbocontext-jumbo-cli.md), [entities/jumbo.md](entities/jumbo.md), [concepts/agent-context-orchestration.md](concepts/agent-context-orchestration.md), [concepts/agentic-workflow-patterns.md](concepts/agentic-workflow-patterns.md), [entities/claude-code.md](entities/claude-code.md), [concepts/llm-wiki-pattern.md](concepts/llm-wiki-pattern.md), [index.md](index.md), [overview.md](overview.md)

---

## [2026-04-13] ingest | nexos.ai — Competitor Analysis (4 website pages)

**Operation:** ingest
**Summary:** Ingested 4 pages from nexos.ai's website (homepage, AI Guardrails, AI Governance, AI for Lawyers) as competitive intelligence for the GuardRail project. Critical finding: nexos.ai is NOT a compliance competitor — it's an all-in-one AI workspace/gateway platform ($350M valuation, NordVPN founders). Their "guardrails" = input/output PII filtering, their "governance" = token spend tracking and model access control. No AI Act risk classification, conformity assessment, or documentation generation. Different problem (safe AI usage vs. regulatory compliance), different buyer (CTO vs. compliance officer), minimal direct overlap. Adjacency risk noted: they have EU presence, enterprise customers, and could add compliance features. Created 1 source page (consolidated from 4 raw files) and 1 entity page. Updated hot.md. Index at 69 pages.
**Pages touched:** [sources/nexos-ai-website.md](sources/nexos-ai-website.md), [entities/nexos-ai.md](entities/nexos-ai.md), [hot.md](hot.md), [index.md](index.md)

---

## [2026-04-13] ingest | ruvnet/ruflo — Enterprise Multi-Agent AI Orchestration

**Operation:** ingest
**Summary:** Ingested GitHub repo ruvnet/ruflo (formerly Claude Flow) via repomix (docs-only, 24MB output, 6.67M tokens, 2,439 files). RuFlo is the most comprehensive Claude Code agent orchestration framework available — 100+ agents, 137+ skills, 313+ MCP tools, 4 swarm topologies, 5 consensus protocols, self-learning via SONA/EWC++/ReasoningBank, 3-tier intelligent routing with WASM Agent Booster, SPARC methodology, claims-based authorization, and multi-provider LLM support. Created 1 source page, 1 entity page (RuFlo), and 6 concept pages covering the major architectural patterns: Swarm Coordination Topologies, Multi-Agent Consensus Protocols, Self-Learning Agent Architecture, Intelligent Task Routing, SPARC Methodology, Claims-Based Agent Authorization. Updated Agentic Workflow Patterns concept to reference RuFlo and link to all new concept pages. The priority was extracting all actionable concepts so the wiki owner can reference them when building agent workflows. Index updated to 67 pages.
**Pages touched:** [sources/ruvnet-ruflo.md](sources/ruvnet-ruflo.md), [entities/ruflo.md](entities/ruflo.md), [concepts/swarm-coordination-topologies.md](concepts/swarm-coordination-topologies.md), [concepts/multi-agent-consensus-protocols.md](concepts/multi-agent-consensus-protocols.md), [concepts/self-learning-agent-architecture.md](concepts/self-learning-agent-architecture.md), [concepts/intelligent-task-routing.md](concepts/intelligent-task-routing.md), [concepts/sparc-methodology.md](concepts/sparc-methodology.md), [concepts/claims-based-agent-authorization.md](concepts/claims-based-agent-authorization.md), [concepts/agentic-workflow-patterns.md](concepts/agentic-workflow-patterns.md), [index.md](index.md)

---

## [2026-04-13] ingest | Fabio Cassisa — Professional Profile

**Operation:** ingest
**Summary:** Ingested LinkedIn profile for Fabio Cassisa — an AI engineer/architect building complex agents at Adnami (ad tech), with a "unicorn full-stack + design" profile. He evolved from industrial design through front-end and blockchain development into AI agent architecture. His AI Ethics coursework at Malmö University (15 credits, grade B) is directly relevant to the EU AI Act space. Fabio is a friend of Maxime and a potential collaborator on GuardRail. Created 1 source page and 1 person page. Updated ideas.md to add Fabio as the fourth team member (Creative Technology & AI Agent Lead) on the GuardRail project. Updated generate_pitch.mjs to include Fabio on the title slide, team slide (now 4 columns), "Why This Combination Wins" slide, competitive landscape table, MVP plan (added Fabio's tasks per phase), risks slide, and closing slide. Index updated to 59 pages.
**Pages touched:** [sources/fabio-cassisa-profile.md](sources/fabio-cassisa-profile.md), [people/fabio-cassisa.md](people/fabio-cassisa.md), [index.md](index.md), ideas.md, generate_pitch.mjs

---

## [2026-04-13] ingest | Karoline Geiker — Professional Profile

**Operation:** ingest
**Summary:** Ingested LinkedIn profile for Karoline Geiker — a Law and Technology specialist based in Copenhagen. She holds an LLM in Law and Technology from Tilburg University (2023-2025) and is pursuing a cand.jur. at the University of Copenhagen (2024-2027). Her experience includes EU legislative analysis at ECSDA (examining MEP amendments on the DLT pilot regime) and legal research at the Institute for European Studies, VUB Brussels. Created 1 source page and 1 person page. Updated index to 57 pages. She has been added to the GuardRail project ideation in ideas.md as the team's legal/regulatory specialist.
**Pages touched:** [sources/karoline-geiker-profile.md](sources/karoline-geiker-profile.md), [people/karoline-geiker.md](people/karoline-geiker.md), [index.md](index.md)

---

## [2026-04-12] ingest | 9 GitHub Repos — AI/ML Tools, Agents, Vision Models, LLM Course

**Operation:** ingest
**Summary:** Batch-ingested 9 GitHub repositories via repomix (docs-only mode). Repos span four clusters: (1) Claude Code tooling — EduardPetraeus/claude-code-quickstart (starter kit with 8 rules/10 hooks/9 agents), Leavitskiy/claude-agentic-flow (domain-specific agent library), Owl-Listener/designer-skills (50+ designer skills), getnao/nao (data analytics platform with embedded multi-agent code-review skill); (2) LLM education — mlabonne/llm-course (free curriculum covering fine-tuning, quantisation, RAG); (3) Document AI — facebookresearch/nougat (neural PDF OCR for LaTeX math), IAmTomShaw/document-chatbot-offline (offline PDF Q&A via Windows AI Foundry); (4) Computer vision foundation models — facebookresearch/segment-anything (SAM, zero-shot segmentation); (5) Production RAG — astronomer/ask-astro (a16z reference RAG app on Airflow+Weaviate). Created 9 source pages, 6 entity pages (Meta AI Research, Astronomer, Apache Airflow, Weaviate, Windows AI Foundry, DuckDB), 6 concept pages (Agentic Workflow Patterns, Promptable Visual Segmentation, Neural Document OCR, LLM Fine-Tuning, LLM Quantization, Offline LLM Inference), 1 person page (Maxime Labonne). Updated Claude Code entity with new repo appearances. Updated CLAUDE.md to mandate Tech Stack and Purpose sections in GitHub repo source pages. Total pages: 55 (was 33).
**Pages touched:** [sources/owl-listener-designer-skills.md](sources/owl-listener-designer-skills.md), [sources/getnao-nao.md](sources/getnao-nao.md), [sources/iamtomshaw-document-chatbot-offline.md](sources/iamtomshaw-document-chatbot-offline.md), [sources/astronomer-ask-astro.md](sources/astronomer-ask-astro.md), [sources/mlabonne-llm-course.md](sources/mlabonne-llm-course.md), [sources/facebookresearch-nougat.md](sources/facebookresearch-nougat.md), [sources/facebookresearch-segment-anything.md](sources/facebookresearch-segment-anything.md), [sources/eduardpetraeus-claude-code-quickstart.md](sources/eduardpetraeus-claude-code-quickstart.md), [sources/leavitskiy-claude-agentic-flow.md](sources/leavitskiy-claude-agentic-flow.md), [entities/meta-ai-research.md](entities/meta-ai-research.md), [entities/astronomer.md](entities/astronomer.md), [entities/apache-airflow.md](entities/apache-airflow.md), [entities/weaviate.md](entities/weaviate.md), [entities/windows-ai-foundry.md](entities/windows-ai-foundry.md), [entities/duckdb.md](entities/duckdb.md), [entities/claude-code.md](entities/claude-code.md), [concepts/agentic-workflow-patterns.md](concepts/agentic-workflow-patterns.md), [concepts/promptable-visual-segmentation.md](concepts/promptable-visual-segmentation.md), [concepts/neural-document-ocr.md](concepts/neural-document-ocr.md), [concepts/llm-fine-tuning.md](concepts/llm-fine-tuning.md), [concepts/llm-quantization.md](concepts/llm-quantization.md), [concepts/offline-llm-inference.md](concepts/offline-llm-inference.md), [people/maxime-labonne.md](people/maxime-labonne.md), [index.md](index.md), [overview.md](overview.md), [../CLAUDE.md](../CLAUDE.md)

---

## [2026-04-12] ingest | Harsh Kakroo — Portfolio & Profile (7 raw files)

**Operation:** ingest
**Summary:** Ingested 7 raw files from harshkakroo.com. Homepage and about page provided substantive profile content; 5 case study pages were image-only captures (no text beyond titles and discipline tags). Harsh Kakroo is a UX Researcher & Product Designer at Massive Entertainment — a colleague of Maxime Haegeman — who worked on Avatar: Frontiers of Pandora and Star Wars Outlaws. Created 1 source page and 1 person page. Updated Massive Entertainment entity to add Harsh. Index updated to 33 pages. Note: case study detail is unavailable without re-capturing with a text-preserving web clipper.
**Pages touched:** [sources/harsh-kakroo-portfolio.md](sources/harsh-kakroo-portfolio.md), [people/harsh-kakroo.md](people/harsh-kakroo.md), [entities/massive-entertainment.md](entities/massive-entertainment.md), [index.md](index.md)

---

## [2026-04-12] ingest | Boris Cherny — How Claude Code's Creator Starts Every Project

**Operation:** ingest
**Summary:** Ingested YouTube transcript (boris-cherny.md) covering Boris Cherny's 6 Claude Code workflow principles: Plan Mode, minimal CLAUDE.md, verification loops (2–3x quality), parallel sessions with partitioned tasks, slash commands for inner loops, and the Bitter Lesson / "never bet against the model." Created 1 source page, 1 person page (Boris Cherny), and 1 entity page (Claude Code). Updated overview.md to expand the wiki's stated scope to three domains (AI forecasting, practical AI tooling, personal knowledge) and added Theme 6 connecting the Bitter Lesson to this wiki's own architecture. Index updated to 31 pages.
**Pages touched:** [sources/boris-cherny-claude-code-workflow.md](sources/boris-cherny-claude-code-workflow.md), [people/boris-cherny.md](people/boris-cherny.md), [entities/claude-code.md](entities/claude-code.md), [overview.md](overview.md), [index.md](index.md)

---

## [2026-04-12] ingest | Maxime Haegeman — Professional Profile (4 raw files)

**Operation:** ingest
**Summary:** Ingested four raw source files comprising Maxime Haegeman's professional profile: GitHub README (mhaegeman - Overview.md), portfolio homepage (Maxime Haegeman Data Engineer.md), CV/work history (Maxime Resume.md), and project list (Maxime Projects.md). All four compiled into one source page. Maxime is the wiki owner — Senior Data / ML Engineer, currently at Massive Entertainment (Ubisoft, Malmö), 5 years experience in data pipelines, ML, and analytics. Created 1 source page, 1 person page (Maxime Haegeman), and 1 entity page (Massive Entertainment). Index updated to 28 pages.
**Pages touched:** [sources/maxime-haegeman-profile.md](sources/maxime-haegeman-profile.md), [people/maxime-haegeman.md](people/maxime-haegeman.md), [entities/massive-entertainment.md](entities/massive-entertainment.md), [index.md](index.md)

---

## [2026-04-12] ingest | RAG-Anything (HKUDS/RAG-Anything)

**Operation:** ingest
**Summary:** Ingested GitHub repo https://github.com/HKUDS/RAG-Anything via WebFetch (repomix unavailable in shell). Fetched README.md + all 5 docs/ files + env.example. RAG-Anything is an all-in-one multimodal RAG framework built on LightRAG, handling text, images, tables, equations via a knowledge graph + vector hybrid pipeline. Created 1 source page, 2 entity pages (RAG-Anything, LightRAG), and 1 concept page (Multimodal RAG). Updated RAG vs Wiki Architecture to reference RAG-Anything as a concrete example of advanced RAG. Index updated to 25 pages.
**Pages touched:** [sources/hkuds-rag-anything.md](sources/hkuds-rag-anything.md), [entities/rag-anything.md](entities/rag-anything.md), [entities/lightrag.md](entities/lightrag.md), [concepts/multimodal-rag.md](concepts/multimodal-rag.md), [concepts/rag-vs-wiki-architecture.md](concepts/rag-vs-wiki-architecture.md), [index.md](index.md)

---

## [2026-04-12] schema-update | GitHub Repo Ingest operation added to CLAUDE.md

**Operation:** update
**Summary:** Added autonomous GitHub Repo Ingest operation to CLAUDE.md (Section 6). The operation triggers on a GitHub URL, runs repomix with a docs-first `--include` filter, verifies output size, and then falls through to the standard ingest workflow. Also added `source_url` as an optional frontmatter field to the source page format, updated the `raw/` read-only rule with an explicit exception for repomix output, and mandated `github`/`open-source` tags for all repo ingests. Schema bumped to 1.2.
**Pages touched:** [CLAUDE.md](../CLAUDE.md)

---

## [2026-04-12] update | Enhanced tags on source pages + added tagging schema to CLAUDE.md

**Operation:** update
**Summary:** User requested thorough tagging for research discoverability. Expanded tags on both source pages from 5 generic tags to 10–25 tags spanning domain, content type, key concepts, technical specifics, entities/people, time period, and stakes framing. Added Section 12 (Tagging) to CLAUDE.md with a full taxonomy, multi-line YAML format guidance, and rules for future ingests. Schema bumped to 1.1.
**Pages touched:** [sources/ai-2027.md](sources/ai-2027.md), [sources/llm-wiki-idea-file.md](sources/llm-wiki-idea-file.md), [CLAUDE.md](../CLAUDE.md)

---

## [2026-04-12] schema-update | Added People section to index and CLAUDE.md

**Operation:** update
**Summary:** User requested a dedicated "People" section in the wiki, separate from orgs/products. Updated CLAUDE.md schema to add `wiki/people/` directory and person page format. Moved Vannevar Bush and Daniel Kokotajlo from `entities/` to `people/`. Updated index.md format and rebuild. CLAUDE.md now distinguishes `people/` (individuals) from `entities/` (orgs, products, projects).
**Pages touched:** [CLAUDE.md](../CLAUDE.md), [index.md](index.md), [people/vannevar-bush.md](people/vannevar-bush.md), [people/daniel-kokotajlo.md](people/daniel-kokotajlo.md)

---

## [2026-04-12] ingest | AI 2027

**Operation:** ingest
**Summary:** Ingested the AI 2027 scenario (ai-2027.com, April 2025). Created source page with full timeline table and key claims. Created 2 entity pages (OpenBrain, DeepCent), 1 person page (Daniel Kokotajlo), and 5 concept pages (AI R&D Progress Multiplier, Intelligence Explosion, Neuralese Recurrence, IDA, AI Alignment and Scheming, AI Arms Race, Superintelligence Milestones). Updated index (21 pages total) and overview. Major new themes: intelligence explosion, adversarial AI misalignment, US-China AI arms race.
**Pages touched:** [sources/ai-2027.md](sources/ai-2027.md), [entities/openbrain.md](entities/openbrain.md), [entities/deepcent.md](entities/deepcent.md), [people/daniel-kokotajlo.md](people/daniel-kokotajlo.md), [concepts/ai-rd-progress-multiplier.md](concepts/ai-rd-progress-multiplier.md), [concepts/intelligence-explosion.md](concepts/intelligence-explosion.md), [concepts/neuralese-recurrence.md](concepts/neuralese-recurrence.md), [concepts/iterated-distillation-amplification.md](concepts/iterated-distillation-amplification.md), [concepts/ai-alignment-scheming.md](concepts/ai-alignment-scheming.md), [concepts/ai-arms-race.md](concepts/ai-arms-race.md), [concepts/superintelligence-milestones.md](concepts/superintelligence-milestones.md), [index.md](index.md), [overview.md](overview.md)

---

## [2026-04-12] ingest | LLM Wiki — Idea File

**Operation:** ingest
**Summary:** First source ingested — the foundational idea file that defines the LLM Wiki Pattern itself. Created source summary page, 3 concept pages (LLM Wiki Pattern, RAG vs Wiki Architecture, Persistent Compounding Knowledge), 3 entity pages (Vannevar Bush, Obsidian, qmd). Updated index.md (9 pages total) and overview.md. The wiki now documents the pattern governing its own operation.
**Pages touched:** [sources/llm-wiki-idea-file.md](sources/llm-wiki-idea-file.md), [concepts/llm-wiki-pattern.md](concepts/llm-wiki-pattern.md), [concepts/rag-vs-wiki-architecture.md](concepts/rag-vs-wiki-architecture.md), [concepts/persistent-compounding-knowledge.md](concepts/persistent-compounding-knowledge.md), [entities/vannevar-bush.md](entities/vannevar-bush.md), [entities/obsidian.md](entities/obsidian.md), [entities/qmd.md](entities/qmd.md), [index.md](index.md), [overview.md](overview.md)

---

## [2026-04-12] setup | Wiki initialized

**Operation:** setup
**Summary:** Second brain wiki created from scratch. Directory structure established (`raw/`, `raw/assets/`, `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/analyses/`). Schema written to `CLAUDE.md`. `index.md`, `log.md`, and `overview.md` initialized. Wiki is empty and ready for first ingest.
**Pages touched:** [index.md](index.md), [log.md](log.md), [overview.md](overview.md)

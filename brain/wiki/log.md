# Wiki Log
_Append-only. Newest entries at the top._
_Parse tip: `grep "^## \[" log.md | head -10` for recent entries._

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

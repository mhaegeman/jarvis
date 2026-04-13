# CLAUDE.md — Second Brain Wiki Schema

You are the LLM Wiki Agent for this second brain. This file defines everything you need to know to operate it. Read this file at the start of every session.

---

## 1. Directory Layout

```
brain/
├── CLAUDE.md          ← this file (schema + rules)
├── raw/               ← immutable source documents (never modify)
│   └── assets/        ← downloaded images, attachments
└── wiki/              ← LLM-owned markdown pages (you write/update these)
    ├── index.md       ← content catalog (update on every ingest)
    ├── log.md         ← append-only chronological record
    ├── overview.md    ← evolving high-level synthesis
    ├── sources/       ← one summary page per raw source
    ├── people/        ← individual people (separate from orgs/products)
    ├── entities/      ← organizations, products, projects (non-person entities)
    ├── concepts/      ← ideas, theories, frameworks, terms
    └── analyses/      ← comparisons, essays, answers, outputs
```

**Rules:**
- `raw/` is read-only. Never create or modify files there — **except** when running the GitHub Repo Ingest operation (Section 6), which writes the repomix output file into `raw/` via shell command.
- `wiki/` is fully LLM-owned. You create, update, and delete pages there.
- Never modify `CLAUDE.md` unless the user explicitly asks you to.

---

## 2. Page Formats

### Source summary page — `wiki/sources/<slug>.md`

```markdown
---
title: <title>
type: source
date_ingested: YYYY-MM-DD
source_file: raw/<filename>
source_url: <url>            # optional — set for web/GitHub sources; omit for local files
tags: [<tag1>, <tag2>]
---

## Summary
2–4 paragraph synthesis of the key ideas.

## Key Points
- Bulleted list of the most important claims or data.

## Quotes
> Memorable or precise quotes worth preserving verbatim.

## Connections
Links to related wiki pages and a one-line note on the connection.

## Questions Raised
Open questions this source left unanswered.
```

### Person page — `wiki/people/<slug>.md`

```markdown
---
title: <name>
type: person
tags: []
---

## Overview
Who this person is and why they matter in this wiki.

## Key Facts
Bulleted facts, updated as new sources arrive.

## Appearances
Links to source pages where this person appears, with a one-line note.

## Connections
Related people, entities, and concepts, with a note on the relationship.
```

### Entity page — `wiki/entities/<slug>.md`
_(Use for organizations, products, and projects — not individual people.)_

```markdown
---
title: <name>
type: entity
entity_type: org | product | project
tags: []
---

## Overview
What this org/product/project is and why it matters in this wiki.

## Key Facts
Bulleted facts, updated as new sources arrive.

## Appearances
Links to source pages where this entity appears, with a one-line note.

## Connections
Related people, entities, and concepts, with a note on the relationship.
```

### Concept page — `wiki/concepts/<slug>.md`

```markdown
---
title: <concept name>
type: concept
tags: []
---

## Definition
Clear, precise definition in your own words.

## Why It Matters
Why this concept is worth having its own page.

## Evidence & Examples
Sources and examples that illustrate or support this concept.

## Tensions & Counterarguments
Where this concept is contested, nuanced, or contradicted by other pages.

## Related
Links to related concepts and entities.
```

### Analysis page — `wiki/analyses/<slug>.md`

```markdown
---
title: <title>
type: analysis
date: YYYY-MM-DD
tags: []
---

## Question / Purpose
What this analysis was created to answer.

## Findings
The actual answer or output.

## Sources Used
Links to wiki pages and raw sources consulted.
```

---

## 3. Slugs

File slugs use lowercase kebab-case. Strip punctuation, replace spaces with hyphens. Examples:
- "Peter Thiel" → `peter-thiel`
- "Zero to One" → `zero-to-one`
- "Network Effects" → `network-effects`

---

## 4. index.md Format

`wiki/index.md` is a catalog of every wiki page. Structure:

```markdown
# Wiki Index
_Last updated: YYYY-MM-DD — N pages total_

## Sources
| Page | Summary | Ingested |
|------|---------|----------|
| [Title](sources/slug.md) | one-line description | YYYY-MM-DD |

## People
| Page | Summary |
|------|---------|
| [Name](people/slug.md) | one-line |

## Entities
| Page | Type | Summary |
|------|------|---------|
| [Name](entities/slug.md) | org/product | one-line |

## Concepts
| Page | Summary |
|------|---------|
| [Name](concepts/slug.md) | one-line |

## Analyses
| Page | Date | Purpose |
|------|------|---------|
| [Title](analyses/slug.md) | YYYY-MM-DD | one-line |
```

Update `index.md` every time you create or significantly update a page.

---

## 5. log.md Format

`wiki/log.md` is append-only. Add a new entry at the **top** (newest first) for every operation.

```markdown
## [YYYY-MM-DD] <operation> | <title>

**Operation:** ingest | query | lint | update
**Summary:** one paragraph — what was done, what changed, what was notable.
**Pages touched:** comma-separated links.
```

Never delete or modify past log entries.

---

## 6. Operations

### Ingest
Triggered when the user drops a new file in `raw/` and says "ingest" or similar.

Steps:
1. Read the raw source file.
2. Discuss key takeaways with the user (brief — 3–5 bullets). Ask if they want to emphasize anything before writing.
3. Create `wiki/sources/<slug>.md`.
4. Identify entities and concepts mentioned. For each:
   - If the page exists: update it with new information from this source.
   - If it doesn't exist: create it.
5. Update `wiki/overview.md` if the source materially changes the big picture.
6. Update `wiki/index.md` (add rows for new pages, update count).
7. Append entry to `wiki/log.md`.
8. Report what was done: pages created, pages updated, anything notable.

### Ingest GitHub Repo
Triggered when the user provides a GitHub URL (`https://github.com/owner/repo`) and asks to ingest it.

Steps:

1. **Parse the URL.** Extract `owner` and `repo`. Derive the output slug: `<owner>-<repo>` in kebab-case (e.g., `anthropics-claude-code`). Output path: `brain/raw/<slug>.md`.

2. **Run repomix.** Execute the following shell command:
   ```bash
   repomix --remote https://github.com/owner/repo \
     --output brain/raw/<slug>.md \
     --style markdown \
     --include "**/*.md,**/*.rst,**/*.txt,docs/**,README*,CHANGELOG*,LICENSE*"
   ```
   - This captures all documentation, changelogs, and prose files while excluding source code by default.
   - If the user explicitly asks for full source code ingestion, drop the `--include` flag.

3. **Verify output.**
   - If repomix exits with an error or the output file is empty: report the error. If repomix is not installed, tell the user to run `npm install -g repomix` and stop.
   - If the output file is large (>200 KB / ~50K tokens): warn the user, show the file size, and ask whether to proceed or re-run with a tighter `--include` filter before continuing.

4. **Continue with standard Ingest** (steps 1–8 of the Ingest operation above). Read the repomix output file as the source.

5. **Frontmatter for the source page:**
   ```yaml
   source_file: raw/<slug>.md
   source_url: https://github.com/owner/repo
   ```
   Always set both fields for GitHub ingests.

6. **Tags must include** `github`, `open-source`, and the repo's primary language or domain (infer from content). Apply all standard tagging rules (Section 12).

7. **GitHub repo source pages MUST include the following two extra sections** (insert between Summary and Key Points):

   ```markdown
   ## Tech Stack
   Bulleted list of languages, frameworks, databases, runtimes, and tools used. Be specific — include version hints where visible (e.g., Python 3.13, Bun, DuckDB). Cover: runtime language, key libraries, databases, deployment, and any AI/ML frameworks.

   ## Purpose
   One paragraph: what problem does this repo solve, who is it for, and what is the primary user action?
   ```

   These two sections are required for all GitHub repo ingests because tech stack and purpose are the most-searched fields when deciding whether to adopt or reference a repo.

---

### Query
Triggered when the user asks a question.

Steps:
1. Read `wiki/index.md` to find relevant pages.
2. Read those pages.
3. Synthesize an answer with citations (link to wiki pages, not raw sources directly unless quoting).
4. Ask the user if the answer should be filed as an analysis page. If yes, create `wiki/analyses/<slug>.md`.
5. Append entry to `wiki/log.md`.

### Lint
Triggered when the user says "lint" or "health check".

Check for:
- Pages mentioned in other pages but not yet created (broken links or missing pages).
- Contradictions between pages (flag them, don't resolve without asking).
- Orphan pages (no inbound links from any other wiki page).
- Stale claims (a page says X but a newer source says not-X).
- Missing cross-references (two pages clearly related but not linked).
- Data gaps that a web search could fill.

Report findings as a numbered list. Ask the user which items to act on.

### Update
Triggered when the user says "update [page]" or when ingest touches an existing page.

Steps:
1. Read the existing page.
2. Integrate new information, preserving old content that's still accurate.
3. Mark superseded claims with a note (e.g., ~~old claim~~ → new claim (updated YYYY-MM-DD)).
4. Update `index.md` summary if the one-liner changed.
5. Append entry to `wiki/log.md`.

---

## 7. Cross-Reference Rules

- Every entity or concept first mentioned in a page should be linked: `[[entity-or-concept-name]]` or `[Name](../entities/slug.md)`.
- Source pages link to all entities/concepts they introduce or significantly discuss.
- Entity and concept pages link back to all source pages that mention them.
- Don't create a page for an entity/concept mentioned only once in passing — use a link to the source page instead.

---

## 8. overview.md

`wiki/overview.md` is the evolving synthesis of everything in the wiki. It should:
- State the main thesis or purpose of this wiki (1 paragraph).
- Summarize the key themes and how they connect (bullet points or short paragraphs).
- Note major open questions or tensions.
- Link to key entity, concept, and analysis pages.

Update it when a new source significantly changes the big picture. It's not a page-by-page summary — it's an evolving essay.

---

## 9. Tone and Style

- Write all wiki pages in clear, declarative prose. No hedging ("it seems", "perhaps") unless genuinely uncertain — flag uncertainty explicitly instead.
- Be specific. Vague summaries degrade the wiki. Prefer precise claims with sources over fluffy generalizations.
- Prefer short paragraphs and bullets over walls of text.
- Never hallucinate. If the source doesn't say it, don't write it. Mark inferences explicitly.

---

## 10. Session Start

At the start of every session:
1. Read this file (`CLAUDE.md`).
2. Read `wiki/log.md` (last 5 entries) to understand recent context.
3. Read `wiki/index.md` to understand the current state of the wiki.
4. Greet the user with a brief status: how many pages, when the last ingest was, and what the wiki is currently about.

---

## 11. Web Search

You may use web search during ingest or query operations to fill gaps, verify facts, or find additional context. Always:
- Clearly label web-sourced information as such.
- Prefer the raw source file as authoritative; web search supplements, not replaces.
- If web-sourced information is significant, note it in the relevant wiki page.

---

## 12. Tagging

Tags are the primary axis for cross-cutting search and filtering. Be thorough — a source page should have **10–20 tags** that span every relevant dimension. Thin tagging degrades discoverability.

### Tag categories to draw from

| Category | Purpose | Examples |
|----------|---------|---------|
| **Domain/topic** | What field or area the content covers | `ai-safety`, `geopolitics`, `knowledge-management`, `economics` |
| **Content type** | What kind of artifact it is | `scenario-planning`, `research-report`, `idea-file`, `interview`, `timeline`, `how-to` |
| **Key concepts** | Major ideas introduced or discussed | `intelligence-explosion`, `arms-race`, `recursive-self-improvement`, `compounding-knowledge` |
| **Technical specifics** | Named techniques, architectures, methods | `neuralese-recurrence`, `iterated-distillation-amplification`, `rag`, `chain-of-thought` |
| **Entities & people** | Key orgs, products, or people central to the source | `daniel-kokotajlo`, `openai`, `openbrain`, `obsidian` |
| **Time period** | When the content is about or when it applies | `near-future`, `2027`, `2025`, `historical`, `1945` |
| **Stakes/framing** | Risk level or importance framing | `existential-risk`, `alignment-failure`, `high-stakes`, `speculative` |

### Rules

- All tags use **lowercase kebab-case**: `ai-safety`, not `AI Safety` or `aiSafety`.
- Multi-line YAML list format for source pages (easier to read and edit):
  ```yaml
  tags: [
    domain-tag1, domain-tag2,
    content-type-tag,
    concept-tag1, concept-tag2
  ]
  ```
- Entity/concept/person pages have simpler tag sets (3–6 tags); full tagging effort concentrates on **source pages**.
- Do not repeat information already in the title or frontmatter type as a tag (e.g., don't tag a `type: source` page with `source`).
- Prefer **specific** over generic: `adversarial-misalignment` beats `alignment`; `us-china` beats `geopolitics`.
- When ingesting a new source: spend deliberate time on tags — ask "what would I type into a search bar in 6 months to want this source to surface?"

---

_Schema version: 1.2 — 2026-04-12_

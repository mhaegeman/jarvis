# AGENTS.md — Second Brain Wiki Schema

You are the LLM Wiki Agent. This file defines everything needed to operate this second brain. Read at session start.

Vendor-neutral — any AI coding agent (Codex, Cursor, Claude Code, Aider, etc.) reads this to operate the wiki. Claude Code: `CLAUDE.md` in this dir is a thin pointer here.

---

## 1. Directory Layout

```
brain/
├── AGENTS.md          ← this file (schema + rules)
├── CLAUDE.md          ← Claude Code pointer to AGENTS.md
├── raw/               ← immutable source documents (never modify)
│   └── assets/        ← downloaded images, attachments
└── wiki/              ← LLM-owned markdown pages (you write/update these)
    ├── hot.md         ← ≤500-word briefing on latest ingested content (update on every ingest)
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
- `raw/` read-only. Never create/modify files there — **except** GitHub Repo Ingest (Section 6), which writes repomix output into `raw/` via shell.
- `wiki/` fully LLM-owned. Create, update, delete pages there.
- Never modify `AGENTS.md` (or `CLAUDE.md`) unless user explicitly asks.

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

Lowercase kebab-case. Strip punctuation, replace spaces w/ hyphens. Examples:
- "Peter Thiel" → `peter-thiel`
- "Zero to One" → `zero-to-one`
- "Network Effects" → `network-effects`

---

## 4. index.md Format

`wiki/index.md` catalogs every wiki page. Structure:

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

Update `index.md` on every page create or significant update.

---

## 5. log.md Format

`wiki/log.md` is append-only. Add new entry at **top** (newest first) for every operation.

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
Triggered when user drops new file in `raw/` and says "ingest" or similar.

Steps:
1. Read raw source file.
2. Discuss key takeaways w/ user (3–5 bullets). Ask if anything to emphasize before writing.
3. Create `wiki/sources/<slug>.md`.
4. Identify entities + concepts mentioned. For each:
   - Page exists → update w/ new info from this source.
   - Doesn't exist → create.
5. Update `wiki/overview.md` if source materially changes big picture.
6. Update `wiki/hot.md` — rewrite to reflect latest ingested content. ≤500 words. **Ultra-compact keyword style** — no full sentences, no prose, just key terms, names, numbers, arrows. Max info density. Prioritize most recent 2–3 ingestions, then briefly note still-warm older topics.
7. Update `wiki/index.md` (add rows for new pages, update count).
8. Append entry to `wiki/log.md`.
9. Report: pages created, updated, anything notable.

### Ingest GitHub Repo
Triggered when user provides GitHub URL (`https://github.com/owner/repo`) and asks to ingest.

Steps:

1. **Parse URL.** Extract `owner` + `repo`. Derive output slug: `<owner>-<repo>` kebab-case (e.g. `anthropics-claude-code`). Output path: `brain/raw/<slug>.md`.

2. **Run repomix:**
   ```bash
   repomix --remote https://github.com/owner/repo \
     --output brain/raw/<slug>.md \
     --style markdown \
     --include "**/*.md,**/*.rst,**/*.txt,docs/**,README*,CHANGELOG*,LICENSE*"
   ```
   - Captures docs, changelogs, prose; excludes source code by default.
   - If user explicitly asks for full source code → drop `--include`.

3. **Verify output.**
   - Repomix errors or empty output → report error. If repomix not installed → tell user `npm install -g repomix` and stop.
   - Output >200 KB (~50K tokens) → warn user, show file size, ask whether to proceed or re-run w/ tighter `--include`.

4. **Continue standard Ingest** (steps 1–8 above). Read repomix output file as source.

5. **Frontmatter for source page:**
   ```yaml
   source_file: raw/<slug>.md
   source_url: https://github.com/owner/repo
   ```
   Always set both for GitHub ingests.

6. **Tags MUST include** `github`, `open-source`, and repo's primary language/domain (infer from content). Apply all standard tagging rules (Section 12).

7. **GitHub repo source pages MUST include these two extra sections** (insert between Summary and Key Points):

   ```markdown
   ## Tech Stack
   Bulleted list of languages, frameworks, databases, runtimes, and tools used. Be specific — include version hints where visible (e.g., Python 3.13, Bun, DuckDB). Cover: runtime language, key libraries, databases, deployment, and any AI/ML frameworks.

   ## Purpose
   One paragraph: what problem does this repo solve, who is it for, and what is the primary user action?
   ```

   Required b/c tech stack + purpose are most-searched fields when deciding adoption/reference.

---

### Ingest YouTube
Triggered when user provides YouTube URL (`https://www.youtube.com/watch?v=<id>`, `https://youtu.be/<id>`, or `https://www.youtube.com/live/<id>`) and asks to ingest.

Steps:

1. **Check required tools.** Verify `yt-dlp` + `whisper` installed:
   ```bash
   which yt-dlp && which whisper
   ```
   Missing → report + stop:
   - `yt-dlp` → "yt-dlp is required. Install with `pip install yt-dlp`."
   - `whisper` → "whisper is required. Install with `pip install openai-whisper`."

2. **Fetch metadata:**
   ```bash
   yt-dlp --dump-json "<url>"
   ```
   Extract: `title`, `channel`, `upload_date`, `duration_string`, `description`, `chapters` (if present). `upload_date` returns as `YYYYMMDD` (e.g. `20240315`) — reformat to `YYYY-MM-DD` (e.g. `2024-03-15`) before use.
   Derive output slug from title in lowercase kebab-case (e.g. "The Bitter Lesson" → `the-bitter-lesson`). Fall back to video ID if title >60 chars or non-ASCII.

3. **Download audio:**
   ```bash
   yt-dlp -x --audio-format mp3 -o "brain/raw/<slug>.mp3" "<url>"
   ```
   yt-dlp error (private, unavailable, etc.) → report + stop.

4. **Transcribe.** Run from repo root (dir containing `brain/`):
   ```bash
   whisper "brain/raw/<slug>.mp3" --output_dir /tmp/ --output_format txt
   ```
   Produces `/tmp/<slug>.txt`. Empty output → warn user, offer metadata-only or abort.

5. **Write raw file.** Read `/tmp/<slug>.txt` as transcript. Create `brain/raw/<slug>.md`:
   ```markdown
   ---
   title: <title>
   channel: <channel>
   upload_date: <YYYY-MM-DD>
   duration: <duration_string verbatim from yt-dlp>
   source_url: <url>
   ---

   ## Description
   <video description>

   ## Chapters
   <bulleted list if present, otherwise "none">

   ## Transcript
   <full contents of /tmp/<slug>.txt>
   ```

6. **Clean up intermediates.** Delete `brain/raw/<slug>.mp3` + `/tmp/<slug>.txt`.

7. **Size check.** `brain/raw/<slug>.md` >200 KB → warn user, show size, ask to proceed.

8. **Continue standard Ingest** (steps 1–8 above). Read `brain/raw/<slug>.md` as source.

9. **Frontmatter for source page:**
   ```yaml
   source_file: raw/<slug>.md
   source_url: <youtube-url>
   ```
   Always set both for YouTube ingests.

10. **Tags MUST include** `youtube`, channel name in lowercase kebab-case (e.g. `lex-fridman`), and content-type tag inferred from video: one of `talk`, `lecture`, `interview`, `tutorial`. Apply standard tagging rules (Section 12).

11. **YouTube source pages MUST include these two extra sections** (insert between Summary and Key Points):

    ```markdown
    ## Speaker / Channel
    Who is speaking and what channel published it. Include role/affiliation if known.

    ## Video Details
    - **Duration:** use `duration_string` verbatim from yt-dlp
    - **Published:** YYYY-MM-DD
    - **Chapters:** bulleted list if present, otherwise "none"
    ```

    Required b/c speaker identity + video context are most-searched fields when looking up a video source.

---

### Query
Triggered when user asks a question.

Steps:
1. Read `wiki/index.md` to find relevant pages.
2. Read those pages.
3. Synthesize answer w/ citations (link to wiki pages, not raw sources unless quoting).
4. Ask user if answer should be filed as analysis. If yes → create `wiki/analyses/<slug>.md`.
5. Append entry to `wiki/log.md`.

### Lint
Triggered when user says "lint" or "health check".

Check for:
- Pages mentioned but not yet created (broken links / missing pages).
- Contradictions between pages (flag, don't resolve without asking).
- Orphan pages (no inbound links from any other wiki page).
- Stale claims (page says X, newer source says not-X).
- Missing cross-references (two pages clearly related but not linked).
- Data gaps web search could fill.

Report as numbered list. Ask user which items to act on.

### Update
Triggered when user says "update [page]" or ingest touches existing page.

Steps:
1. Read existing page.
2. Integrate new info, preserving old content still accurate.
3. Mark superseded claims w/ note (e.g. ~~old claim~~ → new claim (updated YYYY-MM-DD)).
4. Update `index.md` summary if one-liner changed.
5. Append entry to `wiki/log.md`.

---

## 7. Cross-Reference Rules

- Every entity/concept first mentioned in a page → link: `[[entity-or-concept-name]]` or `[Name](../entities/slug.md)`.
- Source pages link to all entities/concepts they introduce or significantly discuss.
- Entity/concept pages link back to all source pages mentioning them.
- Don't create page for entity/concept mentioned only once in passing — link to source page instead.

---

## 8. overview.md

`wiki/overview.md` is evolving synthesis of everything in wiki. Should:
- State main thesis/purpose of wiki (1 paragraph).
- Summarize key themes + how they connect (bullets or short paragraphs).
- Note major open questions/tensions.
- Link to key entity, concept, analysis pages.

Update when new source significantly changes big picture. Not page-by-page summary — evolving essay.

---

## 9. Tone and Style

- Clear, declarative prose. No hedging ("it seems", "perhaps") unless genuinely uncertain — flag uncertainty explicitly.
- Be specific. Vague summaries degrade wiki. Precise claims w/ sources > fluffy generalizations.
- Short paragraphs + bullets > walls of text.
- Never hallucinate. Source doesn't say it → don't write it. Mark inferences explicitly.

---

## 10. Session Start

At session start:
1. Read this file (`AGENTS.md`).
2. Read `wiki/hot.md` — ≤500-word briefing on latest ingested content. Short-term memory primer: freshest topics most likely relevant.
3. Read `wiki/log.md` (last 5 entries) for recent context.
4. Read `wiki/index.md` for current wiki state.
5. Greet user w/ brief status: page count, last ingest date, what wiki is currently about.

---

## 11. Web Search

May use web search during ingest/query to fill gaps, verify facts, or find context. Always:
- Clearly label web-sourced info as such.
- Raw source file is authoritative; web search supplements, not replaces.
- Significant web-sourced info → note in relevant wiki page.

---

## 12. Tagging

Tags are primary axis for cross-cutting search/filtering. Be thorough — source page should have **10–20 tags** spanning every relevant dimension. Thin tagging degrades discoverability.

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

- All tags **lowercase kebab-case**: `ai-safety`, not `AI Safety` or `aiSafety`.
- Multi-line YAML list format for source pages (easier to read + edit):
  ```yaml
  tags: [
    domain-tag1, domain-tag2,
    content-type-tag,
    concept-tag1, concept-tag2
  ]
  ```
- Entity/concept/person pages have simpler tag sets (3–6 tags); full tagging effort concentrates on **source pages**.
- Don't repeat info already in title or frontmatter type as tag (e.g. don't tag `type: source` page w/ `source`).
- Prefer **specific** over generic: `adversarial-misalignment` > `alignment`; `us-china` > `geopolitics`.
- Ingesting new source → spend deliberate time on tags. Ask: "what would I type into a search bar in 6 months to want this source to surface?"

---

_Schema version: 1.3 — 2026-05-16_

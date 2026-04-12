---
title: Obsidian
type: entity
entity_type: product
tags: [tooling, markdown, knowledge-management]
---

## Overview

Obsidian is a local-first markdown note-taking application with a graph view, plugin ecosystem, and strong support for interlinked notes. In the LLM Wiki Pattern, Obsidian serves as the UI for browsing the wiki — the LLM writes files, the user reads and navigates them in Obsidian.

## Key Facts

- Local-first: all files are plain markdown on disk. No proprietary format — the wiki is just a folder of `.md` files.
- **Graph view:** visualizes connections between pages. Best tool for seeing the shape of the wiki — which pages are hubs, which are orphans.
- **Obsidian Web Clipper:** browser extension that converts web articles to markdown. Useful for getting sources into `raw/`.
- **Download attachments hotkey:** Settings → Files and links → set attachment folder to `raw/assets/`. Then bind "Download attachments for current file" to a hotkey (e.g. Ctrl+Shift+D) to download all linked images locally.
- **Marp plugin:** renders markdown files as slide decks. Useful for generating presentations from wiki content.
- **Dataview plugin:** runs SQL-like queries over page frontmatter. Useful if LLM adds YAML metadata (tags, dates, source counts) — can generate dynamic tables and lists.
- "Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase." — from the idea file.

## Appearances

- [LLM Wiki — Idea File](../sources/llm-wiki-idea-file.md) — recommended as the primary UI for the wiki pattern.

## Connections

- [LLM Wiki Pattern](../concepts/llm-wiki-pattern.md) — Obsidian is the recommended viewer/navigator for the wiki
- [qmd](qmd.md) — alternative/complement for search within the wiki at larger scale

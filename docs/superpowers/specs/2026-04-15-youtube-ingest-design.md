# YouTube Ingest — Design Spec

**Date:** 2026-04-15
**Status:** Approved

---

## Overview

Add a "Ingest YouTube" operation to `second-brain/CLAUDE.md`, modelled after the existing "Ingest GitHub Repo" operation. The user provides a YouTube URL; Claude runs `yt-dlp` + `whisper` locally, assembles a structured raw markdown file, and then executes the standard ingest pipeline end-to-end in a single invocation.

---

## Scope

- Both long-form content (talks, lectures, interviews) and short-form content (tutorials, explainers).
- Transcription via local Whisper CLI (not YouTube auto-captions, not OpenAI API).
- Audio download via `yt-dlp`.
- No new scripts or Python files — the operation is fully defined inside `second-brain/CLAUDE.md`.

---

## Trigger

User provides a YouTube URL in any of these forms:
- `https://www.youtube.com/watch?v=<id>`
- `https://youtu.be/<id>`
- `https://www.youtube.com/live/<id>`

...and says "ingest" or similar.

---

## Required CLI Tools

Claude checks for both tools before proceeding. If either is missing, report it and stop.

| Tool | Purpose | Install hint |
|------|---------|-------------|
| `yt-dlp` | Download audio + fetch metadata | `pip install yt-dlp` |
| `whisper` | Local transcription | `pip install openai-whisper` |

---

## Pipeline Steps

1. **Fetch metadata** — run:
   ```bash
   yt-dlp --dump-json "<url>"
   ```
   Extract: `title`, `channel`, `upload_date`, `duration_string`, `description`, `chapters` (if present). Derive slug from the title in lowercase kebab-case (e.g., "The Bitter Lesson" → `the-bitter-lesson`). Fall back to the video ID if the title is very long (>60 chars) or contains non-ASCII characters.

2. **Download audio** — run:
   ```bash
   yt-dlp -x --audio-format mp3 -o "brain/raw/<slug>.mp3" "<url>"
   ```

3. **Transcribe** — run:
   ```bash
   whisper "brain/raw/<slug>.mp3" --output_dir /tmp/ --output_format txt
   ```
   This produces `/tmp/<slug>.txt`.

4. **Write raw file** — create `brain/raw/<slug>.md` combining metadata and transcript:
   ```markdown
   ---
   title: <title>
   channel: <channel>
   upload_date: <YYYY-MM-DD>
   duration: <HH:MM or MM:SS>
   source_url: <url>
   ---

   ## Description
   <video description>

   ## Chapters
   <bulleted list if present, otherwise "none">

   ## Transcript
   <full whisper transcript>
   ```

5. **Clean up intermediates** — delete `brain/raw/<slug>.mp3` and `/tmp/<slug>.txt`.

6. **Continue with standard Ingest** (steps 1–8 of the Ingest operation). Read `brain/raw/<slug>.md` as the source.

---

## Source Page Format

YouTube source pages follow the standard source page schema with two **required extra sections** inserted between Summary and Key Points:

```markdown
## Speaker / Channel
Who is speaking and what channel published it. Include role/affiliation if known.

## Video Details
- **Duration:** HH:MM
- **Published:** YYYY-MM-DD
- **Chapters:** bulleted list if present, otherwise "none"
```

### Frontmatter

```yaml
source_file: raw/<slug>.md
source_url: <youtube-url>
```

Always set both fields.

### Required Tags

Tags **must include**:
- `youtube`
- The channel name in lowercase kebab-case (e.g., `lex-fridman`)
- Content-type tag: one of `talk`, `lecture`, `interview`, `tutorial` — inferred from content

Apply all standard tagging rules (Section 12 of CLAUDE.md): aim for 10–20 tags total.

---

## Error Handling

| Situation | Action |
|-----------|--------|
| `yt-dlp` not installed | Report: "yt-dlp is required. Install with `pip install yt-dlp`." Stop. |
| `whisper` not installed | Report: "whisper is required. Install with `pip install openai-whisper`." Stop. |
| Download fails (private/unavailable video) | Report the yt-dlp error. Stop. |
| Transcript file empty | Warn the user. Offer to proceed with metadata only or abort. |
| Raw file large (>200 KB) | Warn the user and show file size. Ask whether to proceed before continuing. |

---

## Out of Scope

- YouTube auto-captions (Whisper is always used)
- OpenAI Whisper API (local only)
- Playlist ingestion (single videos only)
- Whisper model selection (use default model; user can override via `--model` flag if they want)

---

## Implementation

This spec is implemented entirely by adding a new "Ingest YouTube" section to `second-brain/CLAUDE.md`, following the same structure as the "Ingest GitHub Repo" section.

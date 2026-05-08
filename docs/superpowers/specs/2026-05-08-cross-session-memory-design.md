# Cross-Session Memory — Design

**Status:** spec under review
**Owner:** Maxime Haegeman
**Track:** v0.2 β
**Related specs:** `2026-05-07-jarvis-architecture.md`, `2026-05-08-claude-llm-design.md`

## 1. Goal

Give JARVIS continuity across WebSocket sessions. Two user-visible behaviors:

- **Same-day resume.** Close the tab or lose network, reconnect within 30 minutes, the conversation picks up where it left off.
- **Long-term recall, on demand.** When the user explicitly invokes memory ("do you remember…", "did I mention…", "what do you know about my…"), JARVIS pulls in a richer context: durable user-stated facts, summaries of recent sessions, and a few verbatim past exchanges matching the query.

Memory is **opt-in per turn**. Default turns carry only a small "recent conversation summary" blob. Facts and the session digest are loaded only when the user's text matches a curated phrase list.

## 2. Non-goals

- Embeddings, vector store, or semantic retrieval. LIKE-based matching is sufficient given that the rich-context path is only entered on explicit triggers.
- A user-facing "forget" command. Manual SQL only for v1.
- Multi-user. Schema deliberately omits a `user_id`; adding one later is a single migration.
- Second-brain integration. That is a separate track that will share the LLM `extra_context` seam introduced here.
- Background janitor for sessions stranded by hard process crashes. Tolerated for v1.
- Prompt-cache breakpoints on the system-prompt prefix. The blob sits well under the 4 K Haiku cache threshold; revisited when it grows.

## 3. Today's state

`server/server/session.py`:

- `Session._history: list[dict[str, str]]` is in-memory only and resets on every WS connect.
- Cap is 20 turns, trimmed at the end of each turn.
- `LLM.stream(history, user_text)` carries no memory beyond the live `_history` buffer.

The architecture spec (`2026-05-07-jarvis-architecture.md`) and Claude LLM spec (`2026-05-08-claude-llm-design.md`) explicitly defer cross-session memory and note that "the LLM ABC will need a context-providing seam." This spec introduces that seam.

## 4. Architecture

A new package `server/server/memory/` with four modules. The rest of the server depends only on `MemoryStore` and `MemoryContext`; the summarizer and trigger detector are internals.

### 4.1 `store.py` — `MemoryStore`

Async wrapper around a single SQLite file. Driver: `aiosqlite`, journal mode WAL, foreign keys on. Owns all persistence. No LLM calls.

Public API:

```python
class MemoryStore:
    @classmethod
    async def open(cls, path: str) -> "MemoryStore": ...
    async def close(self) -> None: ...

    # session lifecycle
    async def start_session(self) -> str: ...
    async def end_session(self, session_id: str) -> None: ...
    async def find_resumable(self, within_minutes: int) -> str | None: ...
    async def load_session_turns(self, session_id: str, cap: int) -> list[Turn]: ...

    # per-turn writes
    async def append_turn(self, session_id: str, role: str, content: str) -> int: ...

    # default-context read / refresh
    async def get_recent_summary(self) -> str: ...
    async def get_recent_summary_meta(self) -> RecentSummaryMeta: ...
    async def write_recent_summary(self, summary: str, last_turn_id: int) -> None: ...
    async def turns_since(self, last_turn_id: int) -> int: ...

    # full-context reads (only when triggered)
    async def get_facts(self) -> dict[str, str]: ...
    async def list_recent_summaries(self, limit: int) -> list[SessionSummary]: ...
    async def search_turns(self, query: str, limit: int) -> list[Turn]: ...

    # consolidation writes
    async def write_session_summary(self, session_id: str, summary: str) -> None: ...
    async def upsert_facts(self, facts: list[Fact], source_session_id: str) -> None: ...
    async def evict_facts_to_cap(self, cap: int) -> None: ...
```

### 4.2 `summarizer.py` — `Summarizer`

Wraps `anthropic.AsyncAnthropic` pinned to **Haiku** (`claude-haiku-4-5-20251001`) regardless of which model handles the conversation. Three methods:

- `refresh_recent_summary(turns) -> str` — 1–2 sentences over the last ~20 turns. Used by the default-context path.
- `summarize_session(turns) -> str` — 1–2 sentences for an ended session. Written to `session_summaries`.
- `extract_facts(turns) -> list[Fact]` — JSON-mode call. Returns durable user-stated facts as `{key, value}` pairs. Empty list on parse failure (logged, not raised).

`Summarizer` is a `Protocol`; tests inject `FakeSummarizer` returning canned strings.

### 4.3 `triggers.py` — `is_memory_query`

Pure function, case-insensitive substring match against a curated phrase list. Phrase-level (not single-word) to avoid false positives like "I'll remember to call mom."

```python
_TRIGGER_PHRASES: tuple[str, ...] = (
    "do you remember", "did i mention", "did i tell you",
    "you said", "you mentioned", "you told me",
    "we discussed", "we covered", "we talked about", "did we discuss",
    "earlier you", "last time we", "last time you",
    "what do you know about", "what's my", "whats my", "what are my",
    "what did i", "what did we",
    "recall ", "remember when",
)

def is_memory_query(text: str) -> bool:
    s = text.lower()
    return any(p in s for p in _TRIGGER_PHRASES)
```

The list is a module constant, freely tweakable. Tests cover canonical phrasings plus documented false-positive landmines (see §7).

### 4.4 `context.py` — `MemoryContext`

Builds the `extra_context` string passed to the LLM each turn.

```python
class MemoryContext:
    @staticmethod
    async def default(store: MemoryStore) -> str: ...
    @staticmethod
    async def full(store: MemoryStore, user_text: str) -> str: ...
```

**Default blob** (always used):

```
Background (recent conversation summary):
<recent_summary text>
```

If `recent_summary` is empty, `default` returns `""` (no useless header).

**Full blob** (only when `is_memory_query` is true). Composed sections, each omitted when its source is empty:

```
Background (recent conversation summary):
<recent_summary>

What I know about you (from prior conversations):
- preferred_language: TypeScript
- current_project: JARVIS v0.2
  ...

Recent sessions (most recent first):
- 2026-05-07 14:22: <summary>
- 2026-05-06 09:11: <summary>
  ...

Possibly relevant past exchanges:
- [user, 2026-04-30] "I prefer to deploy on Fridays"
- [assistant, 2026-04-30] "Got it — I'll keep Friday in mind for releases."
  ...
```

Section caps enforced by `full`: facts ≤ 50, session summaries ≤ 10, search results ≤ 5. Total target: ~2 K tokens.

`search_turns` query for the verbatim section: lowercase the user's text, strip punctuation, split on whitespace, take the longest 2–3 tokens, build `LIKE %token%` filters joined with `OR`. Deliberately dumb. Adequate for the trigger-only path.

### 4.5 `LLM` ABC change

```python
class LLM(Protocol):
    def stream(
        self,
        history: list[dict[str, str]],
        user_text: str,
        *,
        extra_context: str = "",
    ) -> AsyncIterator[str]: ...
```

`ClaudeLLM.stream` concatenates `extra_context` to the system prompt, after `JARVIS_SYSTEM_PROMPT`, before the conversation:

```python
system_prompt = JARVIS_SYSTEM_PROMPT
if extra_context:
    system_prompt = f"{system_prompt}\n\n{extra_context}"
```

`MockLLM.stream` is updated to accept and ignore `extra_context` (default `""`). Call-sites in `tests/test_session.py` that don't pass `extra_context` keep working unchanged.

Memory does **not** go in `messages` (Anthropic's API allows only `user`/`assistant` roles there; synthesizing a fake turn would pollute the conversation).

## 5. Schema

Single SQLite file at `server/data/memory.db` (overridable via `JARVIS_MEMORY_DB`). The `data/` directory is created on first run and added to `.gitignore`.

```sql
CREATE TABLE sessions (
    session_id  TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,                              -- ISO-8601 UTC
    ended_at    TEXT                                         -- NULL while session is active
);

CREATE TABLE turns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(session_id),
    ts          TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content     TEXT NOT NULL
);
CREATE INDEX idx_turns_session ON turns(session_id, id);

CREATE TABLE session_summaries (
    session_id  TEXT PRIMARY KEY REFERENCES sessions(session_id),
    summary     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE facts (
    key                TEXT PRIMARY KEY,
    value              TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    source_session_id  TEXT REFERENCES sessions(session_id)
);

CREATE TABLE recent_summary (
    id              INTEGER PRIMARY KEY CHECK (id = 1),       -- single-row
    summary         TEXT NOT NULL,
    refreshed_at    TEXT NOT NULL,
    last_turn_id    INTEGER NOT NULL                          -- highest turns.id at refresh
);
```

## 6. Lifecycle

### 6.1 On WS connect

```
resumable = await store.find_resumable(within_minutes=30)
if resumable:
    self.session_id = resumable                  # adopt prior id; do NOT mark ended
    turns = await store.load_session_turns(resumable, cap=20)
    self._history = [{role, content} for t in turns]
else:
    self.session_id = await store.start_session()
    self._history = []
emit ServerMessage.ready(session_id=self.session_id)
```

Resume is silent at the protocol layer — same `ready` event. The client sees a non-empty history simply by virtue of the next turn.

### 6.2 Per-turn (inside `Session._do_llm_and_tts`)

```
1. user_text arrives (STT or TextIn).
2. self._history.append({"role": "user", "content": user_text})
3. await store.append_turn(session_id, "user", user_text)
4. extra = (await MemoryContext.full(store, user_text))
        if triggers.is_memory_query(user_text)
        else (await MemoryContext.default(store))
5. stream = self._llm.stream(self._history, user_text, extra_context=extra)
   ... existing fanout / sentence-split / TTS unchanged ...
6. After fanout completes, if assistant_buf is non-empty:
       self._history.append({"role": "assistant", "content": full_assistant})
       await store.append_turn(session_id, "assistant", full_assistant)
7. Trim self._history to history_cap (existing).
8. await maybe_refresh_recent_summary()
```

`maybe_refresh_recent_summary`:

```python
meta = await store.get_recent_summary_meta()
if (current_turn_id - meta.last_turn_id) >= REFRESH_TURNS:
    turns = last RECENT_WINDOW turns across sessions
    summary = await summarizer.refresh_recent_summary(turns)
    await store.write_recent_summary(summary, current_turn_id)
```

If the Haiku call fails: log, skip. The next turn retries. Stale summaries are tolerable; missing ones return `""` from `default`.

### 6.3 On WS graceful close (inside `Session.cleanup`)

After existing task cancellations:

```python
try:
    turns = await store.load_session_turns(self.session_id, cap=200)
    if len(turns) >= 2:
        summary = await summarizer.summarize_session(turns)
        await store.write_session_summary(self.session_id, summary)
        facts = await summarizer.extract_facts(turns)
        if facts:
            await store.upsert_facts(facts, source_session_id=self.session_id)
            await store.evict_facts_to_cap(FACTS_CAP)
    await store.end_session(self.session_id)
except Exception:
    log.exception("memory consolidation failed")
```

Synchronous in cleanup, not background. Adds ~1–2 s of teardown time (two Haiku round-trips) but happens during WS close so the user doesn't perceive it; avoids races against the asyncio loop shutdown.

### 6.4 Hard-crash behavior

If the process dies between turns, `sessions.ended_at` stays `NULL` and no `session_summaries` row is written. On next startup the resume window finds the most recent session with `ended_at IS NULL`; if it falls inside 30 minutes we resume into it (turns are persisted per-turn, so they're intact). Older orphans sit in the table, untouched. A janitor that summarizes stranded sessions later is **out of scope** for v1.

### 6.5 Concurrency

Single-user, single-machine assumption. If two WS connections race, they get distinct `session_id`s and proceed independently — each persists its own turns. `find_resumable` picks the most-recently-ended.

## 7. Triggers — true and false positives

Locked into tests so a future contributor doesn't naively expand `_TRIGGER_PHRASES` to bare `"remember"`.

**True positives** (must match):
- "Do you remember when we discussed the deploy?"
- "Did I mention the Friday rule?"
- "You said TypeScript was preferred."
- "What do you know about my project?"
- "What's my preferred language?"
- "Recall the last release notes."

**False positives we deliberately accept** (rare):
- "Do you remember to be polite" → True. Rare phrasing.
- "What's my plan for tomorrow" → True. `what's my` is genuinely a memory probe in most uses.

**False positives we deliberately exclude** (regression-locked):
- "I'll remember to call mom" → False (`remember` alone never triggers).
- "I recalled it later" → False (`recall ` requires trailing space).
- "Remember me to your mother" → False (no matching phrase).

## 8. Defaults and configuration

| Setting | Default | Env var |
|---|---|---|
| DB path | `server/data/memory.db` | `JARVIS_MEMORY_DB` |
| Resume window | 30 minutes | `JARVIS_MEMORY_RESUME_MIN` |
| Verbatim resume cap | 20 turns | `JARVIS_MEMORY_RESUME_CAP` |
| Recent-summary refresh cadence | every 5 turns | `JARVIS_MEMORY_REFRESH_TURNS` |
| Recent-summary content window | 20 turns | `JARVIS_MEMORY_RECENT_WINDOW` |
| Facts cap | 50 | `JARVIS_MEMORY_FACTS_CAP` |
| Session-summary digest in full blob | 10 sessions | `JARVIS_MEMORY_DIGEST_SESSIONS` |
| `search_turns` result cap | 5 | `JARVIS_MEMORY_SEARCH_CAP` |
| Summarization model | `claude-haiku-4-5-20251001` | `JARVIS_MEMORY_MODEL` |

**Disable switch:** `JARVIS_MEMORY=off` skips memory wiring entirely. `Session` runs in pure-in-RAM mode (today's behavior). Used for tests, debugging, and as a fast-revert lever.

## 9. Testing

The package is built around small, swappable seams. Most tests are unit tests with no network and no on-disk SQLite.

**Seams used by tests:**
- `Summarizer` is a `Protocol`; tests inject `FakeSummarizer`.
- `MemoryStore.open` accepts `:memory:` for fully isolated SQLite.
- `triggers.is_memory_query` is pure → table-driven tests.
- `MemoryContext` takes a `MemoryStore` instance; tests build one in `:memory:`, seed it, assert blob string.

**Test files:**

| File | What it covers |
|---|---|
| `tests/memory/test_triggers.py` | Phrase list — true positives and the documented false-positive landmines |
| `tests/memory/test_store.py` | Schema migrations, all CRUD methods, LRU fact eviction, resume-window math, idempotent `start_session` |
| `tests/memory/test_context.py` | Default blob shape, full blob with all-empty / partial / saturated inputs, section ordering, total-size guard |
| `tests/memory/test_summarizer.py` | Mocks `AsyncAnthropic.messages.create`; asserts Haiku model id, JSON-mode for `extract_facts`, tolerance for malformed JSON |
| `tests/memory/test_session_integration.py` | E2E with `:memory:` store + `FakeSummarizer` + `MockLLM`: resume flow, per-turn append, refresh cadence, consolidation on cleanup, crash-mid-session leaves turns intact |

`tests/test_session.py` (existing) must still pass unchanged. `Session.__init__` gains optional `memory: MemoryStore | None = None`; when `None`, the memory path is skipped and behavior matches today's.

**No tests against real Anthropic.** A separate manual smoke checklist (in the implementation plan) verifies real Haiku output during dev.

## 10. Security and privacy

- Memory is local only. SQLite file lives on the same machine as the server. No network egress beyond the existing Anthropic calls.
- Facts and summaries flow through Haiku (Anthropic). This is the same trust boundary as the conversation itself; no new exposure.
- The `data/` directory is gitignored. The DB file should never be committed.
- No secrets-in-prompt scanning is in scope. The user is responsible for not pasting credentials into the chat (same as today).

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| False-positive triggers bloat every prompt with the full blob | Phrase-level (not single-word) matching; documented landmine tests |
| False-negative triggers leave the user feeling JARVIS "forgot" | User can rephrase ("do you remember"); add phrase to list when observed |
| Haiku consolidation fails on cleanup | Wrapped in `try/except`, never blocks teardown; turns are already persisted |
| Hard crash strands a session | Resume window covers the common case; orphans are inert until a future janitor |
| Concurrent WS connections corrupt state | aiosqlite + WAL handles SQL concurrency; each connection has its own `session_id` |
| Facts table grows unbounded | LRU eviction at cap (50) on every consolidation |
| Memory blob exceeds budget | Per-section caps in `MemoryContext.full`; total target ~2 K tokens, well under Haiku's 4 K cache threshold |

## 12. Out of scope (deferred)

- Background janitor for stranded sessions
- FTS5 / embeddings for richer retrieval
- User-facing forget command (slash command or UI)
- Multi-user support (`user_id` column)
- Second-brain integration (separate track; will reuse the `extra_context` seam)
- Cache breakpoints on the system-prompt prefix (deferred to Claude LLM follow-up)

## 13. Acceptance criteria

A reviewer can verify the spec is satisfied by:

1. `pytest server/tests/memory/` passes.
2. `pytest server/tests/test_session.py` still passes (no regressions).
3. Setting `JARVIS_MEMORY=off`, the server behaves identically to today.
4. With memory on: connect, send 6+ turns, disconnect, reconnect within 30 min → next turn proceeds with prior `_history` populated (verified via WS frames).
5. With memory on: connect, send a memory-trigger phrase → the LLM call sees `extra_context` containing the full blob (verified via mocked LLM in integration test).
6. With memory on: a session of ≥2 turns leaves a row in `session_summaries` and any extracted facts in `facts` after `cleanup`.

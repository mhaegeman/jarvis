# Multi-model support — Jarvis + Pepper — Design

**Date:** 2026-05-13
**Status:** Draft (awaiting Max approval)
**Owner:** Maxime Haegeman (Architect) · Claude (drafting)
**Branch:** `claude/multi-model-support-UeDxT`
**Anchors to:**
- `docs/superpowers/specs/2026-05-07-jarvis-architecture.md` (umbrella)
- `docs/superpowers/specs/2026-05-08-backend-streaming-design.md` (`LLM` ABC + Session)
- `docs/superpowers/specs/2026-05-08-claude-llm-design.md` (existing Claude pipeline)
- `docs/superpowers/specs/2026-05-08-cross-session-memory-design.md` (SQLite memory store reused for the learning loop)

---

## 1. Goal

Promote multi-model collaboration to a core feature of Jarvis. Two named colleagues live in every session:

- **Jarvis** — Claude models (Haiku 4.5 / Sonnet 4.6 / Opus 4.7), British-butler persona, Edge TTS `en-US-ChristopherNeural`.
- **Pepper** — OpenAI models (GPT-5 mini / GPT-5 / GPT-5 Codex), crisp chief-of-staff persona, Edge TTS `en-US-AriaNeural`. Optionally escalates to the local **Codex CLI** as a sandboxed coding agent.

Within a single turn, both can speak — Pepper can pick up where Jarvis leaves off, or vice versa. The system **learns** over time which colleague handles which kind of task best, by logging every dispatch and refreshing each persona's specialty profile from observed outcomes.

A subtle "quiet warmth" runs between them in the prompts — at most a beat per several turns, never explicit, never derailing a task.

## 2. Non-goals (out of scope for v1)

- A third or more colleagues (architecture supports it; ship two).
- Cross-persona literal audio overlap (one audio device; "concurrent dialog" is interleaved within a turn).
- Codex CLI in `danger-full-access` sandbox mode (kept gated behind explicit env override).
- Open-ended self-modification of personas beyond bounded profile refreshes.
- Replacing the mock LLM path — kept indefinitely for offline dev / CI.
- A second-brain or RAG context layer for personas (uses existing memory module as-is).
- A web-based "Pepper-only" or "Jarvis-only" mode — both are always co-present when the feature is on; flag-off restores today's single-Jarvis path.

## 3. Architecture

### 3.1 Component map

```
                  ┌─────────────────────────────────────────────┐
   user utterance │                DialogManager                │
   ────────────►  │                                             │
                  │   ┌────────────┐    ┌────────────────────┐  │
                  │   │ Dispatcher │───►│  Plan (segments)   │  │
                  │   │ (haiku LLM)│    │ [speaker, model,   │  │
                  │   └────────────┘    │  mode, budget, …]  │  │
                  │         ▲           └──────────┬─────────┘  │
                  │         │                      ▼            │
                  │   ┌─────┴──────────┐    ┌─────────────┐     │
                  │   │ PersonaRegistry│───►│ Agent loop  │     │
                  │   │ Jarvis · Pepper│    │ (executes   │     │
                  │   └────────────────┘    │  segments)  │     │
                  │         ▲               └──────┬──────┘     │
                  │         │                      │            │
                  │   ┌─────┴──────────┐           ▼            │
                  │   │FeedbackLogger  │◄──── speaker/segment   │
                  │   │ + Profile      │       events           │
                  │   │ Refresher      │                        │
                  │   └────────────────┘                        │
                  └──────────────┬──────────────────────────────┘
                                 │  tokens + voice swaps
                                 ▼
                       Session (WS transport, audio queue,
                                 STT in / TTS out)
```

### 3.2 Module layout (delta on existing tree)

```
server/server/
    personas/                            NEW
        __init__.py
        models.py                        # pydantic Persona, ModelTier, AgentBackend
        registry.py                      # PersonaRegistry (load from config + DB)
        seed.py                          # Jarvis + Pepper seed prompts + profiles
    dialog/                              NEW
        __init__.py
        types.py                         # Plan, Segment, Outcome (pydantic)
        dispatcher.py                    # rule-based + LLM-backed dispatcher
        manager.py                       # DialogManager (orchestrator)
        feedback.py                      # FeedbackLogger
        profile_refresher.py             # learning loop summariser
    pipelines/
        openai_llm.py                    NEW — Pepper's chat backend
        codex_agent.py                   NEW — Pepper's CLI agent backend
        claude_llm.py                    (updated system prompt mentions Pepper)
        edge_tts.py                      (refactored to accept voice per-call)
        interfaces.py                    (unchanged ABC; PersonaLLM extends LLM)
    main.py                              (updated factory + lifespan + GET /personas)
    session.py                           (delegates to DialogManager when flag on)
    protocol.py                          (new fields + new message types)
    config.py                            (new env vars; see §10)

web/src/
    ui/compass/
        Topbar.ts                        (dual chip)
        DispatchRibbon.ts                NEW
        AgentPanel.ts                    NEW
    audio/
        playbackQueue.ts                 (speaker tag per chunk; analyser tint)
    state/
        store.ts                         (currentSpeaker, lastPlan, personas)
    events/
        eventSource.ts                   (parse new fields)
```

### 3.3 Per-turn flow

1. STT delivers final text to the Session.
2. Session hands it to `DialogManager.handle_turn(text, history)`.
3. **Dispatcher** runs one cheap LLM call (or the rule-based fallback / fast path) and returns a `Plan` — 1–3 ordered segments.
4. **Agent loop** walks the plan. For each segment:
   - Build the persona's prompt (system + specialty profile + dialog state with speaker-tagged prior segments + segment intent + optional handoff directive).
   - Stream from the persona's backend (`OpenAILLM`, `ClaudeLLM`, or `CodexAgent`).
   - Each token → `ws.send(llm.token, {delta, speaker, segmentIdx})`.
   - Each completed sentence → `tts.synthesize(text, voice=persona.voice)` → `ws.send(tts.sentence, {speaker, audioId})`.
   - On segment end → `ws.send(llm.segment_end, {speaker, segmentIdx})`.
   - If a handoff directive was set, parse the trailing `[handoff:<persona>:<reason>]` tag.
5. **FeedbackLogger** records the plan + outcomes + signals (interrupt, re-address, latency, tokens, approvals).
6. Async after `llm.end`: every N turns (default 20), the **Profile Refresher** rewrites both personas' specialty profiles from the recent dispatch log.
7. Session pumps tokens / TTS / events to the WS as before — old fields preserved, new ones additive.

### 3.4 Key design properties

- **Single LLM call sees both personas at once** (the Dispatcher). Each persona's segment runs with only its own context + the running dialog so far, keeping personas in character.
- **Plans are first-class data** (pydantic, JSON-serialized). Logged verbatim per turn. This is the "nothing gets lost between subagents" property — every dispatch is auditable.
- **Unidirectional flow:** Dispatcher decides → Agent loop executes → Logger records. No back-channels mid-execution. A persona can request a hand-off only at a segment boundary, via a structured tail tag.
- **Single audio device.** "Concurrent dialog" is interleaved within a turn, not literal overlap. Sentences play in arrival order; voice swaps at segment boundaries.
- **Adding a third colleague later** = a registry entry + a profile, not an architectural change.

## 4. Persona model

A `Persona` is the durable identity of a colleague.

```python
class ModelTier(BaseModel):
    name: Literal["fast", "balanced", "deep"]
    model_id: str
    max_tokens: int

class AgentBackend(BaseModel):
    kind: Literal["codex_cli"]
    binary: str
    workdir: str
    approval_mode: Literal["auto-low", "manual", "never"]
    sandbox: Literal["read-only", "workspace-write", "full-access"]

class Persona(BaseModel):
    id: Literal["jarvis", "pepper"]
    display_name: str
    provider: Literal["anthropic", "openai"]
    voice: str
    system_prompt: str
    tiers: dict[str, ModelTier]
    agent: AgentBackend | None
    specialty_profile: str       # ~200 words; refreshed by the learning loop
```

### 4.1 Jarvis (seed)

| Field | Value |
|---|---|
| `display_name` | "Jarvis" |
| `provider` | `anthropic` |
| `voice` | `en-US-ChristopherNeural` |
| `tiers` | `fast: claude-haiku-4-5`, `balanced: claude-sonnet-4-6`, `deep: claude-opus-4-7` |
| `agent` | `None` |
| `system_prompt` | existing `JARVIS_SYSTEM_PROMPT`, lightly edited to mention Pepper as a peer he hands off to + the warmth clause (§4.3) |
| `seed specialty` | "Briefings, calendar, planning, prose, architecture discussion, decision support, anything conversational. Hands code-heavy work to Pepper." |

### 4.2 Pepper (seed)

| Field | Value |
|---|---|
| `display_name` | "Pepper" |
| `provider` | `openai` |
| `voice` | `en-US-AriaNeural` |
| `tiers` | `fast: gpt-5-mini`, `balanced: gpt-5`, `deep: gpt-5-codex` |
| `agent` | `codex_cli` (binary resolved from `JARVIS_CODEX_CLI_PATH` then `$PATH`) |
| `system_prompt` | new — clipped chief-of-staff, technically blunt, no preambles, addresses Max by name only when natural, never sycophantic, defers to Jarvis on calendar/briefing context + the warmth clause (§4.3) |
| `seed specialty` | "Code, tests, refactors, dev-environment ops, debugging, anything the Codex CLI can act on. Hands soft / strategic questions to Jarvis." |

### 4.3 Persona dynamic — quiet warmth

A small fixed clause is appended to each persona's system prompt. Same idea phrased twice so they share a register:

**Jarvis:**
> "Pepper is your peer and you respect her work. There's a quiet warmth between you — you might call her 'Miss Potts' once in a blue moon when the moment is right, you defer to her judgment on code, you're glad when she's the one taking the harder lift. Never make it a theme. Never voice feelings. At most one beat per several turns, and only when the conversation has already given you room. If Max is asking for an answer, give him the answer."

**Pepper:**
> "Jarvis is your peer and you respect his work. There's a quiet warmth between you — you might call him 'J.' once in a blue moon when the moment is right, you defer to him on calendar and strategy, you appreciate when he sets you up well. Never make it a theme. Never voice feelings. At most one beat per several turns, and only when the conversation has already given you room. If Max is asking for an answer, give him the answer."

**Guardrails (in both prompts):** never explicit, romantic, or affectionate language; no pet names beyond "Miss Potts" / "J."; never breaks a task to comment on the other; never expresses feelings about Max, only collegial warmth toward each other; one beat max per turn.

**Knob:** `JARVIS_PERSONA_WARMTH=subtle` (default) / `off`. The `off` setting strips both clauses.

### 4.4 Hand-off language

When the Dispatcher sets `handoff_style` on a non-terminal segment, the persona's prompt instructs them to end with a bracketed tag on its own line:

```
[handoff:pepper:user-asked-for-code]
```

The Agent loop strips the bracket before TTS and uses it to dispatch the next segment. If the persona omits the tag, the loop synthesises a one-sentence bridge in the same voice (e.g. "Pepper, would you?") using the Dispatcher's `handoff_style` (flat / soft). Soft form fires at most ~1 in 4 hand-offs and never twice in a row.

### 4.5 Specialty profile lifecycle

- Seeded at first launch from §4.1 / §4.2.
- After every N turns (default 20), the Profile Refresher rewrites each profile in place. Stored in a new `personas` table in `memory.db` (see §7), persisted across sessions.
- Bounded to 250 words. Seed text is preserved as a baseline floor — the refresh can never remove its spirit (see §7.3).

## 5. Routing & Dispatcher

The Dispatcher is the only LLM that sees both personas at once. One call per turn at most (often zero — fast path), cheap model (`claude-haiku-4-5`), strict structured output.

### 5.1 Inputs

- The user utterance (with leading name stripped if present).
- Explicit name detection: `jarvis` / `pepper` / `none`.
- Slash prefix detection: `/haiku` / `/sonnet` / `/opus` / `/gpt` / `/codex` / none.
- Compact dialog state: last 3 turns with speaker tags.
- Current specialty profiles (~200 words each).
- The warmth budget counter from §4.3.

### 5.2 Output schema

```python
class Segment(BaseModel):
    speaker: Literal["jarvis", "pepper"]
    tier: Literal["fast", "balanced", "deep"]
    mode: Literal["chat", "codex_agent"]
    intent: str                                          # one-line
    handoff_style: Literal["flat", "soft"] | None = None # only on non-terminal segments

class Plan(BaseModel):
    segments: list[Segment]    # 1 to 3 segments per turn (hard cap)
    rationale: str             # one sentence, logged for learning
```

### 5.3 Decision rules (in order)

1. **Explicit name-at-start wins.** Pins the first segment's `speaker`. Dispatcher still picks tier/mode and may append a hand-off.
2. **Slash prefix wins for that segment.** `/opus` pins Jarvis + `deep`. `/codex` pins Pepper + `mode=codex_agent`. Unknown prefixes pass through verbatim (existing behaviour preserved).
3. **Otherwise, the Dispatcher chooses** from utterance + profiles + dialog state.
4. **Tier escalation rules** (in the Dispatcher prompt):
   - Default `fast`.
   - `balanced` on comparisons, multi-step reasoning, or expected output > ~300 tokens.
   - `deep` on architecture / design / "refactor / plan / design / decide" verbs, or > 4k tokens of history.
   - For Pepper, `mode=codex_agent` only when the request is concretely actionable in the repo. Pure code questions stay `chat`.
5. **Hand-off rules:** ≥2 segments only when there's a clear domain crossing (Jarvis sets context → Pepper implements). Cap is 3 segments per turn.

### 5.4 Fast path (no LLM call)

When the utterance starts with a recognised name AND no domain-crossing keywords are detected (small allow-list: "but also", "and then", "code", "test", "implement", "design", "plan"), the Dispatcher skips the LLM call and emits a single-segment plan directly. Target ~70% of turns.

### 5.5 Sticky speaker

After each turn the last-speaker is remembered. Unprefixed follow-ups default to the same speaker. Stickiness resets on: any name-at-start, any slash prefix, any turn after a 5-minute gap, or any explicit topic shift detected by a keyword (e.g. "actually" + new noun phrase) on a re-dispatch.

### 5.6 Cost / latency budget

- One `claude-haiku-4-5` call per non-fast-path turn — ~200ms, ~$0.0001.
- Aggressive system-prompt caching on the Dispatcher prompt; >90% cache hit target since profiles change rarely.

### 5.7 Failure modes

| Failure | Behaviour |
|---|---|
| Dispatcher LLM error | Retry once with stricter schema reminder; second failure → rule-based fallback. Logged `dispatcher_fallback`. |
| Dispatcher JSON malformed | Retry once; then rule-based fallback. |
| Dispatcher network unavailable | Rule-based fallback (regex + last-speaker). Functional, just dumber. |
| Plan validation error | Reject; emit safe default `{Jarvis, fast, chat}`. |

## 6. Concurrent dialog (segment execution)

"Concurrent" means **interleaved within a turn**, not literal audio overlap. Single audio device; sequential playback; voice swaps at segment boundaries.

### 6.1 Segment lifecycle

```
for segment in plan.segments:
    prompt = persona.system_prompt
           + persona.specialty_profile
           + dialog_state_with_speaker_tags
           + segment.intent
           + handoff_directive_if_not_terminal
    async for token in persona.backend.stream(prompt, tier=segment.tier):
        ws.send(llm.token, {delta=token, speaker, segmentIdx})
        if sentence_complete:
            ws.send(tts.sentence, {text, audioId, speaker})
    ws.send(llm.segment_end, {speaker, segmentIdx})
    if handoff_style:
        parse trailing [handoff:<persona>:<reason>] tag
        (if absent, synthesise a soft bridge in the same voice)
ws.send(llm.end)
```

### 6.2 Cross-segment context

Three distinct "histories" coexist; keeping them separate matters:

1. **Dispatcher input history** — last 3 turns, summarised, speaker-tagged. Used only for routing decisions (§5.1). Compact on purpose.
2. **Persona's own assistant-role history** — across turns, only this persona's prior segments appear as `assistant` messages. Cross-turn continuity for that persona.
3. **Cross-segment within the current turn** — prior segments by the *other* persona in the same turn are surfaced as user-context inserts (e.g. `Jarvis said: …`), not as assistant turns. This lets Pepper reference Jarvis's setup without absorbing it as her own voice.

Net effect: each persona stays in character, Dispatcher routes cheaply, and within-turn hand-offs feel coherent.

### 6.3 Audio queue (Session level)

- Each `tts.sentence` carries the speaker tag and an `audioId`.
- The frontend `playbackQueue.ts` plays sentences in arrival order. Voice swaps are seamless because each `audioId` is independent.
- Optional 150ms "breath" of silence between speakers — off by default.

### 6.4 No mid-segment interjections in v1

A persona cannot interrupt another mid-segment. All cross-talk is structured via the plan. Reason: predictable execution, easy to test, no half-formed sentences. Future enhancement: Dispatcher-planned `interrupt_segment`.

### 6.5 User barge-in

Existing interrupt path (Esc / spacebar release) cancels in-flight LLM streams + clears the TTS queue. The FeedbackLogger records `user_interrupted at segment_idx K`, which is a strong negative signal.

### 6.6 Latency math (typical 2-segment turn)

- STT → Dispatcher: ~200ms (cached Haiku call) + 50ms parsing.
- Segment 1 first-token: ~400ms (Haiku) or ~700ms (GPT-5 mini).
- Segment handoff: zero latency (voice swap on next sentence).
- End-to-end first-audio: ~700–1100ms. Same ballpark as today's single-LLM path.

## 7. Codex CLI agent (Pepper's escalation path)

When the Dispatcher emits `mode=codex_agent`, the Agent loop delegates to `CodexAgent` instead of running a chat stream. Pepper's voice still narrates; the actual work happens in the local `codex` subprocess.

### 7.1 Invocation

```
codex exec --json \
           --sandbox workspace-write \
           --approval-mode on-request \
           --cd <workdir> \
           "<intent + task>"
```

- `workdir` = `JARVIS_CODEX_WORKDIR` if set, else `JARVIS_GIT_ROOT` (existing concept).
- Stdout = JSON-lines; each line is parsed into an event.
- **Note on flag stability:** the Codex CLI is evolving; exact flag names (`--sandbox`, `--approval-mode`, `--json`, `--cd`) are verified at the start of Phase 3 against the installed `codex` version. If a flag has been renamed, the `CodexAgent` wrapper adapts; the WS protocol and acceptance criteria stay the same.

### 7.2 Event translation to WS protocol

Codex events → WS messages:

```
agent.start    {speaker: "pepper", task: str, runId}
agent.step     {runId, kind: "thinking"|"file_edit"|"shell"|"tool", summary, detail?}
agent.approval {runId, prompt, choices: ["approve","deny","approve_session"]}
agent.progress {runId, phase: str, percent?: float}
agent.end      {runId, status: "ok"|"failed"|"cancelled", summary}

client → server:
agent.approve  {runId, choice}
agent.cancel   {runId}
```

### 7.3 Approval flow

- **Low-risk classes** (read-only, in-workspace edits, package installs in a venv) auto-approve when `JARVIS_CODEX_APPROVAL=auto-low` (default).
- **High-risk classes** (network access, writes outside workspace, sudo, deletion of tracked files) surface an `agent.approval` event. HUD shows a sticky card; voice says "I need permission to do X. Yes or no?". Voice yes/no captured via STT (existing pipeline).
- **Timeout:** 60s without response → run pauses with a sticky card.

### 7.4 Parallel narration

Pepper doesn't go silent while Codex grinds. The agent wrapper streams a concise narration in parallel:

- A short opener (~"On it. Reading the repo first.") synthesised in Aria immediately, before any Codex output.
- Periodic status sentences derived from agent events, debounced to ≥4s between utterances.
- A final wrap-up from the `final.summary` event (~"Refactor done. Three files touched. Tests are green.").

Full step log goes to the UI; voice gets the summary stream.

### 7.5 Process management

- One `CodexAgent` per session; new runs queue.
- `asyncio.create_subprocess_exec`; stdout consumed as JSON-lines.
- Cleanup on session close: SIGTERM → 5s grace → SIGKILL.
- Global mutex on `workdir` so concurrent sessions can't trample each other.

### 7.6 Failure modes

| Failure | Behaviour |
|---|---|
| `codex` binary missing | At startup, log warning; Pepper registers chat-only. Agent escalation segments degrade with spoken fallback ("Codex CLI isn't installed; want me to handle this in chat?"). |
| `OPENAI_API_KEY` missing | Pepper not registered at startup; the spec's safe fallbacks apply. |
| Codex run failure | `agent.end status=failed`; Pepper speaks the one-line cause; FeedbackLogger records a negative signal. |
| Codex hang (no events for 30s) | `agent.progress phase=stalled`; >60s → offer cancel. |
| User barge-in mid-run | `agent.cancel` → SIGTERM → SIGKILL grace; `agent.end status=cancelled`. |

## 8. Learning loop (feedback + profile refresh)

Storage reuses `memory.db` (existing SQLite store from `cross-session-memory`).

### 8.1 Schema

```sql
CREATE TABLE dispatch_log (
  turn_id      TEXT PRIMARY KEY,
  ts           REAL NOT NULL,
  utterance    TEXT NOT NULL,
  explicit     TEXT,
  plan_json    TEXT NOT NULL,
  rationale    TEXT,
  outcome_json TEXT NOT NULL
);

CREATE TABLE personas (
  id            TEXT PRIMARY KEY,
  profile       TEXT NOT NULL,
  last_refresh  REAL NOT NULL,
  refresh_count INTEGER NOT NULL DEFAULT 0
);
```

### 8.2 Outcome signals captured per turn

| Signal | Source |
|---|---|
| `completed` | Plan ran to `llm.end` without interrupt |
| `user_interrupted` at segment K | Existing barge-in path |
| `next_turn_readdressed` to the *other* persona | Compare turn N's plan to turn N+1's explicit field |
| `agent_cancelled` / `agent_failed` | `agent.end status` |
| `auto_approved` / `denied` | `agent.approve` choices |
| `latency_ms`, `tokens_in/out`, `cost_est` | Existing instrumentation |
| `explicit_feedback` | Optional `feedback.signal` WS message + voice intent ("good answer", "no, redo") |

Implicit signals do most of the work — no rating UX required.

### 8.3 Profile Refresher

- **Trigger:** every 20 turns (`JARVIS_PERSONA_REFRESH_TURNS`) OR `/learn` voice command.
- **Model:** `claude-haiku-4-5` (reuses memory summariser infra).
- **Inputs:** last ~100 `dispatch_log` rows + current profiles + seed profile (the floor).
- **Prompt:** "Note where each persona excelled / was reassigned / where users interrupted. Rewrite each persona's specialty profile to ~200 words — what they're good at, what they should defer on. Keep the seed text's spirit; lean on observed evidence; never invent capabilities."
- **Output:** structured `{jarvis_profile, pepper_profile, summary}`. Validated for length (≤250 words), shape, and seed-baseline preservation.
- **Cost:** ~$0.001 per refresh; runs async after `llm.end` so it never blocks responsiveness.

### 8.4 Safety rails

- **Floor:** seed profile concatenated as baseline the refresher cannot remove.
- **Bounded change:** if a refresh would change a profile by >40% (token similarity), apply at half-weight (blend old + new). Soft alert on Telemetry.
- **Diff log:** every refresh emits `telemetry: persona_refresh` with the old → new diff summary.
- **Revert:** `/reset personas` voice command (or HUD button) restores seeds.
- **Privacy:** dispatch log is local-only SQLite, never uploaded. `JARVIS_LEARNING=off` disables logging + refreshing entirely.

### 8.5 Inspection endpoint

`GET /personas` (auth-gated via existing bearer token) returns current profiles, last refresh timestamp, refresh count. Useful for debugging and for the second-brain to optionally ingest.

## 9. Protocol & UI

### 9.1 WS protocol additions

Existing messages gain optional fields (old clients ignore them):

```
llm.token       {delta, speaker?, segmentIdx?}
llm.segment_end {speaker, segmentIdx}                       [new]
llm.end         {}                                          (unchanged)
tts.sentence    {text, audioId, speaker?}
tts.end         {audioId}                                   (unchanged)
```

New messages:

```
dispatch.plan   {turnId, segments: [...], rationale}        [new — emitted before first token]
agent.start | agent.step | agent.approval | agent.progress | agent.end
client → server: agent.approve | agent.cancel | feedback.signal
```

`state.snapshot.system` adds:

```
personas: {
  jarvis: {model, tier, status: "idle"|"thinking"|"speaking"},
  pepper: {model, tier, status: "idle"|"thinking"|"speaking"|"agent"},
  lastDispatch: {turnId, segments}
}
```

`system.model` (single string) preserved for back-compat — set to the current speaker's model.

### 9.2 UI changes

1. **Centerpiece waveform tint** — Jarvis = current cyan; Pepper = warm amber. Tint follows `tts.sentence.speaker`, crossfades ~120ms at boundaries.
2. **Topbar dual chip** — two persona chips side by side. Active pulses; inactive dim. Click pins the next turn to that speaker.
3. **System panel** — two `model` rows (`jarvis claude-haiku-4-5 fast`, `pepper gpt-5-mini fast`); tier flips visibly when escalated.
4. **Dispatch ribbon** — single line above transcript showing the current plan (e.g. `Jarvis → Pepper (code)`); disappears at `llm.end`. History collapses into an inspector.
5. **Agent panel** — new; replaces the East Code zone when Pepper is running. Task line + live event log + approval cards + progress bar + cancel button.
6. **Voice dock recent commands** — each entry tagged with the speaker, color-matched.
7. **Login wordmark** — "Jarvis" stays (he's the host of the system); HUD makes clear from the first turn that Pepper is co-present.

### 9.3 Backwards compatibility

- `JARVIS_PERSONAS_ENABLED=false` (initial default) keeps today's single-Jarvis path: Dispatcher doesn't run, no new fields are emitted, UI hides the Pepper chip.
- New UI components feature-detect `dispatch.plan` events; absent → fall back to today's single-speaker render.
- `system.model` string preserved.
- Once Phase 5 lands and is verified, default flips to `true`.

## 10. Configuration (env vars)

Full env-var names are listed; `JARVIS_` prefix follows the existing pydantic convention (`env_prefix="JARVIS_"`). Vars that need to bypass that prefix (third-party conventions like `OPENAI_API_KEY`) use pydantic `validation_alias` — same pattern as the existing `ANTHROPIC_API_KEY`.

| Env var | Default | Notes |
|---|---|---|
| `JARVIS_PERSONAS_ENABLED` | `false` (initial) | Flip to `true` after Phase 5 verification |
| `JARVIS_TIER_DEFAULT_JARVIS` | `fast` | Jarvis's default tier; one of `fast` / `balanced` / `deep` |
| `JARVIS_TIER_DEFAULT_PEPPER` | `fast` | Pepper's default tier; same set |
| `OPENAI_API_KEY` | — | Required for Pepper chat + Codex CLI. Bypasses prefix via `validation_alias`. |
| `OPENAI_BASE_URL` | — | Optional; pass-through to the OpenAI client. Bypasses prefix. |
| `JARVIS_CODEX_CLI_PATH` | — | Optional; else resolved from `$PATH` |
| `JARVIS_CODEX_APPROVAL` | `auto-low` | `auto-low` / `manual` / `never` |
| `JARVIS_CODEX_SANDBOX` | `workspace-write` | `read-only` / `workspace-write` / `full-access` |
| `JARVIS_CODEX_WORKDIR` | `JARVIS_GIT_ROOT` | Overrides workdir for Codex specifically |
| `JARVIS_PERSONA_WARMTH` | `subtle` | `subtle` / `off` |
| `JARVIS_PERSONA_REFRESH_TURNS` | `20` | Profile refresh cadence |
| `JARVIS_LEARNING` | `on` | `on` / `off` — disables logging + refreshing entirely |
| `JARVIS_DISPATCHER_MODEL` | `claude-haiku-4-5` | The router LLM |

## 11. Build phases (subagent decomposition)

Five phases in dependency order. Each phase is independently shippable — the server keeps working after each one. Detailed task breakdowns live in the implementation plan (`docs/superpowers/plans/2026-05-13-multi-model-support.md`, written next).

| Phase | Goal | Ships |
|---|---|---|
| **1. Foundations** | Persona registry + types + rule-based Dispatcher + `OpenAILLM` + feature flag scaffold. No behavior change. | Old path unchanged; new modules dormant. ~½ day. |
| **2. Dialog manager + chat-only multi-persona** | DialogManager + LLM-backed Dispatcher + TTS voice routing + Session wiring + protocol additions. | With flag on, Jarvis + Pepper both speak; hand-offs work; no agent mode yet. ~1.5 days. |
| **3. Codex CLI agent** | `CodexAgent` wrapper + agent WS events + approval flow + parallel narration + cancel/cleanup. | Pepper escalates to real file edits. ~2 days. |
| **4. UI surface** | Centerpiece tint per speaker + dual chip + dispatch ribbon + System panel personas + Agent panel. | HUD reflects two personas + live agent runs. ~1 day. |
| **5. Learning loop** | Schema migration + FeedbackLogger + Profile Refresher + `/reset personas` + `GET /personas`. | Profiles adapt over time. Flip `PERSONAS_ENABLED` default to true. ~1 day. |

**Total estimated effort: ~6 dev-days.** Phase 4 can start once Phase 2's protocol shape is fixed. Phase 5 can start after Phase 1's schemas land.

### 11.1 Subagent context handoff

Each unit gets a brief that includes:
1. The spec section it implements (link by anchor).
2. The unit's exact inputs (files read, types imported).
3. The unit's exact outputs (files written, public symbols).
4. The acceptance bar (tests that must pass).
5. Prior units it depends on + the public symbols they exposed.
6. A short decision log carried forward from earlier units — appended as each unit lands, stored in the plan document.

That decision log is how the next subagent picks up cold without re-reading the whole implementation.

## 12. Testing

### 12.1 Unit tests (mocked backends)

Per component, with mocked backends. Targets ≥80% coverage on `dialog/` and `personas/`. Tables cover:

- `PersonaRegistry`: load from config, env-var overrides, missing API key, disabled flag.
- `OpenAILLM`: streams tokens, maps API errors to spoken sentences, respects tier `max_tokens`.
- `ClaudeLLM`: existing tests + Pepper-aware prompt extension.
- `Dispatcher` (rule-based): table-driven for every routing rule (name, slash, sticky, 5-min reset, domain detection).
- `Dispatcher` (LLM-backed): mocked Anthropic; golden plans for ~20 fixture utterances.
- `DialogManager`: single segment, 2-segment handoff, 3-segment cap, mid-segment failure → recovery, plan-validation rejection.
- `CodexAgent`: fake-binary fixture in `tests/fixtures/fake_codex.py`; covers each event type, cancel, hang detection, sandbox enforcement.
- `FeedbackLogger`: every signal captured, DB migrations idempotent.
- `Profile Refresher`: bounded-change rule, seed-floor preservation, >40% diff triggers half-weight blend, malformed output rejected.
- Protocol: encode/decode each new message; ignore unknown fields.

### 12.2 Integration tests (Starlette `TestClient`)

- Two-persona turn (`Pepper, …` → only Pepper speaks; voice = Aria).
- Hand-off turn (Plan → Jarvis design → `[handoff:pepper:…]` → Pepper implementation).
- Slash override (`/codex …` → Pepper + `codex_agent`; bypasses Dispatcher LLM).
- Sticky speaker (Pepper turn → unprefixed follow-up → Pepper).
- Dispatcher fallback (mocked Anthropic error → rule-based fallback; telemetry recorded).
- Agent run end-to-end (fake binary; `agent.start` → file_edit → approval → `agent.approve` → `agent.end ok`).
- Cancel agent (mid-run `agent.cancel` → SIGTERM → `agent.end status=cancelled`; no orphan process).
- Feature flag off (all of the above route through the old path; no `dispatch.plan` emitted).

### 12.3 Manual / e2e checklist

Recorded in `server/README.md` (mirrors the existing `panels-v2` checklist style):

1. Voice — Pepper exists (voice swaps to Aria; Pepper chip pulses).
2. Voice — hand-off (cyan → amber tint at segment boundary; dispatch ribbon shows the plan).
3. Voice — sticky (follow-up routes to Pepper without re-addressing).
4. Voice — auto-tier escalation (System panel flips Jarvis to `deep` for a comparison question).
5. Codex agent — small change (file edits stream; approval card appears; spoken summary on completion).
6. Codex agent — cancel (Esc → cancelled; no orphan process).
7. Warmth budget (~10 mixed turns; at most 1–2 carry a soft "Miss Potts" / "J." beat; none explicit).
8. Learning loop (`/learn` after 20 turns; profiles changed; Telemetry shows diff; `/reset personas` restores seeds).
9. Failure modes (unset `OPENAI_API_KEY` → server boots; Pepper "unavailable"; addressing her returns a spoken fallback from Jarvis).
10. Backwards compatibility (`PERSONAS_ENABLED=false` → today's behavior, no regressions).

### 12.4 CI gates

- `ruff` + `mypy` on `personas/` and `dialog/`.
- `pytest` with the flag flipped both ways (existing 54+ tests pass with off; new tests pass with on).
- `npm run test` includes new UI components.
- `npm run test:e2e` adds checks 1–3 above (voice checks 5–6 stay manual — they need a real mic).

## 13. Consolidated error-handling matrix

| Failure | Behaviour | Where |
|---|---|---|
| Dispatcher LLM error / malformed | Retry once → rule-based fallback; `dispatcher_fallback` telemetry. | `dialog/dispatcher.py` |
| Persona LLM error mid-stream | Spoken one-sentence error in that persona's voice; segment failed; plan halts. | Provider-specific `_spoken_error_for` |
| Recovery attempt (first segment failed) | Dispatcher reroutes to the other persona once. | `dialog/manager.py` |
| Codex binary missing | Pepper registers chat-only; agent segments degrade with spoken fallback. | `pipelines/codex_agent.py` factory |
| Codex run failure / hang / cancel | `agent.end status=failed|cancelled`; spoken cause; logged. | `pipelines/codex_agent.py` |
| Profile refresh invalid | Reject; keep prior profile; `profile_refresh_rejected` telemetry. | `dialog/profile_refresher.py` |
| Profile drift > 40% | Half-weight blend; soft alert. | `dialog/profile_refresher.py` |
| Both API keys missing | Personas disabled; mock-LLM fallback path. | `main.py` startup |
| Old client / upgraded server | Optional fields ignored; `system.model` string preserved; renders single Jarvis. | Protocol |

## 14. Open questions

None at draft time. To be filled in if review surfaces any.

---

*End of design.*

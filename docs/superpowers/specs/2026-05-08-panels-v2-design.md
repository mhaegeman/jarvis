# Panels v2 — Design

**Date:** 2026-05-08
**Status:** Approved (orchestrator, per Architect delegation; user approved 2026-05-08)
**Owner:** Maxime Haegeman (Architect) · Orchestrator (drafting)
**Anchors to:** `docs/superpowers/specs/2026-05-07-jarvis-architecture.md` (umbrella)
**Sister specs:** spec-01 / spec-02 / spec-03 / spec-04 — all merged to `main`

---

## 1. Goal

Replace placeholder data on the nine HUD panels with real, live information. Land it as one umbrella v2 effort coordinated by the orchestrator with per-panel subagent dispatch in Phase C.

| Panel | Today | v2 |
|---|---|---|
| Header | clock + uptime | + WS connection state badge |
| Centerpiece | analyser-driven waveform | unchanged (already real) |
| System | uptime real, rest fake | real load (`psutil`), tokens/min (rolling 60 s), session id, model name |
| Memory | all fake | real context-used (token count) vs context-max (model window) |
| Calendar | hard-coded | today's entries from Google Calendar; refresh on user-triggered Sync only (no automatic polling) |
| Network | all fake | endpoint, RTT (heartbeat ping/pong), packet count, server queue depth |
| Tasks | all fake | counts from server-side queue (second-brain ingestion + scheduled prompts) |
| Telemetry | real | unchanged |
| Audio | output fake | output dB from playback `AnalyserNode` RMS |

## 2. Non-goals

- New panels or HUD layout changes
- Multiple Google calendars (primary only)
- Calendar event creation / edit
- Persistent task queue across server restart (in-memory only)
- Real LLM token counts (mock pipelines emit stable values; spec-02 Phase 2 brings real numbers)
- Auth on calendar sync beyond Google's OAuth desktop flow

## 3. Inputs from prior specs

| From | Contract |
|---|---|
| spec-01 | Panel classes (`Component<State>` + `render(state)`); store slice pattern in `web/src/state/store.ts` |
| spec-02 | Server protocol module (`ServerMessage` factory in `server/server/protocol.py`); 5 s telemetry heartbeat; per-session orchestrator at `server/server/session.py` |
| spec-03 | `WSEventSource` JSON dispatch; `EventMap` typed events; centerpiece waveform driven by playback `AnalyserNode` |
| spec-04 | systemd `--user` unit at `~/.config/systemd/user/jarvis-backend.service`; `STATICRYPT_PASSWORD` repo secret; `~/.config/jarvis/` exists for backend secrets (introduced here for OAuth tokens) |

## 4. Architecture overview

```
┌── server/server/ ─────────────────────────────────────────────┐
│  state.py            periodic state.snapshot every 1s          │
│   ├── samples psutil.cpu_percent → system.load                 │
│   ├── reads tasks.py counts → tasks                            │
│   ├── reads heartbeat.last_rtt_ms → network                    │
│   ├── reads session history token tally → memory               │
│   └── packs into ServerMessage.state_snapshot(...)             │
│                                                                │
│  tasks.py            in-memory queue (queued/active/done)      │
│   └── consumed by ingestor + scheduler hooks (placeholders)    │
│                                                                │
│  calendar_client.py  Google Calendar API + OAuth desktop flow  │
│   ├── refresh token at ~/.config/jarvis/google-token.json      │
│   └── emits calendar.update on connect + every 30 min          │
│                                                                │
│  heartbeat.py        ping/pong (replaces 5s telemetry "heart") │
│   └── records rtt_ms, exposed via state.network.latencyMs      │
└────────────────────────────────────────────────────────────────┘

┌── web/src/ ───────────────────────────────────────────────────┐
│  events/wsEventSource.ts  decode state.snapshot, calendar.update│
│                            (and pong→ping echo for RTT)         │
│  state/store.ts            new slice: panelData                  │
│  ui/panels/*               render reads from panelData          │
└────────────────────────────────────────────────────────────────┘
```

## 5. Server-side additions

### 5.1 Protocol additions

Two new server message types (factory methods in `ServerMessage`):

```python
@staticmethod
def state_snapshot(
    *,
    system: dict,    # {load, tokensPerMin, sessionId, modelName}
    memory: dict,    # {contextUsed, contextMax}
    network: dict,   # {endpoint, latencyMs, packets, sendQueueDepth, sendQueueMax}
    tasks: dict,     # {queued, active, done}
) -> dict[str, Any]: ...

@staticmethod
def calendar_update(*, entries: list[dict]) -> dict[str, Any]:
    # entries[i] = {time: "HH:MM", title: str, durationMin: int}
    ...

@staticmethod
def ping(seq: int) -> dict[str, Any]: ...
```

One new client message type (`Pong` in `decode_client`):

```python
class Pong(_Base):
    type: Literal["pong"]
    seq: int
```

`Hello.clientVersion` payload extended (optional, backward compatible) — server returns `sessionId` in the `ready` event:

```python
@staticmethod
def ready(*, session_id: str | None = None) -> dict[str, Any]: ...
```

### 5.2 `state.py` periodic emitter

Owned by `Session`. Runs as a background task started in `Session.run()`. Cadence: 1 s. Reads from:
- `psutil.cpu_percent(interval=None)` for `system.load` (process-wide)
- `len(self._send_q._queue)` and `self._send_q.maxsize` for `network.sendQueueDepth/Max`
- `self._packet_counter` (incremented on each `_send_q.put`) for `network.packets`
- `self._token_counter` rolling 60-second window for `system.tokensPerMin`
- `self._token_budget_used` per-turn snapshot for `memory.contextUsed`
- `config.MODEL_CONTEXT_MAX` (new, default 200000) for `memory.contextMax`
- `tasks.snapshot()` for `tasks`
- `heartbeat.last_rtt_ms` (or `null` if no pong received yet)

Emits via existing `_enqueue_json(ServerMessage.state_snapshot(...))`. When the snapshot would exceed send-queue capacity, it's dropped silently — telemetry beats it.

### 5.3 `tasks.py`

```python
class TasksQueue:
    def __init__(self) -> None: ...
    def enqueue(self, name: str) -> str: ...   # returns task_id
    def start(self, task_id: str) -> None: ...
    def finish(self, task_id: str) -> None: ...
    def snapshot(self) -> dict[str, int]:
        return {"queued": ..., "active": ..., "done": ...}
```

Module-level singleton `tasks_queue: TasksQueue`. Hooks reserved for the second-brain ingestor and scheduled-prompt runner — those modules don't exist yet; the tests use `tasks_queue` directly. Done counter is monotonic (no eviction in v2).

### 5.4 `calendar_client.py`

Google Calendar API via `google-auth`, `google-auth-oauthlib`, `google-api-python-client`. OAuth desktop flow:
- First run: opens browser; user grants `https://www.googleapis.com/auth/calendar.readonly`
- Refresh token persisted at `~/.config/jarvis/google-token.json` (mode 0600)
- Credentials at `~/.config/jarvis/credentials.json` (Maxime downloads from Google Cloud Console)

Public API:

```python
class CalendarClient:
    def __init__(self, credentials_path: Path, token_path: Path) -> None: ...
    async def fetch_today(self) -> list[dict]:
        # returns [{time: "HH:MM", title: str, durationMin: int}, ...]
        # sorted by start time; events without a start time are filtered out
        ...
```

**Manual-sync only** (Architect direction, 2026-05-08): the calendar is fetched on demand, not on a timer. On `Session.run()` the server emits one `calendar.update` with `entries: []` (empty placeholder). The client sends `{type: "calendar.sync"}` when the user clicks the Sync button on the Calendar panel; the server fetches and emits a fresh `calendar.update`. Concurrent syncs coalesce. If credentials are missing, the fetch returns `[]` and the server emits an `error` event so the panel can surface it; otherwise the sync is silent on success beyond the `calendar.update`.

### 5.5 Heartbeat refactor

Replace the existing `_heartbeat_loop` (which sends a `telemetry: heartbeat`) with a ping/pong:

```python
async def _heartbeat_loop(self) -> None:
    seq = 0
    while not self._closing:
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)
        self._heartbeat_pending[seq] = time.monotonic()
        await self._enqueue_json(ServerMessage.ping(seq=seq))
        seq += 1
```

When the client replies `{type: "pong", seq}`, the server records `last_rtt_ms = (now - pending[seq]) * 1000`. Pending entries older than 30 s are evicted. The `network.latencyMs` field in the next snapshot uses `last_rtt_ms` (or `null` if no RTT measured yet).

The previous telemetry-style heartbeat is deleted — telemetry events still exist for log lines (errors, state transitions); they're no longer used for liveness/RTT.

## 6. Per-panel design

Each section is the contract a Phase-C subagent receives. Format is identical: state shape, data source, frontend file(s), test, acceptance.

### 6.1 Header

- **State:** `{ uptimeMs: number, wsState: "live" | "demo" | "reconnecting" }`
- **Source:** `wsState` derived from `connect()` mode + WS reconnect telemetry events
- **File:** `web/src/ui/Header.ts`
- **Render addition:** state badge in the header bar, `data-state` attribute toggles a CSS pulse on `reconnecting`
- **Test:** unit test verifies the three states render distinct DOM attributes
- **Acceptance:** badge updates within 1 s of WS state change

### 6.2 Centerpiece

- No real-data change in v2. Subagent only adds a unit test that documents the analyser-driven amplitude path (currently uncovered).
- **File:** `web/src/ui/Centerpiece.ts` (no modification) + `web/test/centerpiece.test.ts` (new)

### 6.3 System

- **State:** `{ uptimeMs, load: number, tokensPerMin: number, sessionId: string, modelName: string }`
- **Source:** snapshot `system.*`; `uptimeMs` continues to be derived from app boot in main.ts
- **File:** `web/src/ui/panels/SystemPanel.ts`
- **Render:** existing rows + new `model` row beneath `session`
- **Test:** unit test feeds a snapshot, asserts each value renders

### 6.4 Memory

- **State:** `{ contextUsed, contextMax }` — drop `recallPct` (no defensible meaning)
- **Source:** snapshot `memory.*`
- **File:** `web/src/ui/panels/MemoryPanel.ts`
- **Render:** drop the recall row + bar; keep the context row + bar
- **Test:** unit test verifies bar width = `(contextUsed / contextMax) * 100` clamped 0..100

### 6.5 Calendar

- **State:** `{ entries: { time: string, title: string, durationMin: number }[], syncing: boolean }`
- **Source:** `calendar.update` event payload routed into store; `syncing` flips true on user click and false when the next `calendar.update` arrives
- **Sync trigger:** new "Sync" button in the panel. On click, the panel emits `events.syncCalendar()` (new method on `EventSource`) which sends `{type: "calendar.sync"}` over the wire. The button is disabled while `syncing === true`.
- **File:** `web/src/ui/panels/CalendarPanel.ts`, `web/src/data/calendar.ts` (drop the hard-coded TODAY constant), `web/src/events/eventSource.ts` (add `syncCalendar()`), `web/src/events/wsEventSource.ts` + `web/src/events/mockEventSource.ts` (implement)
- **Render:** rows show `HH:MM  Title (Nm)` where `(Nm)` is duration if known; header has a `[Sync]` button
- **Empty state:** "Click Sync to load today's calendar" when `entries.length === 0`
- **Test:** unit test renders 0/1/5 entries, button click invokes `syncCalendar`, button disables during `syncing`

### 6.6 Network

- **State:** `{ endpoint, latencyMs, packets, sendQueueDepth, sendQueueMax }`
- **Source:** snapshot `network.*`; `endpoint` in live mode = WS URL, in demo mode = `"demo"`
- **File:** `web/src/ui/panels/NetworkPanel.ts`
- **Render:** existing rows; `busyPct` becomes `sendQueueDepth / sendQueueMax * 100` for the bar
- **Test:** unit test asserts bar width and missing-latency display (`-- ms`)

### 6.7 Tasks

- **State:** `{ queued, active, done }` — same shape as today
- **Source:** snapshot `tasks.*`
- **File:** `web/src/ui/panels/TasksPanel.ts`
- **Render:** unchanged shape; values now come from snapshot
- **Test:** unit test verifies it just renders the input

### 6.8 Telemetry

- No source change. Subagent ensures the synthetic-mode heartbeat banner is not the only event in live mode (a regression check, not a feature).
- **File:** `web/src/ui/panels/TelemetryPanel.ts` (no modification expected) + `web/test/telemetry.test.ts` if missing

### 6.9 Audio

- **State:** `{ inputDb, outputDb, inputBarPct, mic }`
- **Source:** `outputDb` newly computed each render frame from `playbackQueue.analyser` RMS (similar to centerpiece amplitude in spec-03), wired in `main.ts`
- **File:** `web/src/ui/panels/AudioPanel.ts` (no shape change; `main.ts` change to compute outputDb)
- **Test:** existing tests still pass; new unit test for the `analyser → dB` helper

## 7. Multi-agent execution plan

Three phases. Phases A and B are orchestrator-driven (sequential, touches shared protocol/transport). Phase C is per-panel parallel subagent dispatch. Each panel's subagent gets a sealed prompt: panel section verbatim from §6, snapshot schema from §5.1, allowed-files list, forbidden-files list.

| Phase | Approach | Tasks |
|---|---|---|
| A — server foundation | Orchestrator inline (TDD) | A1 protocol additions; A2 heartbeat refactor; A3 state.py emitter; A4 tasks.py; A5 calendar_client.py |
| B — frontend decode | Orchestrator inline (TDD) | B1 WSEventSource decodes new messages; B2 store `panelData` slice; B3 main.ts wires `panelData` into render calls |
| C — per-panel | Parallel subagents (one implementer per panel; per-panel reviewer follows) | C1–C9, one task per panel; dispatched in batches of 3 to limit parallel writes |
| D — verification | Orchestrator | full vitest + pytest + lint + typecheck + build; STATUS update; manual e2e checklist additions |

**Subagent prompt template (Phase C):**
- Read skill: `subagent-driven-development.md`
- Branch context: this work is on `panels-v2`; current commit is the tip of B
- Allowed files: `<panel file>`, `<panel test file>` only
- Forbidden files: any other panel file, server/, WSEventSource, store, main.ts, types.ts (orchestrator owns those)
- Snapshot schema: pasted verbatim
- Task: implement §6.x; tests pass; commit with message `feat(panels): <panel> v2 — real data from snapshot`
- Status report format: `DONE` / `DONE_WITH_CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED` per the skill

**Reviewer prompt** (per panel, sequential after the panel's implementer reports):
- Two-stage: spec compliance reviewer first, then code quality reviewer (per skill)
- Scope: same allowed-files

**File-isolation guarantee:** all 9 panels touch disjoint files (each is `web/src/ui/panels/<Name>Panel.ts` + `web/test/<name>.test.ts`). The "Don't dispatch parallel implementers" rule from `subagent-driven-development.md` exists to prevent file conflicts; this v2 work proves disjoint scope, so parallel dispatch is safe and is the user-approved approach.

## 8. Tests

**Server (Phase A):**
- `tests/test_state_snapshot.py` — snapshot schema, cadence, queue-saturation drop
- `tests/test_tasks.py` — enqueue/start/finish/snapshot semantics
- `tests/test_calendar_client.py` — projection from Google API responses to entries (mock the API)
- `tests/test_heartbeat.py` — ping/pong RTT, timeout eviction
- Existing 58 tests must continue to pass

**Frontend (Phase B + C):**
- `test/wsEventSource.test.ts` extended for `state.snapshot`, `calendar.update`, `pong` echo
- One test file per panel where missing: `test/header.test.ts`, `test/centerpiece.test.ts`, `test/systemPanel.test.ts`, `test/memoryPanel.test.ts`, `test/calendarPanel.test.ts`, `test/networkPanel.test.ts`, `test/tasksPanel.test.ts`, `test/telemetryPanel.test.ts`, `test/audioPanel.test.ts` (some of these may already exist in some form — subagent extends if so)
- Existing 60 tests must continue to pass

## 9. Acceptance criteria

- All server tests pass; lint + mypy clean
- All frontend tests pass; lint + tsc + build clean
- With backend running (`uvicorn server.main:app`), the deployed site shows live values on every panel within 2 s of connect:
  - System: load, tokens/min, session id, model name update
  - Memory: bar fills proportional to a recent turn's history token count
  - Calendar: empty by default; clicking Sync fetches today's actual events from the connected Google account
  - Network: latency reflects real RTT (`< 50 ms` on localhost), packet count climbs with messages, busy bar reflects send queue depth
  - Tasks: counts reflect anything enqueued via `tasks.enqueue` from a `python -m server.cli_test` test path
  - Header: badge shows `live`; toggling backend off → `reconnecting` → on → `live`
  - Audio: outputDb reacts to assistant speech
- Demo mode (no backend): all panels keep working with mock/zero values, no console errors

## 10. One-time manual setup (Maxime)

Documented in `server/deploy/README.md` addendum:

1. Google Cloud Console → create project → enable Calendar API → create OAuth client (Desktop) → download `credentials.json`
2. `mkdir -p ~/.config/jarvis && mv credentials.json ~/.config/jarvis/`
3. First server run prompts for browser auth; refresh token saved to `~/.config/jarvis/google-token.json`

## 11. Risks

| Risk | Mitigation |
|---|---|
| Subagent variance across 9 panels | Two-stage review per panel (skill-mandated). Reviewer catches drift; per-panel scope is small enough that a redo costs ~5 min. |
| `psutil` cross-platform behavior | Tested on Linux (target laptop OS, spec-04). macOS works with the same API; Windows untested + out of scope. |
| Google OAuth refresh fails in production | Server logs a clear warning + emits a one-shot `telemetry` error; calendar panel falls back to "No events". Documented manual re-auth procedure. |
| Snapshot at 1 Hz is wasteful while idle | Acceptable for v2 (~200 B/s). Event-driven snapshot is a future optimization. |
| `tasks.py` queue grows unbounded over a long session | Done counter wraps at `2**31 - 1`; queued/active are strictly bounded by what's running. Acceptable for v2. |
| Calendar leaks data via the WS connection | Connection is `ws://localhost`; server never forwards calendar to anyone but the local browser. Documented in spec §5.4. |

## 12. Self-review notes

- [x] Per-panel sections (§6.1–9) include exactly one allowed-files list per subagent — no overlap
- [x] Phase A and B explicitly orchestrator-driven; Phase C explicitly parallel subagent
- [x] Snapshot schema (§5.1) is the single source of truth used by both server emitter and per-panel subagent prompts
- [x] No new dependencies on the frontend (only existing `web/src` modules); server adds `psutil`, `google-auth`, `google-auth-oauthlib`, `google-api-python-client` (all well-maintained, MIT/Apache)
- [x] Demo-mode backwards compat preserved — placeholder data + zero values still render without crashes

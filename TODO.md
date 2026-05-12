# Jarvis — Missing Implementations

Items are grouped by area. Each entry names the stub, the file it lives in, and the real interface needed to replace it.

---

## Frontend — Compass Zones & Overlays

### Code zone shows hardcoded stub files
**Files:** `web/src/compass/types.ts:119`, `web/src/ui/compass/zones/EastCode.ts`  
`STUB_CODE_FILES` is a static array of three filenames. The diff pane in CodeFocus renders hardcoded `+/-` lines.  
**To implement:** Wire `simple-git` (or a backend `/git/status` endpoint) to return the active branch, changed files, and per-file diffs. Interface: `GitCodeSource { branch: string; files: CompassCodeFile[]; buildStatus: "ok" | "fail" | "running" }`.

### Real git diff not rendered in CodeFocus overlay
**File:** `web/src/ui/compass/overlays/CodeFocus.ts:31`  
The diff pane always shows the same three hardcoded lines regardless of which file is selected.  
**To implement:** Fetch `DiffLine[]` per file from the git source above and render them dynamically. Interface: `GitCodeSource.diff(file: string): DiffLine[]`.

### Task rows have no individual task detail
**File:** `web/src/compass/types.ts:100`  
`PanelDataTasks` only carries aggregate counts (active / queued / done). The mapper synthesises placeholder rows with `"step — / —"` and `pct: 50`.  
**To implement:** Expose individual task records from the agent runtime (Temporal, BullMQ, or Jarvis's own tasks table). Interface: `TaskDetail { id, label, state: "run"|"queue"|"done", step: number, totalSteps: number, pct: number }`.

### Notification chips are a static stub array
**Files:** `web/src/compass/types.ts:127`, `web/src/ui/compass/CompassApp.ts:218`  
`STUB_NOTIFS` is six hardcoded chips that never change and are never dismissed persistently.  
**To implement:** Replace with a unified notification inbox fed by real sources:
- **Calendar** (ready to wire): emit a chip when a calendar event is ≤ 5 min away, using the existing `calendar.update` WebSocket event.
- **Tasks** (ready to wire): emit on task state transition (queue → run, run → done).
- **System** (ready to wire): emit when context usage > 80 % or CPU load > threshold, from `state.snapshot`.
- **Build / CI** (needs external webhook): subscribe to a webhook from GitHub Actions / your CI provider. Interface: `NotifSource.build(payload: CIWebhookPayload): CompassNotif`.

---

## Backend — Mock Pipelines

The server ships with three Phase-1 mock pipelines that replace real ML models. All three are wired via the `stt_engine`, `tts_engine`, and `model_name` settings in `server/server/config.py`.

### MockSTT — no real speech recognition
**File:** `server/server/pipelines/mock_stt.py`  
Emits progressive prefixes of a single canned string (`"Brief me on today."`). No audio is decoded.  
**To implement:** Already partially done — `WhisperSTT` (`pipelines/whisper_stt.py`) is the real replacement. Set `JARVIS_STT_ENGINE=whisper` (or `auto`) in production. Requires `faster-whisper` installed and a downloaded model (default `base.en`).

### MockLLM — keyword-routed canned responses
**File:** `server/server/pipelines/mock_llm.py`  
Picks a reply from `scenarios.py` by coarse keyword matching. Ignores conversation history and extra context entirely.  
**To implement:** Set `JARVIS_MODEL_NAME=claude-sonnet-4-6` (or any `claude-*` model) in production. `ClaudeLLM` is already implemented in `pipelines/claude_llm.py` and requires `ANTHROPIC_API_KEY`.

### MockTTS — emits no audio
**File:** `server/server/pipelines/mock_tts.py`  
`synthesize()` returns empty bytes. The UI never receives any audio to play back.  
**To implement:** Two real replacements exist:
- `EdgeTTS` (`pipelines/edge_tts.py`) — Microsoft neural TTS, no API key needed. Set `JARVIS_TTS_ENGINE=edge`.
- `OpenVoiceTTS` (`pipelines/openvoice_tts.py`) — local voice cloning. Set `JARVIS_TTS_ENGINE=openvoice` and `JARVIS_OPENVOICE_PATH`.

---

## Backend — Missing Endpoints

### No `/git/status` or `/git/diff` endpoint
The EastCode zone and CodeFocus overlay need live git data.  
**To implement:** Add routes (or extend the WebSocket `state.snapshot`) to expose `{ branch, files: CompassCodeFile[], buildStatus }` and per-file diffs. `simple-git` (Node side) or `pygit2` / `gitpython` (Python side) can drive this.

---

## Shipped

- 2026-05-12: Voice dock recent commands persisted to `localStorage` via `CommandHistory` (PR #23)
- 2026-05-12: `POST /auth/login` with argon2 verification + frontend wiring (PR #24)
- 2026-05-12: Calendar attendees + room forwarded to `CalendarTakeover` (PR #25)

# Jarvis — Missing Implementations

Items are grouped by area. Each entry names the stub, the file it lives in, and the real interface needed to replace it.

---

## Frontend — Compass Zones & Overlays

### Task rows have no individual task detail
**File:** `web/src/compass/types.ts:100`  
`PanelDataTasks` only carries aggregate counts (active / queued / done). The mapper synthesises placeholder rows with `"step — / —"` and `pct: 50`.  
**To implement:** Expose individual task records from the agent runtime (Temporal, BullMQ, or Jarvis's own tasks table). Interface: `TaskDetail { id, label, state: "run"|"queue"|"done", step: number, totalSteps: number, pct: number }`.

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

## Notifications — deferred sources

The notification chip system (PR #27) ships with three live sources (calendar ≤5 min, task transitions, context budget > 80%). One source was intentionally deferred:

### Build / CI notification source
**File:** `web/src/ui/compass/notifManager.ts`  
**To implement:** Subscribe to a webhook from GitHub Actions (or whatever CI is wired). On failed/passed workflow runs, emit a chip via the existing manager. Interface: `NotifSource.build(payload: CIWebhookPayload): CompassNotif`. Needs a small backend route (`POST /webhooks/ci`) that the chip manager polls or subscribes to via WS.

---

## Shipped

- 2026-05-12: Voice dock recent commands persisted to `localStorage` via `CommandHistory` (PR #23)
- 2026-05-12: `POST /auth/login` with argon2 verification + frontend wiring (PR #24)
- 2026-05-12: Calendar attendees + room forwarded to `CalendarTakeover` (PR #25)
- 2026-05-12: Notification chips live from calendar / tasks / system sources, with DOM reconciliation + click-to-dismiss persistence (PR #27)
- 2026-05-12: `/git/status` + `/git/diff` endpoints with Bearer-token auth (consumes `/auth/login` tokens); EastCode zone + CodeFocus overlay wired to live git data; WebSocket `/ws` now auth-gated when a passphrase hash is configured (PR #29)

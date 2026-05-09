# Jarvis Setup Checklist

Everything Jarvis needs from you (the user) to run end-to-end. Work through it top to bottom — items are ordered so each step's prerequisites are already done. Each section says **what** to do, **where** to get it, and **why** it matters.

Default mode (no API keys, no extra installs) gives you a working HUD with **mock** STT/LLM/TTS — useful for the demo, not useful as an assistant. The keys and credentials below light up the real functionality.

---

## 0. Prerequisites

- [ ] **Python 3.12+** — `python3 --version`. The server pins `>=3.12`.
- [ ] **Node 20+** — `node --version`. Required for the web app and for `npx staticrypt` in CI.
- [ ] **git** — `git --version`.
- [ ] **A microphone** — needed for the audio path; text path works without one.
- [ ] **A modern Chromium-based browser** — required for `AudioWorklet` (used in `web/public/mic-processor.js`).

OS notes:
- **Linux**: `systemd --user` autostart works as documented (`server/deploy/`).
- **macOS**: Everything works except the systemd unit; use `launchd` or run `uvicorn` in a terminal/tmux.
- **Windows**: Use WSL2.

---

## 1. Clone the repo and create your venv

```bash
git clone https://github.com/mhaegeman/jarvis.git
cd jarvis

# Backend venv
cd server
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd ..

# Frontend deps
cd web
npm install
cd ..
```

- [ ] `cd server && pytest -q` passes (54 tests, all mocks).
- [ ] `cd web && npm run test` passes.

If both pass, the skeleton is healthy and you can start filling in the real services below.

---

## 2. Anthropic API key (the LLM brain)

This is the single most important key. Without it, Jarvis runs on `MockLLM`, which only replies from a small static scenario library — it can't actually talk to you.

- [ ] Go to **https://console.anthropic.com/** and sign in (or sign up).
- [ ] Click **Settings → API Keys → Create Key**.
- [ ] Name it something like `jarvis-laptop`.
- [ ] Copy the key (starts with `sk-ant-…`). You only see it once.
- [ ] Add **at least $5 of credit** at **Settings → Billing**, or your first WS turn errors out with a 401.
- [ ] Optional but recommended: at **Settings → Limits**, set a daily spend cap so a runaway bug can't drain the account.

Where to put the key — pick **one** of these:

**Option A: `.env` file (simplest for local dev)**
```bash
# server/.env  (already gitignored via server/.gitignore patterns, but verify)
ANTHROPIC_API_KEY=sk-ant-...
JARVIS_MODEL_NAME=claude-sonnet-4-6
```
- [ ] `cat server/.gitignore` — make sure `.env` is excluded before you commit anything.

**Option B: shell export (CI-style)**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export JARVIS_MODEL_NAME=claude-sonnet-4-6
```

**Option C: systemd service (autostart, see §10)** — set both as `Environment=` lines.

### Pick your default model

Set via `JARVIS_MODEL_NAME`:

| Value | Use when |
|---|---|
| `mock` | Offline/demo only. No API calls. |
| `claude-haiku-4-5` | Fast & cheap. Good default for chatty interactions. |
| `claude-sonnet-4-6` | **Recommended starting default.** Better reasoning, still cheap. |
| `claude-opus-4-7` | Hard questions / deep reasoning. Slower, ~5x cost. |

Per-turn override: prefix any message with `/haiku`, `/sonnet`, or `/opus` to route just that turn.

- [ ] Smoke test:
  ```bash
  cd server
  source .venv/bin/activate
  uvicorn server.main:app --port 8000          # terminal 1
  python -m server.cli_test                    # terminal 2; type "hello"
  ```
  Should stream a real Claude reply token-by-token. Check **https://console.anthropic.com/** → **Usage** to confirm the call landed on the right model.

> The server refuses to start if `JARVIS_MODEL_NAME` selects a Claude model but `ANTHROPIC_API_KEY` is unset (`server/main.py:46`) — this is intentional, fail-fast over silent 401 loops.

---

## 3. Real Speech-to-Text (faster-whisper)

Without this, `MockSTT` returns the same canned text regardless of what you say.

- [ ] Install the extra:
  ```bash
  cd server
  source .venv/bin/activate
  pip install -e ".[stt]"
  ```
- [ ] (Optional) pin engine + model size:
  ```bash
  export JARVIS_STT_ENGINE=whisper       # or leave =auto (default)
  export JARVIS_WHISPER_MODEL=base.en    # tiny.en | base.en | small.en | medium.en
  ```
  - `tiny.en` (~75 MB) — fastest, lowest quality.
  - `base.en` (~140 MB) — **recommended default**, good speed/quality balance on CPU.
  - `small.en` (~460 MB) — noticeably better, requires GPU for real-time.
  - `medium.en` (~1.5 GB) — GPU only.
- [ ] (Optional) force device: `JARVIS_DEVICE=cuda|mps|cpu`. Default `auto` probes torch.

The first connection downloads the model into `~/.cache/huggingface/hub`. Subsequent runs reuse it.

- [ ] Verify: start the server, hold **Space** in the web UI, speak — partial transcripts should appear live in the transcript panel as you talk.

---

## 4. Real Text-to-Speech (OpenVoice)

Without this, `MockTTS` emits sentence markers but no audio — the centerpiece waveform fakes amplitude during `speaking`.

OpenVoice is **not a pip package**. You need to clone two repos and merge them.

- [ ] Clone the code and the checkpoints:
  ```bash
  git clone https://github.com/myshell-ai/OpenVoice ~/OpenVoice
  cd ~/OpenVoice
  git clone https://huggingface.co/myshell-ai/OpenVoice
  cp -r OpenVoice/* .
  ```
  Final layout under `~/OpenVoice/`:
  - `api.py`
  - `checkpoints/base_speakers/EN/checkpoint.pth`
  - `checkpoints/converter/checkpoint.pth`

  > Hugging Face may require a free account + accepting the model terms before `git clone https://huggingface.co/myshell-ai/OpenVoice` works. Sign in at **https://huggingface.co/** first.

- [ ] Install torch + the `[tts]` extras (CPU example — replace the index URL for CUDA from **https://pytorch.org/get-started/locally/**):
  ```bash
  cd <repo>/server
  source .venv/bin/activate
  pip install torch --index-url https://download.pytorch.org/whl/cpu
  pip install -e ".[tts]"
  ```
- [ ] Configure the engine:
  ```bash
  export JARVIS_TTS_ENGINE=openvoice           # or leave =auto (default)
  export JARVIS_OPENVOICE_PATH=~/OpenVoice     # default; set if cloned elsewhere
  ```

The server validates the OpenVoice clone at startup (`server/main.py:121`) and falls back to `MockTTS` with a warning if files are missing — set `JARVIS_TTS_ENGINE=openvoice` to make missing files a hard error instead.

### 4a. Voice cloning (optional, but the whole point)

Clone your own voice so Jarvis sounds like you, not the default English speaker.

- [ ] Record **10–30 seconds of clean speech** — quiet room, single voice, normal cadence. WAV format.
  - Easiest path: phone voice memo → export as WAV → AirDrop/scp to laptop.
  - Or in-browser: any WebM recorder + `ffmpeg -i input.webm -ar 24000 -ac 1 voice.wav`.
- [ ] Save it somewhere stable, e.g. `~/.config/jarvis/voice-sample.wav`.
- [ ] Point the server at it:
  ```bash
  export JARVIS_SPEAKER_WAV=~/.config/jarvis/voice-sample.wav
  ```
- [ ] First synthesize call runs `se_extractor` once, then caches. Subsequent turns are fast.

If the cloned voice sounds off, re-record with: less reverb, no background music, more vowel variety, ~20 s minimum.

---

## 5. Google Calendar (HUD Calendar panel)

Optional. Without this, the Calendar panel just stays empty — nothing else breaks.

- [ ] Go to **https://console.cloud.google.com/**.
- [ ] Create a project (or pick one). Name it e.g. `jarvis-personal`.
- [ ] **APIs & Services → Library** → search **Google Calendar API** → **Enable**.
- [ ] **APIs & Services → OAuth consent screen**:
  - User Type: **External**
  - Add yourself as a **Test User** (under Audience). Without this you'll get `access_denied` on first auth.
  - Scopes: add `https://www.googleapis.com/auth/calendar.readonly`.
- [ ] **APIs & Services → Credentials → Create credentials → OAuth client ID**:
  - Application type: **Desktop app**
  - Download the JSON.
- [ ] Save it as `~/.config/jarvis/credentials.json`:
  ```bash
  mkdir -p ~/.config/jarvis
  mv ~/Downloads/client_secret_*.json ~/.config/jarvis/credentials.json
  chmod 600 ~/.config/jarvis/credentials.json
  ```
- [ ] First fetch (click **Sync** in the Calendar panel) opens a browser tab for OAuth consent. After you approve, a refresh token is saved at `~/.config/jarvis/google-token.json`.

If Google rotates the refresh token (occasional `calendar fetch failed` lines in the journal):
```bash
rm ~/.config/jarvis/google-token.json
# next click on Sync re-prompts
```

---

## 6. Memory (already on, no setup needed)

Conversation summaries persist to SQLite at `server/data/memory.db` so Jarvis remembers across sessions. This is on by default (`server/server/config.py:22`) and uses Claude Haiku for summarization (`JARVIS_MEMORY_MODEL`).

- [ ] To disable: `export JARVIS_MEMORY=off`.
- [ ] To wipe and start over: `rm server/data/memory.db`.
- [ ] To relocate: `export JARVIS_MEMORY_DB=/path/to/memory.db`.

The DB is gitignored. It's not encrypted — treat it as you would your shell history.

---

## 7. Frontend wiring

- [ ] If your backend runs on a non-default port or host, set `VITE_WS_URL` in `web/.env.local`:
  ```bash
  echo 'VITE_WS_URL=ws://localhost:8000/ws' > web/.env.local
  ```
  Default backend port in the systemd unit is **8000**; the `server/README.md` Develop section shows **8765**. Pick one and be consistent.
- [ ] (E2E only) install Playwright system deps once:
  ```bash
  sudo npx playwright install-deps chromium
  cd web && npx playwright install chromium
  ```

---

## 8. End-to-end smoke test

With backend + web both running:

```bash
# terminal 1
cd server && source .venv/bin/activate && uvicorn server.main:app --port 8000

# terminal 2
cd web && npm run dev
```

Open `http://localhost:5173` in Chromium and walk through `web/README.md` "Manual end-to-end checklist (spec-03)":

- [ ] Header shows `LIVE` (not `DEMO`).
- [ ] Type "Brief me on today" via dev controls — streamed reply with audio.
- [ ] Hold **Space**, speak, release — transcript appears, reply plays.
- [ ] Mid-reply, press **Esc** — audio stops immediately.
- [ ] Kill `uvicorn`, watch telemetry show reconnect attempts; restart, watch it reconnect.
- [ ] Click **Sync** on Calendar panel — today's events load.

If everything in that list works, Jarvis is fully wired.

---

## 9. (Linux only) systemd autostart

Keeps `uvicorn` alive across reboots and login so the deployed GitHub Pages site (§10) always finds a backend.

- [ ] Install the unit:
  ```bash
  JARVIS_ROOT="$(git rev-parse --show-toplevel)"
  mkdir -p ~/.config/systemd/user
  cp "$JARVIS_ROOT/server/deploy/jarvis-backend.service" ~/.config/systemd/user/
  sed -i "s|%h/jarvis|$JARVIS_ROOT|g" ~/.config/systemd/user/jarvis-backend.service
  ```
- [ ] Edit `~/.config/systemd/user/jarvis-backend.service` and add your env vars under `[Service]`:
  ```ini
  Environment=ANTHROPIC_API_KEY=sk-ant-...
  Environment=JARVIS_MODEL_NAME=claude-sonnet-4-6
  Environment=JARVIS_STT_ENGINE=whisper
  Environment=JARVIS_TTS_ENGINE=openvoice
  Environment=JARVIS_OPENVOICE_PATH=%h/OpenVoice
  Environment=JARVIS_SPEAKER_WAV=%h/.config/jarvis/voice-sample.wav
  ```
- [ ] Enable + start:
  ```bash
  systemctl --user daemon-reload
  systemctl --user enable --now jarvis-backend.service
  curl http://127.0.0.1:8000/health        # should return {"status":"ok"}
  ```
- [ ] Persist past logout (otherwise it stops when you log out):
  ```bash
  loginctl enable-linger "$USER"
  ```
- [ ] Verify: `journalctl --user -u jarvis-backend -f` and trigger a turn from the web UI.

---

## 10. GitHub Pages deploy (live URL)

The deployed site at **https://mhaegeman.github.io/jarvis/** is already wired — every push to `main` rebuilds, encrypts `index.html` with [staticrypt](https://github.com/robinmoisson/staticrypt), and publishes via `actions/deploy-pages` (`.github/workflows/`).

You only need to set **one** repo secret:

- [ ] Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**.
- [ ] Name: `STATICRYPT_PASSWORD`. Value: any password you'll remember; this is what the password gate prompts for.
- [ ] Push any commit to `main`, or run **Actions → Deploy → Run workflow**.
- [ ] Verify: open `https://mhaegeman.github.io/jarvis/`, enter the password, see the HUD.

The deployed site connects to `ws://localhost:8000/ws` — so it only "works" while your laptop is on, the systemd unit (§9) is running, and the laptop is on the same machine you're browsing from. That's by design ("nothing leaves the room").

To rotate the password:
- [ ] Update the `STATICRYPT_PASSWORD` secret.
- [ ] Re-run the **Deploy** workflow (or push any commit).

---

## 11. Quick reference: env vars

All backend vars in one place. Drop them in `server/.env`, your shell, or the systemd unit.

| Var | Default | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required** for any non-mock LLM. From console.anthropic.com. |
| `JARVIS_MODEL_NAME` | `mock` | `mock` \| `claude-haiku-4-5` \| `claude-sonnet-4-6` \| `claude-opus-4-7` |
| `JARVIS_LLM_MAX_TOKENS` | `1024` | Base per-request `max_tokens` (auto 2× for `/sonnet`, 4× for `/opus`). |
| `JARVIS_WS_PORT` | `8765` | uvicorn port (note: deploy unit uses 8000). |
| `JARVIS_LOG_LEVEL` | `INFO` | Python logger level. |
| `JARVIS_STT_ENGINE` | `auto` | `auto` \| `mock` \| `whisper` |
| `JARVIS_WHISPER_MODEL` | `base.en` | `tiny.en` \| `base.en` \| `small.en` \| `medium.en` |
| `JARVIS_TTS_ENGINE` | `auto` | `auto` \| `mock` \| `openvoice` |
| `JARVIS_OPENVOICE_PATH` | `~/OpenVoice` | Path to your OpenVoice clone. |
| `JARVIS_SPEAKER_WAV` | — | Path to a 10–30 s WAV for voice cloning. |
| `JARVIS_DEVICE` | `auto` | `auto` \| `cuda` \| `mps` \| `cpu` |
| `JARVIS_MEMORY` | `true` | Set `off` to disable persistent memory. |
| `JARVIS_MEMORY_DB` | `data/memory.db` | SQLite path (cwd-relative). |
| `JARVIS_MEMORY_MODEL` | `claude-haiku-4-5-20251001` | Summarizer model. |
| `JARVIS_MEMORY_RESUME_MIN` | `30` | Resume-window in minutes. |
| `JARVIS_MEMORY_REFRESH_TURNS` | `5` | Re-summarize every N turns. |
| `JARVIS_MEMORY_RECENT_WINDOW` | `20` | Recent-turns window. |
| `JARVIS_MEMORY_FACTS_CAP` | `50` | Max long-term facts. |

Frontend:

| Var | Default | What it does |
|---|---|---|
| `VITE_WS_URL` | `ws://localhost:8000/ws` | Backend WS endpoint. |
| `VITE_BASE` | `/` | Vite base path. CI sets this to `/jarvis/` for Pages. |

GitHub repo secrets:

| Secret | What it does |
|---|---|
| `STATICRYPT_PASSWORD` | Password gate for the deployed Pages site. |

Local files outside the repo:

| Path | Purpose |
|---|---|
| `~/.config/jarvis/credentials.json` | Google OAuth desktop client. |
| `~/.config/jarvis/google-token.json` | Refresh token (auto-written after first OAuth). |
| `~/.config/jarvis/voice-sample.wav` | Optional cloning reference. |
| `~/OpenVoice/` | OpenVoice code + checkpoints. |
| `~/.cache/huggingface/hub/` | Whisper model cache. |
| `server/data/memory.db` | Conversation memory. |

---

## 12. Troubleshooting

**`ANTHROPIC_API_KEY` is unset error on startup.** Either you set `JARVIS_MODEL_NAME` to a Claude model without setting the key, or the key is in `server/.env` but you ran `uvicorn` from a different cwd. Fix: confirm the `.env` is next to where you launch `uvicorn`, or `export` the key in the same shell.

**Calendar panel always empty.** Check `journalctl --user -u jarvis-backend` for `calendar credentials missing` (= `~/.config/jarvis/credentials.json` not found) or `calendar fetch failed` (= token expired, delete `google-token.json`).

**Whisper falls back to MockSTT silently.** You're on `JARVIS_STT_ENGINE=auto` and `faster-whisper` isn't installed. Install with `pip install -e ".[stt]"`, or set `JARVIS_STT_ENGINE=whisper` to make the missing dep a hard failure.

**OpenVoice falls back to MockTTS silently.** Same pattern: `auto` mode is forgiving. Either torch isn't installed, or the clone at `JARVIS_OPENVOICE_PATH` is missing `api.py` / one of the `.pth` checkpoints. Set `JARVIS_TTS_ENGINE=openvoice` to fail loudly.

**Web shows `DEMO` instead of `LIVE`.** Backend not reachable at `VITE_WS_URL`. Check `curl http://localhost:8000/health`. If the backend is on a different port, set `VITE_WS_URL` accordingly and rebuild.

**Microphone denied.** Browser permission. In Chromium: lock icon → Site settings → Microphone → Allow. Text path keeps working without it.

**Pages deploy fails with `STATICRYPT_PASSWORD repo secret is not set`.** Add the secret (§10).

**`libnspr4.so: cannot open shared object file` in Playwright.** `sudo npx playwright install-deps chromium`.

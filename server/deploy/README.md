# Backend autostart (systemd --user)

A `systemd --user` unit that runs `uvicorn` on the laptop with on-failure
restart and start-at-login. Pairs with the spec-04 GH Pages deployment so
the live site at `https://mhaegeman.github.io/jarvis/` always finds a
backend at `ws://localhost:8000/ws`.

## Prerequisites

A working venv at `server/.venv/` with the package installed:

```bash
cd server
python3.12 -m venv .venv
.venv/bin/pip install -e .
```

(For development extras add `.[dev]`.)

## Install

Run from anywhere inside the cloned `jarvis` repository:

```bash
JARVIS_ROOT="$(git rev-parse --show-toplevel)"

mkdir -p ~/.config/systemd/user
cp "$JARVIS_ROOT/server/deploy/jarvis-backend.service" ~/.config/systemd/user/

# Rewrite the `%h/jarvis` placeholder to the actual repo path.
sed -i "s|%h/jarvis|$JARVIS_ROOT|g" ~/.config/systemd/user/jarvis-backend.service

systemctl --user daemon-reload
systemctl --user enable --now jarvis-backend.service
```

If you don't have `git` available, replace the first line with the absolute path to the repo, e.g. `JARVIS_ROOT="$HOME/jarvis"`.

## Verify

```bash
systemctl --user status jarvis-backend
curl http://127.0.0.1:8000/health   # → 200 OK
journalctl --user -u jarvis-backend -f
```

## Persist across logout

Without this the service stops when you log out. Required if you want the
backend to keep running while the laptop's screen is locked or after
closing the terminal:

```bash
loginctl enable-linger "$USER"
```

## Update / restart

After pulling a new version of the server package:

```bash
systemctl --user restart jarvis-backend
```

## Stop / disable

```bash
systemctl --user stop jarvis-backend
systemctl --user disable jarvis-backend
```

## Google Calendar (panels v2)

The Calendar HUD panel reads today's events from Google Calendar via a
read-only OAuth client. Without these credentials the panel just stays
empty — no other system feature is affected.

### One-time setup

1. **Google Cloud Console** → create (or pick) a project.
2. Enable the **Google Calendar API**.
3. **APIs & Services → OAuth consent screen** → set up as External, add
   yourself as a test user, scopes: `calendar.readonly`.
4. **APIs & Services → Credentials → Create credentials → OAuth client
   ID** → application type **Desktop**. Download the JSON.
5. Save it as `~/.config/jarvis/credentials.json`:

```bash
mkdir -p ~/.config/jarvis
mv ~/Downloads/client_secret_*.json ~/.config/jarvis/credentials.json
chmod 600 ~/.config/jarvis/credentials.json
```

### First run

The first time the server fetches the calendar (right after the next
WS connection), it pops a browser tab for OAuth consent. After you
grant access, a refresh token is saved at
`~/.config/jarvis/google-token.json` (`chmod 600`). Subsequent runs use
the refresh token silently.

### If Google rotates the refresh token

You'll see a `calendar fetch failed` line in `journalctl --user -u
jarvis-backend`. Delete the token and the next fetch re-prompts:

```bash
rm ~/.config/jarvis/google-token.json
systemctl --user restart jarvis-backend
```

## Real pipelines (optional)

The default install runs with mock pipelines. To enable real Whisper STT:

### STT — faster-whisper

```bash
cd server
pip install -e .[stt]
```

Then either leave `JARVIS_STT_ENGINE=auto` (default) or set it explicitly:

```bash
export JARVIS_STT_ENGINE=whisper
export JARVIS_WHISPER_MODEL=base.en    # or small.en, tiny.en, medium.en
# JARVIS_DEVICE defaults to auto; set to cuda | mps | cpu only to override.
```

Restart the server. The first WS connection downloads the model (~140 MB
for `base.en`) into `~/.cache/huggingface/hub` and warms the singleton;
later connections reuse the cached model.

If `JARVIS_STT_ENGINE=auto` and faster-whisper isn't installed, the
server logs a `WARNING` and falls back to `MockSTT`. Set the engine to
`whisper` to make a missing dep a hard failure.

### TTS — OpenVoice

OpenVoice is not a pip package. Clone the upstream repo and the Hugging Face
checkpoints into one directory:

```bash
git clone https://github.com/myshell-ai/OpenVoice ~/OpenVoice
cd ~/OpenVoice
git clone https://huggingface.co/myshell-ai/OpenVoice
cp -r OpenVoice/* .
```

Then install torch and the [tts] extras (CPU example; replace the torch
index URL for CUDA):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .[tts]
```

Set the engine and (optionally) the cloning reference WAV:

```bash
export JARVIS_TTS_ENGINE=openvoice                  # or leave =auto (default)
export JARVIS_OPENVOICE_PATH=~/OpenVoice            # default; override if cloned elsewhere
# Optional: 10–30 s of clean speech to clone the user's voice. Without it,
# OpenVoice uses its default English speaker.
export JARVIS_SPEAKER_WAV=/path/to/voice-sample.wav
```

The first synthesize call loads the OpenVoice models and (if cloning) runs
`se_extractor` once. Subsequent turns reuse the cached singletons.

If `JARVIS_TTS_ENGINE=auto` and torch isn't installed, the server logs a
`WARNING` and falls back to `MockTTS`. Set the engine to `openvoice` to make
a missing dep a hard failure.

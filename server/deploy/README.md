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

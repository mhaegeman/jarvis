# spec-04 · Deploy + staticrypt gate — Design

**Date:** 2026-05-08
**Status:** Approved (orchestrator, per Architect delegation; user approved 2026-05-08)
**Owner:** Maxime Haegeman (Architect) · Orchestrator (drafting)
**Anchors to:** `docs/superpowers/specs/2026-05-07-jarvis-architecture.md` (umbrella)
**Sister specs:** spec-01, spec-02, spec-03 — all merged to `main`

---

## 1. Goal

Three deliverables, all CI/infra:

1. **PR quality gates** (`.github/workflows/ci.yml`) — run `web/` and `server/` lint/typecheck/test/build on every PR. Required check before merge.
2. **Deployed frontend** (`.github/workflows/deploy.yml`) — on every push to `main`, build `web/`, encrypt the bundle with `staticrypt`, publish to GitHub Pages.
3. **Backend autostart** (`server/deploy/jarvis-backend.service`) — a `systemd --user` unit template so Maxime's laptop runs `uvicorn` automatically at login with on-failure restart.

After this spec, the v1 system is fully shipped: a password-gated HTTPS site at `https://mhaegeman.github.io/jarvis/` that talks to a laptop-resident backend over `ws://localhost:8000/ws`.

## 2. Non-goals (out of scope)

- HTTPS for the backend / Cloudflare tunnel (architecture §7 risk row; future upgrade)
- Custom domain
- Multi-region deploys, preview deployments, branch deploys
- Lighthouse / Playwright e2e on CI (Playwright is documented manual; revisit later)
- Secret rotation automation (manual: update repo secret + re-run workflow)
- Backend deployment off the laptop (same as architecture §8)

## 3. Inputs from prior specs

| From | Contract | Used by |
|---|---|---|
| spec-01 | `web/` builds via `npm run build` (`tsc --noEmit && vite build`); lints via `npm run lint`; tests via `npx vitest run` | `ci.yml` web job |
| spec-02 | `server/` lints via `ruff check .`; types via `mypy`; tests via `pytest -q`. Python ≥3.12. | `ci.yml` server job |
| spec-03 | `connect.ts` reads `import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws"` at build time | `deploy.yml` sets `VITE_WS_URL` env var (or relies on default — see §5.2) |
| spec-03 | `vite build` output is `web/dist/`; bundle ~9 KB gzip JS | `deploy.yml` artifact |

## 4. Architecture

```
PR opened
   │
   ▼
.github/workflows/ci.yml ── parallel jobs
   ├── web    : checkout → setup-node → npm ci → tsc → eslint → vitest → vite build
   └── server : checkout → setup-python → pip install → ruff → mypy → pytest
   │
   └─ both green required before merge (branch protection rule, set manually)

push to main
   │
   ▼
.github/workflows/deploy.yml ── single workflow, two jobs
   ├── build  : npm ci → vite build → staticrypt encrypt → upload-pages-artifact
   └── deploy : actions/deploy-pages → https://mhaegeman.github.io/jarvis/

laptop (Maxime)
   │
   └── systemd --user
         └── jarvis-backend.service
               └── uvicorn server.main:app --host 127.0.0.1 --port 8000
```

## 5. Module-level design

### 5.1 `.github/workflows/ci.yml`

Triggers: `pull_request` (default events: opened, synchronize, reopened) + `push` to `main` (so post-merge CI is recorded on `main`'s commit).

Two jobs run in parallel; both must succeed for the workflow to be green.

**Job `web`:**
```yaml
runs-on: ubuntu-latest
defaults:
  run:
    working-directory: web
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-node@v4
    with:
      node-version: "20"
      cache: npm
      cache-dependency-path: web/package-lock.json
  - run: npm ci
  - run: npx tsc --noEmit
  - run: npm run lint
  - run: npx vitest run
  - run: npm run build
```

**Job `server`:**
```yaml
runs-on: ubuntu-latest
defaults:
  run:
    working-directory: server
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: "3.12"
      cache: pip
      cache-dependency-path: server/pyproject.toml
  - run: pip install -e ".[dev]"
  - run: ruff check .
  - run: mypy
  - run: pytest -q
```

Branch protection (Settings → Branches → main) is configured manually to require `web` and `server` checks before merge. Documented in §9.

### 5.2 `.github/workflows/deploy.yml`

Triggers: `push` to `main` and `workflow_dispatch` (manual re-run). Deploys are **idempotent** — re-running with the same commit SHA and same secret produces the same artifact.

```yaml
name: Deploy
on:
  push:
    branches: [main]
  workflow_dispatch: {}
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: web/package-lock.json
      - run: npm ci
        working-directory: web
      - name: Build
        run: npm run build
        working-directory: web
        env:
          # Default works for Maxime's setup; override here only if backend
          # ever moves off port 8000.
          VITE_WS_URL: ws://localhost:8000/ws
          # Set Vite base path so Pages can serve from /jarvis/.
          VITE_BASE: /jarvis/
      - name: Verify staticrypt secret is set
        run: |
          if [ -z "$STATICRYPT_PASSWORD" ]; then
            echo "::error::STATICRYPT_PASSWORD repo secret is not set."
            echo "Configure: Settings → Secrets and variables → Actions → New repository secret"
            exit 1
          fi
        env:
          STATICRYPT_PASSWORD: ${{ secrets.STATICRYPT_PASSWORD }}
      - name: Encrypt bundle with staticrypt
        run: |
          npx -y staticrypt@^3 web/dist/index.html \
            -p "$STATICRYPT_PASSWORD" \
            --short \
            -d web/dist
        env:
          STATICRYPT_PASSWORD: ${{ secrets.STATICRYPT_PASSWORD }}
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web/dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

**Vite base path note.** GitHub Pages serves the project site from `/jarvis/`, so the bundle's asset URLs (`/assets/index-XXX.js`) need to be prefixed. We set `VITE_BASE` and read it in `vite.config.ts`. This is a one-line config change documented in §5.4.

**`staticrypt` invocation.** `staticrypt@^3` reads the input HTML, replaces it with a self-contained unlock page that decrypts `index.html` client-side using the password (PBKDF2 + AES-256-GCM). `--short` skips the long help link in the generated UI. `-d web/dist` writes back into the build directory in place. The encrypted page references the original assets unchanged — assets are NOT encrypted (only HTML is gated). This is a known limitation of staticrypt; it's acceptable per architecture §2 ("secure enough for now").

### 5.3 `server/deploy/jarvis-backend.service`

`systemd --user` unit installed at `~/.config/systemd/user/jarvis-backend.service`.

```ini
[Unit]
Description=Jarvis backend (FastAPI WebSocket, spec-02)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/jarvis/server
ExecStart=%h/jarvis/server/.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=2
# Keep stdout/stderr in journalctl; harmless if Maxime ignores them.
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

**Install procedure** (in `server/deploy/README.md`):

```bash
# one-time setup
mkdir -p ~/.config/systemd/user
cp server/deploy/jarvis-backend.service ~/.config/systemd/user/
# adjust WorkingDirectory if jarvis lives somewhere other than ~/jarvis
sed -i "s|%h/jarvis|$PWD|g" ~/.config/systemd/user/jarvis-backend.service

# enable and start
systemctl --user daemon-reload
systemctl --user enable --now jarvis-backend.service

# verify
curl http://127.0.0.1:8000/health   # → 200 OK

# enable persistence across logout (so it stays up even when nobody is logged in)
loginctl enable-linger "$USER"
```

The unit assumes a virtualenv at `server/.venv/` already created via `python3.12 -m venv .venv && .venv/bin/pip install -e .` — already documented in `server/README.md` from spec-02. No new venv conventions.

### 5.4 `web/vite.config.ts` — base path support

Single line change to honor `VITE_BASE`:

```ts
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  // …existing config unchanged
});
```

Default `/` keeps `npm run dev` and local `vite preview` working unchanged. The deploy workflow sets `VITE_BASE=/jarvis/`. No runtime check needed — Vite rewrites asset URLs at build time.

### 5.5 `web/README.md` and root README updates

Document:
- Live URL: `https://mhaegeman.github.io/jarvis/`
- How to set/rotate the staticrypt password (Settings → Secrets → `STATICRYPT_PASSWORD`)
- Pointer to `server/deploy/README.md` for backend autostart

## 6. One-time manual setup (Architect, post-merge)

1. **Set staticrypt secret.** Settings → Secrets and variables → Actions → New repository secret → name `STATICRYPT_PASSWORD`, value: chosen password.
2. **Configure GH Pages source.** Settings → Pages → Source: **GitHub Actions**. (No need to set a branch.)
3. **Add branch protection on `main`.** Settings → Branches → Add rule for `main` → require status checks: `web`, `server`. Tick "Require branches to be up to date before merging".
4. **Install backend service** on the laptop following `server/deploy/README.md`.
5. **First deploy** triggers automatically on the spec-04 merge; `actions/deploy-pages` posts a Pages URL in the Actions UI.

These five steps are explicit and small; spec-04 cannot automate them (GitHub repo settings need to be touched once via UI), but it documents them so they aren't lost.

## 7. Testing strategy

Spec-04 is mostly YAML and a unit file — most of the verification is observational.

- **CI workflow self-tests by running.** The PR that introduces `ci.yml` is itself the first thing the workflow runs against. If the web job fails, fix `web/`; if the server job fails, fix `server/`. The PR is not merged until both are green.
- **Deploy workflow.** First deploy lands on the spec-04 merge to main. Manual smoke: visit the Pages URL, unlock with password, observe the HUD loads, telemetry shows demo-mode banner (because no backend running on a laptop reached from GH Pages CI runner — that's expected).
- **Service unit.** Followup the procedure in §5.3, then `curl 127.0.0.1:8000/health` returns `200`. Restart the laptop or reboot the user session, confirm `systemctl --user status jarvis-backend` shows `active (running)`.
- **No new automated tests.** None of these layers benefit from unit testing — they're integration glue.

## 8. Acceptance criteria

- `ci.yml` runs on this PR and is green (both `web` and `server` jobs).
- `deploy.yml` runs on push to `main` and produces a successful Pages deployment.
- Visiting `https://mhaegeman.github.io/jarvis/` shows the staticrypt unlock page; correct password reveals the HUD; no console errors related to asset 404s.
- With the backend running on the laptop, the deployed site connects via `ws://localhost:8000/ws` and a full conversation works (per spec-03 manual checklist).
- `systemctl --user enable --now jarvis-backend.service` brings the backend up; `journalctl --user -u jarvis-backend -f` shows uvicorn logs.
- All four pre-existing tests for web (60) and server (58) remain green via CI.

## 9. Manual setup checklist (in `web/README.md` for posterity)

A condensed numbered list — same content as §6 above, in the place where Maxime will look for it. The spec doc holds the prose; the README holds the actionable list.

## 10. Risks & open questions

| Risk | Mitigation |
|---|---|
| `staticrypt` v3 flag drift in a minor release | Pin `@^3` and document the exact CLI in `deploy.yml`. v4 (if it lands) requires a spec update. |
| GH Pages source toggle missed → silent build, no deploy | Step 2 of §6 is explicit; first deploy will fail with a clear `actions/deploy-pages` error if Pages source is unset. |
| Backend `.venv/` path differs on Maxime's laptop | `server/deploy/README.md` includes a `sed` for `WorkingDirectory` and notes the venv assumption. |
| `pip install -e .[dev]` slow per CI run | Caches via `setup-python`'s `cache: pip`. Acceptable; revisit if pain emerges. |
| `loginctl enable-linger` requires sudo on some distros | Documented as the optional last step; service still works at login without it. |
| Workflow leaks the password into logs | `staticrypt` doesn't echo `-p`. The "verify secret" step compares with `[ -z … ]` (no echo of value). GitHub Actions auto-redacts secrets in logs. |
| Asset URLs not encrypted (only HTML) | Acknowledged limitation of staticrypt; per architecture §2 this is "secure enough for now". |
| First-deploy 404 if `VITE_BASE` not set | Hard-coded in `deploy.yml`; the build env var is the only place it's set. Local `vite preview` uses default `/` so no drift. |

## 11. Self-review notes (orchestrator before commit)

- [x] No "TBD" or placeholders remain
- [x] Internal consistency: workflow YAML quoted matches `package.json` script names; service unit `ExecStart` matches `server/README.md` venv conventions
- [x] Scope: no overlap with spec-03 (no protocol changes); no premature work on real STT/LLM/TTS
- [x] Ambiguity: GH Pages base path explicit (`/jarvis/`); password handling explicit (env var only, never echoed); systemd unit lifetime explicit (`enable-linger` documented)
- [x] Manual one-time steps enumerated in §6 and condensed for `web/README.md`

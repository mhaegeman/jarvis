# spec-04 · Deploy + staticrypt gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up CI quality gates, GitHub Pages auto-deploy with staticrypt encryption, and a systemd `--user` unit for backend autostart.

**Architecture:** Two GitHub Actions workflows (`ci.yml` PR gates; `deploy.yml` push-to-main → Pages) plus a service-unit template under `server/deploy/`. One small Vite config change to honor `VITE_BASE` for the `/jarvis/` Pages path.

**Tech Stack:** GitHub Actions (`actions/checkout@v4`, `actions/setup-node@v4`, `actions/setup-python@v5`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4`), `staticrypt@^3`, systemd. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-05-08-deploy-and-gate-design.md`

---

## File Structure

**Create:**
- `.github/workflows/ci.yml` — PR + push-to-main quality gates (web + server jobs in parallel)
- `.github/workflows/deploy.yml` — push-to-main → vite build → staticrypt → deploy-pages
- `server/deploy/jarvis-backend.service` — systemd `--user` unit template
- `server/deploy/README.md` — install + verify procedure for the service unit

**Modify:**
- `web/vite.config.ts` — read `VITE_BASE` env var (default `/`) and pass to Vite's `base` config
- `web/README.md` — add Live URL section, password-rotation pointer, autostart pointer
- `README.md` (project root, if exists) — top-level pointer to the live URL
- `docs/superpowers/STATUS.md` — phase pointer + final-spec marker

**Untouched:** all spec-01/02/03 application code, test files, packages, server pipelines.

---

## Task 0: Branch + baseline

**Files:** none.

- [x] **Step 1: Already on branch `spec-04-deploy-and-gate` (created at brainstorm time).**

- [ ] **Step 2: Verify baseline tests still pass locally**

```bash
cd web && npm test -- --run
cd ../server && . .venv/bin/activate && pytest -q
```
Expected: 60/60 vitest, 58/58 pytest.

- [ ] **Step 3: No commit — sanity check only.**

---

## Task 1: Vite base path support

**Files:**
- Modify: `web/vite.config.ts`

The deploy workflow needs `VITE_BASE=/jarvis/` to rewrite asset URLs for GH Pages project-site path. Local dev / preview keep `/` default.

- [ ] **Step 1: Read current vite.config.ts** (already done in spec-03 work)

- [ ] **Step 2: Add `base` field**

```ts
import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  server: { port: 5173 },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    target: "es2022",
  },
  esbuild: {
    target: "es2022",
  },
});
```

- [ ] **Step 3: Verify default build is unchanged**

```bash
cd web && npm run build
```
Expected: 60/60 vitest still green; bundle still ~9 KB gzip JS; asset paths in `dist/index.html` start with `/assets/`.

- [ ] **Step 4: Verify VITE_BASE override works**

```bash
cd web && VITE_BASE=/jarvis/ npm run build
grep -o "/jarvis/assets/[^\"]*" dist/index.html | head -3
```
Expected: at least one match showing the prefixed path.

- [ ] **Step 5: Commit**

```bash
git add web/vite.config.ts
git commit -m "feat(web): honor VITE_BASE for GH Pages project-site path"
```

---

## Task 2: PR CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

Two jobs — `web` and `server` — run in parallel on `pull_request` and `push` to `main`.

- [ ] **Step 1: Write the workflow**

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]

jobs:
  web:
    name: web (lint, typecheck, test, build)
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
      - name: Typecheck
        run: npx tsc --noEmit
      - name: Lint
        run: npm run lint
      - name: Test
        run: npx vitest run
      - name: Build
        run: npm run build

  server:
    name: server (ruff, mypy, pytest)
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
      - name: Install
        run: pip install -e ".[dev]"
      - name: Lint
        run: ruff check .
      - name: Typecheck
        run: mypy
      - name: Test
        run: pytest -q
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: PR quality gates (web + server, parallel jobs)"
```

This workflow first runs against the PR that introduces it. Failures get fixed in subsequent task commits before merge.

---

## Task 3: Deploy workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Write the workflow**

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
    name: Build + encrypt
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: web/package-lock.json
      - name: Install
        run: npm ci
        working-directory: web
      - name: Build
        run: npm run build
        working-directory: web
        env:
          VITE_WS_URL: ws://localhost:8000/ws
          VITE_BASE: /jarvis/
      - name: Verify staticrypt secret
        env:
          STATICRYPT_PASSWORD: ${{ secrets.STATICRYPT_PASSWORD }}
        run: |
          if [ -z "$STATICRYPT_PASSWORD" ]; then
            echo "::error::STATICRYPT_PASSWORD repo secret is not set."
            echo "Configure: Settings → Secrets and variables → Actions → New repository secret"
            exit 1
          fi
      - name: Encrypt index.html
        env:
          STATICRYPT_PASSWORD: ${{ secrets.STATICRYPT_PASSWORD }}
        run: |
          npx -y staticrypt@^3 web/dist/index.html \
            -p "$STATICRYPT_PASSWORD" \
            --short \
            -d web/dist
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web/dist

  deploy:
    name: Publish to Pages
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: GH Pages deploy on push to main with staticrypt gate"
```

The workflow won't run until merged to `main` (no `pull_request` trigger). The first deploy will land on the spec-04 merge.

---

## Task 4: systemd --user service unit

**Files:**
- Create: `server/deploy/jarvis-backend.service`
- Create: `server/deploy/README.md`

- [ ] **Step 1: Write the unit**

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
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

- [ ] **Step 2: Write the install README**

````markdown
# Backend autostart (systemd --user)

A `systemd --user` unit that runs `uvicorn` on the laptop with on-failure
restart and start-at-login.

## Prerequisites

A working venv at `server/.venv/` with the package installed:

```bash
cd server
python3.12 -m venv .venv
.venv/bin/pip install -e .
```

## Install

```bash
mkdir -p ~/.config/systemd/user
cp server/deploy/jarvis-backend.service ~/.config/systemd/user/

# Adjust WorkingDirectory if jarvis lives somewhere other than ~/jarvis
sed -i "s|%h/jarvis|$PWD/..|g" ~/.config/systemd/user/jarvis-backend.service

systemctl --user daemon-reload
systemctl --user enable --now jarvis-backend.service
```

## Verify

```bash
systemctl --user status jarvis-backend
curl http://127.0.0.1:8000/health   # → 200 OK
journalctl --user -u jarvis-backend -f
```

## Persist across logout (optional)

Without this the service stops when you log out:

```bash
loginctl enable-linger "$USER"
```

## Stop / disable

```bash
systemctl --user stop jarvis-backend
systemctl --user disable jarvis-backend
```
````

- [ ] **Step 3: Commit**

```bash
git add server/deploy/jarvis-backend.service server/deploy/README.md
git commit -m "feat(server): systemd --user unit + install README for laptop autostart"
```

---

## Task 5: README pointers + STATUS update

**Files:**
- Modify: `web/README.md`
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Append to `web/README.md`**

Add a section before "Architecture":

```markdown
## Live deployment

Deployed at: **https://mhaegeman.github.io/jarvis/** (password-gated via staticrypt).

### Rotate the password

1. Settings → Secrets and variables → Actions → `STATICRYPT_PASSWORD` → Update
2. Re-run the **Deploy** workflow from the Actions tab (or push any commit to `main`).

### Backend autostart

See `server/deploy/README.md` for the systemd `--user` unit that keeps `uvicorn` running on the laptop.
```

- [ ] **Step 2: Update `docs/superpowers/STATUS.md`**

Mark spec-04 row in progress (Brainstorm + Plan ✅, Implement in progress).
Update Last action / Next action sections.

```markdown
**Last updated:** 2026-05-08 (spec-04 implementation in progress)

## Current Phase
**spec-04-deploy-and-gate · implementation (CI + deploy + service unit)**

## Macro Progress

| 4 | spec-04-deploy-and-gate | ✅ committed (f80d562) | ✅ committed (TODO) | ⏳ in progress | ⬜ | ⬜ | ⬜ |
```

(Replace the actual hashes when committing.)

- [ ] **Step 3: Commit**

```bash
git add web/README.md docs/superpowers/STATUS.md
git commit -m "docs(jarvis): live URL + autostart pointers; STATUS for spec-04"
```

---

## Task 6: Push the branch + open PR

**Files:** none.

- [ ] **Step 1: Push**

```bash
git push -u origin spec-04-deploy-and-gate
```

- [ ] **Step 2: Open PR via MCP** (orchestrator does this; not a CLI step).

PR description must include:
- Spec link
- Plan link
- Manual one-time setup steps from spec §6 — copy verbatim into the PR body so they aren't lost
- Notes that CI workflow runs on this PR (validates itself); deploy workflow only runs on merge

- [ ] **Step 3: Watch the CI run.** If `web` or `server` job fails, fix the underlying issue, push, repeat. The PR is the validation surface for `ci.yml`.

---

## Task 7: Post-merge verification (Architect, manual)

These steps cannot run in CI — they touch GitHub repo settings via the UI. Documented here so they're not forgotten.

- [ ] **A. Set repository secret** `STATICRYPT_PASSWORD`
- [ ] **B. Configure Pages source** = "GitHub Actions" (Settings → Pages → Source)
- [ ] **C. Add branch protection** for `main` requiring `web` and `server` checks
- [ ] **D. Merge spec-04 PR.** First Deploy run will land at `https://mhaegeman.github.io/jarvis/`.
- [ ] **E. Smoke the live site.** Unlock with password; HUD loads; demo banner appears (no laptop backend reachable from GH runners — expected).
- [ ] **F. Install backend service** on the laptop per `server/deploy/README.md`. Verify `curl http://127.0.0.1:8000/health` returns 200.
- [ ] **G. Open the live site from a Chromium browser on the laptop.** Confirm WS connects to `ws://localhost:8000/ws` and a full conversation works.

---

## Self-Review Notes

**Spec coverage:**
- §5.1 ci.yml → Task 2 ✅
- §5.2 deploy.yml → Task 3 ✅
- §5.3 service unit → Task 4 ✅
- §5.4 vite base path → Task 1 ✅
- §5.5 README updates → Task 5 ✅
- §6 manual setup → Task 7 (Architect-side, documented) ✅
- §7 testing → Task 0 baseline + Task 6 PR runs ci.yml + Task 7 manual deploy smoke ✅
- §8 acceptance → all gated by Tasks 6 & 7 ✅

**Placeholder scan:** `(TODO)` placeholder in Task 5 STATUS.md edit refers to the spec doc commit hash — fixed inline at commit time. No other placeholders.

**Type consistency:** N/A (no TypeScript types introduced).

**Risk:** GH Actions runners come pre-loaded with Node 20+ and Python 3.12, so `setup-node`/`setup-python` are configuration only. If a runner image changes default versions in the future, the workflows pin the version explicitly.

# Auth Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the client-side passphrase stub with a real `POST /auth/login` backend endpoint that validates an argon2-hashed passphrase and returns a session token stored in `sessionStorage`.

**Architecture:** The backend adds one new FastAPI route that reads `JARVIS_PASSPHRASE_HASH` (an argon2id hash) from the environment, verifies the submitted passphrase with `argon2-cffi`, and returns `{ "token": "<random-token>" }`. The frontend replaces the `handleSubmit` local check with a `fetch` call, and stores the returned token in `sessionStorage`. For this milestone, the token is not verified on the WebSocket endpoint (that is future scope); the goal is to make login real.

**Tech Stack:** Python `argon2-cffi`, FastAPI, TypeScript `fetch` API, `sessionStorage`

**Branch:** `feat/auth-login` (branch off `main`)

---

### Environment setup

```bash
cd /home/user/jarvis
git fetch origin main
git checkout -b feat/auth-login origin/main
cd server
```

Run tests baseline before touching anything:
```bash
uv run --extra dev pytest -q
```
All tests must pass (baseline green).

---

### Task 1: Add argon2-cffi dependency

**Files:**
- Modify: `server/pyproject.toml`

- [ ] **Step 1: Add the dependency**

In `server/pyproject.toml`, add `argon2-cffi>=23.1` to the `dependencies` list (after `aiosqlite`):

```toml
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "websockets>=13",
  "pydantic>=2.9",
  "pydantic-settings>=2.5",
  "psutil>=5.9",
  "google-auth>=2.30",
  "google-auth-oauthlib>=1.2",
  "google-api-python-client>=2.140",
  "anthropic>=0.40,<1.0",
  "aiosqlite>=0.20",
  "argon2-cffi>=23.1",
]
```

- [ ] **Step 2: Install and verify**

```bash
cd /home/user/jarvis/server
uv sync --extra dev
python -c "from argon2 import PasswordHasher; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add server/pyproject.toml
git commit -m "build(auth): add argon2-cffi dependency"
```

---

### Task 2: Add `JARVIS_PASSPHRASE_HASH` to config

**Files:**
- Modify: `server/server/config.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_auth.py`:

```python
"""Tests for the POST /auth/login endpoint."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from server.config import Settings


def test_passphrase_hash_config_default_is_none() -> None:
    """JARVIS_PASSPHRASE_HASH is optional; defaults to None."""
    s = Settings()
    assert s.passphrase_hash is None
```

- [ ] **Step 2: Run the failing test**

```bash
cd /home/user/jarvis/server
uv run --extra dev pytest tests/test_auth.py::test_passphrase_hash_config_default_is_none -v
```
Expected: FAIL (AttributeError: passphrase_hash)

- [ ] **Step 3: Add field to Settings**

In `server/server/config.py`, add after `tts_voice`:

```python
    # Auth — passphrase hash (argon2id). Generate with:
    #   python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('yourphrase'))"
    passphrase_hash: str | None = Field(default=None, validation_alias="JARVIS_PASSPHRASE_HASH")
```

- [ ] **Step 4: Run the test — expect green**

```bash
uv run --extra dev pytest tests/test_auth.py::test_passphrase_hash_config_default_is_none -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/server/config.py server/tests/test_auth.py
git commit -m "feat(auth): add JARVIS_PASSPHRASE_HASH config field"
```

---

### Task 3: Implement `POST /auth/login` endpoint

**Files:**
- Modify: `server/server/main.py`
- Modify: `server/tests/test_auth.py`

The endpoint contract:
- `POST /auth/login` body: `{ "passphrase": "<string>" }`
- `200 OK` → `{ "token": "<32-hex-char random token>" }` when passphrase matches the hash
- `401 Unauthorized` → `{ "detail": "Invalid passphrase" }` on mismatch or wrong passphrase
- `503 Service Unavailable` → `{ "detail": "Auth not configured" }` when `JARVIS_PASSPHRASE_HASH` is unset

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_auth.py`:

```python
from server.main import app


@pytest.mark.asyncio
async def test_login_returns_503_when_no_hash_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """503 when JARVIS_PASSPHRASE_HASH is not set."""
    monkeypatch.setattr("server.main.settings", Settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/auth/login", json={"passphrase": "anything"})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_login_returns_401_on_wrong_passphrase(monkeypatch: pytest.MonkeyPatch) -> None:
    """401 on wrong passphrase when hash is configured."""
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    correct_hash = ph.hash("correctphrase123")
    monkeypatch.setattr("server.main.settings", Settings(JARVIS_PASSPHRASE_HASH=correct_hash))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/auth/login", json={"passphrase": "wrongpassphrase"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid passphrase"


@pytest.mark.asyncio
async def test_login_returns_token_on_correct_passphrase(monkeypatch: pytest.MonkeyPatch) -> None:
    """200 + token when passphrase matches the hash."""
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    correct_hash = ph.hash("correctphrase123")
    monkeypatch.setattr("server.main.settings", Settings(JARVIS_PASSPHRASE_HASH=correct_hash))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/auth/login", json={"passphrase": "correctphrase123"})
    assert r.status_code == 200
    body = r.json()
    assert "token" in body
    assert len(body["token"]) == 64  # 32 bytes hex = 64 chars
```

- [ ] **Step 2: Run the failing tests**

```bash
uv run --extra dev pytest tests/test_auth.py -v
```
Expected: 3 new tests FAIL (404 Not Found on /auth/login)

- [ ] **Step 3: Implement the endpoint**

In `server/server/main.py`:

Add imports at the top (after `from fastapi import FastAPI, WebSocket, WebSocketDisconnect`):
```python
import secrets

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel as _BaseModel
```

Add after the `health` route (before `_StarletteWSAdapter`):

```python
class _LoginRequest(_BaseModel):
    passphrase: str


@app.post("/auth/login")
async def auth_login(req: _LoginRequest) -> dict[str, str]:
    if settings.passphrase_hash is None:
        raise HTTPException(status_code=503, detail="Auth not configured")
    try:
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
    except ImportError:  # pragma: no cover
        raise HTTPException(status_code=503, detail="Auth not configured")
    ph = PasswordHasher()
    try:
        ph.verify(settings.passphrase_hash, req.passphrase)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid passphrase")
    token = secrets.token_hex(32)
    return {"token": token}
```

- [ ] **Step 4: Run tests — expect green**

```bash
uv run --extra dev pytest tests/test_auth.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 5: Run the full suite**

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check server/
uv run --extra dev mypy --strict server/
```
Expected: all pass, no errors

- [ ] **Step 6: Commit**

```bash
git add server/server/main.py server/tests/test_auth.py
git commit -m "feat(auth): POST /auth/login with argon2 verification"
```

---

### Task 4: Wire the frontend login form to `POST /auth/login`

**Files:**
- Modify: `web/src/ui/login/LoginPage.ts`

The frontend `handleSubmit` replaces the local stub check with a `fetch` call. If the backend is unreachable (demo mode), fall back to the existing local length check so the app still works offline.

- [ ] **Step 1: Write the failing frontend test**

Create `web/test/loginPage.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// We test the auth fetch logic in isolation by testing the helper directly.
// The helper is extracted from LoginPage.ts as a pure function.
import { attemptLogin } from "@/ui/login/attemptLogin";

describe("attemptLogin", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it("returns ok:true and stores token on 200", async () => {
    const token = "a".repeat(64);
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ token }), { status: 200 }),
    );
    const result = await attemptLogin("correctphrase123");
    expect(result.ok).toBe(true);
    expect(sessionStorage.getItem("jarvis_token")).toBe(token);
  });

  it("returns ok:false on 401", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Invalid passphrase" }), { status: 401 }),
    );
    const result = await attemptLogin("wrongpassphrase");
    expect(result.ok).toBe(false);
    expect(sessionStorage.getItem("jarvis_token")).toBeNull();
  });

  it("returns ok:true (offline fallback) when fetch throws", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError("Failed to fetch"));
    // Offline fallback: any passphrase ≥12 chars succeeds
    const result = await attemptLogin("offlinepassphrase");
    expect(result.ok).toBe(true);
  });

  it("offline fallback returns ok:false for short passphrase", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const result = await attemptLogin("short");
    expect(result.ok).toBe(false);
  });
});
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd /home/user/jarvis/web
npm run test -- loginPage --run 2>&1 | tail -20
```
Expected: FAIL (cannot find module `@/ui/login/attemptLogin`)

- [ ] **Step 3: Create `attemptLogin.ts`**

Create `web/src/ui/login/attemptLogin.ts`:

```typescript
const AUTH_URL = "/auth/login";
const MIN_LENGTH = 12;

export interface LoginResult {
  ok: boolean;
}

export async function attemptLogin(passphrase: string): Promise<LoginResult> {
  try {
    const res = await fetch(AUTH_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ passphrase }),
    });
    if (res.ok) {
      const { token } = (await res.json()) as { token: string };
      sessionStorage.setItem("jarvis_token", token);
      return { ok: true };
    }
    return { ok: false };
  } catch {
    // Backend unreachable (demo/offline mode) — fall back to length check
    return { ok: passphrase.length >= MIN_LENGTH };
  }
}
```

- [ ] **Step 4: Run the test — expect green**

```bash
npm run test -- loginPage --run 2>&1 | tail -20
```
Expected: 4 tests PASS

- [ ] **Step 5: Wire `attemptLogin` into `LoginPage.ts`**

In `web/src/ui/login/LoginPage.ts`:

At the top, add the import:
```typescript
import { attemptLogin } from "./attemptLogin";
```

Replace the `handleSubmit` function body (the block from `// TODO: replace with POST /auth/login` through `setTimeout(() => onSuccess(), 900);`) with:

```typescript
  async function handleSubmit(e: Event): Promise<void> {
    e.preventDefault();
    if (fieldState === "success") return;
    const val = pwEl.value;
    if (val.length < MIN_LENGTH) return;
    const result = await attemptLogin(val);
    if (!result.ok) {
      setFieldState("error");
      setTimeout(() => {
        if (fieldState === "error") {
          setFieldState("idle");
          pwEl.focus();
          pwEl.select();
        }
      }, 600);
      return;
    }
    setFieldState("success");
    setTimeout(() => onSuccess(), 900);
  }
```

Also update the event listener registration (it must now handle a Promise):
```typescript
  form.addEventListener("submit", (e) => { handleSubmit(e).catch(() => {}); });
```

Remove the old `form.addEventListener("submit", handleSubmit);` line.

- [ ] **Step 6: Type-check and build**

```bash
cd /home/user/jarvis/web
npm run build 2>&1 | tail -20
```
Expected: build succeeds, no TS errors

- [ ] **Step 7: Run full frontend test suite**

```bash
npm run test -- --run 2>&1 | tail -10
```
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
cd /home/user/jarvis
git add web/src/ui/login/attemptLogin.ts web/src/ui/login/LoginPage.ts web/test/loginPage.test.ts
git commit -m "feat(auth): wire frontend login form to POST /auth/login"
```

---

### Task 5: Push branch

```bash
git push -u origin feat/auth-login
```

**Merge order note:** Merge this branch second (after `feat/voice-dock-history`, before `feat/calendar-attendees`).

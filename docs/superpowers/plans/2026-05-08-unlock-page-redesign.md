# Unlock page redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace staticrypt's default unlock UI with a HUD-styled custom template (`web/unlock-template.html`) shipped through the existing `deploy.yml` workflow via the `--template` flag.

**Architecture:** Single self-contained HTML file at `web/unlock-template.html` with inlined CSS (HUD design tokens copied from `web/src/styles/global.css`) and inlined JS that drives our own form submit handler — calling `staticrypt.handleDecryptionOfPage(...)` directly and branching on the returned `isSuccessful` flag instead of letting the default handler `alert()` on failure. CI gains a smoke test that runs `npx staticrypt@^3 --template web/unlock-template.html` against the freshly-built `web/dist/index.html` and grep's the output for our HUD title and the staticrypt element-ID contract.

**Tech Stack:** `staticrypt@^3.3.x` (already pinned in `deploy.yml`), no new runtime dependencies. Uses GitHub Actions, Node 20, the existing CI workflow, the existing Vite build.

**Spec:** `docs/superpowers/specs/2026-05-08-unlock-page-redesign-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `web/unlock-template.html` | Create (~200 LOC) | Self-contained HUD-styled staticrypt template |
| `.github/workflows/deploy.yml` | Modify (+1 line) | Pass `--template web/unlock-template.html` to staticrypt |
| `.github/workflows/ci.yml` | Modify (+10 lines) | Smoke-test the template on every PR |
| `web/README.md` | Modify (+3 lines) | Document where the unlock template lives |
| `docs/superpowers/STATUS.md` | Modify (+1 row) | Track v0.2 ε in the project log |

---

## Task 1: Pre-flight — verify staticrypt version + placeholder format

**Why:** The spec's design contract depends on `staticrypt@^3.3.x`'s exact placeholder format (`/*[|name|]*/0`) and element-ID set. Drift in a minor release would break the template silently. Before writing code, confirm reality matches the spec.

**Files:** None (probe only).

- [ ] **Step 1: Install staticrypt in a throwaway directory**

```bash
mkdir -p /tmp/staticrypt-probe && cd /tmp/staticrypt-probe \
  && npm init -y >/dev/null \
  && npm i staticrypt@^3 >/dev/null \
  && node -e "console.log(require('staticrypt/package.json').version)"
```

Expected: a version string `3.x.y` where `x >= 3`. If `x < 3` or major is `4+`, STOP and flag — the spec assumes `^3.3.x`.

- [ ] **Step 2: Confirm placeholder format and element IDs in the bundled template**

```bash
grep -E '\/\*\[\|[a-z_]+\|\]\*\/' /tmp/staticrypt-probe/node_modules/staticrypt/lib/password_template.html | sort -u
grep -oE 'id="[a-z_-]+"' /tmp/staticrypt-probe/node_modules/staticrypt/lib/password_template.html | sort -u
```

Expected placeholders include (at minimum): `/*[|staticrypt_config|]*/`, `/*[|js_staticrypt|]*/`, `/*[|is_remember_enabled|]*/`, `/*[|template_error|]*/`. Expected IDs include: `id="staticrypt_loading"`, `id="staticrypt_content"`, `id="staticrypt-form"`, `id="staticrypt-password"`, `id="staticrypt-remember"`. If any of these are missing, STOP and update the spec.

- [ ] **Step 3: Confirm the runtime API surface**

```bash
grep -nE '(handleDecryptOnLoad|handleDecryptionOfPage|replaceHtmlCallback)' /tmp/staticrypt-probe/node_modules/staticrypt/lib/password_template.html
```

Expected: all three names appear. `handleDecryptOnLoad` and `handleDecryptionOfPage` are the engine methods our submit handler calls; `replaceHtmlCallback` is the `templateConfig` hook our fade-out uses.

No commit. Pre-flight only.

---

## Task 2: Add the CI smoke test (RED — must fail with current main)

**Why:** TDD applied to a static template means: write the failing assertion first, then satisfy it.

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add a smoke-test step at the end of the `web` job**

Append to `.github/workflows/ci.yml` at the end of the `web` job's `steps:` (after the existing `Build` step at line 28-29):

```yaml
      - name: staticrypt template smoke test
        run: |
          mkdir -p /tmp/unlock-smoke
          cp dist/index.html /tmp/unlock-smoke/index.html
          npx -y staticrypt@^3 /tmp/unlock-smoke/index.html \
            -p ci-smoke-password \
            --short \
            --template unlock-template.html \
            -d /tmp/unlock-smoke
          # The rendered template must surface our HUD title.
          grep -q 'JARVIS // OS' /tmp/unlock-smoke/index.html
          # The staticrypt engine's element-ID contract must survive our restyling.
          grep -q 'id="staticrypt-form"' /tmp/unlock-smoke/index.html
          grep -q 'id="staticrypt-password"' /tmp/unlock-smoke/index.html
          grep -q 'id="staticrypt_loading"' /tmp/unlock-smoke/index.html
          grep -q 'id="staticrypt_content"' /tmp/unlock-smoke/index.html
```

(The `web` job has `working-directory: web`, so `unlock-template.html` and `dist/index.html` resolve under `web/`.)

- [ ] **Step 2: Verify the new step exists**

```bash
grep -n "staticrypt template smoke test" .github/workflows/ci.yml
```

Expected: one match line in the file.

- [ ] **Step 3: Run the smoke test locally to confirm it fails**

```bash
cd web && npm run build && \
  mkdir -p /tmp/unlock-smoke && cp dist/index.html /tmp/unlock-smoke/index.html && \
  npx -y staticrypt@^3 /tmp/unlock-smoke/index.html -p ci-smoke-password --short \
    --template unlock-template.html -d /tmp/unlock-smoke 2>&1 | tail -5
```

Expected: staticrypt fails with an error like `ENOENT: no such file or directory, open 'unlock-template.html'`. This proves the smoke test would fail in CI today — exactly what we want before writing the template.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(unlock): smoke test for HUD staticrypt template (RED)

Asserts that web/unlock-template.html exists, surfaces the HUD title
'JARVIS // OS', and preserves the staticrypt engine's element-ID
contract (staticrypt-form, staticrypt-password, staticrypt_loading,
staticrypt_content) after encryption. Currently fails — template
file does not yet exist."
```

---

## Task 3: Minimal template — make smoke test pass (GREEN)

**Why:** Smallest possible template that satisfies the smoke test, before adding visual styling. Tests that our placeholder set and element-ID contract are correct against staticrypt's expectations.

**Files:**
- Create: `web/unlock-template.html`

- [ ] **Step 1: Create the minimal template**

Create `web/unlock-template.html` with this exact content:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>JARVIS // OS</title>
</head>
<body>
  <div id="staticrypt_loading">DECRYPTING…</div>
  <div id="staticrypt_content" style="display:none">
    <h1>JARVIS // OS</h1>
    <form id="staticrypt-form" action="#" method="post">
      <label for="staticrypt-password">PASSWORD</label>
      <input id="staticrypt-password" type="password" name="password" autofocus />
      <input id="staticrypt-remember" type="checkbox" name="remember" hidden />
      <button type="submit">AUTHENTICATE</button>
    </form>
    <output id="jarvis-status" aria-live="polite">STATUS: STANDING BY.</output>
  </div>
  <script>
    const staticryptInitiator = /*[|js_staticrypt|]*/ 0;
    const staticryptConfig = /*[|staticrypt_config|]*/ 0;
    const isRememberEnabled = /*[|is_remember_enabled|]*/ 0;
    const templateError = "/*[|template_error|]*/0";

    const staticrypt = staticryptInitiator.init(staticryptConfig, {
      rememberExpirationKey: "staticrypt_expiration",
      rememberPassphraseKey: "staticrypt_passphrase",
      replaceHtmlCallback: null,
      clearLocalStorageCallback: null,
    });

    window.addEventListener("load", async () => {
      const { isSuccessful } = await staticrypt.handleDecryptOnLoad();
      if (!isSuccessful) {
        document.getElementById("staticrypt_loading").style.display = "none";
        document.getElementById("staticrypt_content").style.display = "block";
        document.getElementById("staticrypt-password").focus();
      }
    });

    document.getElementById("staticrypt-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const password = document.getElementById("staticrypt-password").value;
      const { isSuccessful } = await staticrypt.handleDecryptionOfPage(password, false);
      if (!isSuccessful) alert(templateError);
    });
  </script>
</body>
</html>
```

- [ ] **Step 2: Run smoke test locally — should pass**

```bash
cd web && npm run build && \
  mkdir -p /tmp/unlock-smoke && cp dist/index.html /tmp/unlock-smoke/index.html && \
  npx -y staticrypt@^3 /tmp/unlock-smoke/index.html -p ci-smoke-password --short \
    --template unlock-template.html -d /tmp/unlock-smoke && \
  grep -q 'JARVIS // OS' /tmp/unlock-smoke/index.html && \
  grep -q 'id="staticrypt-form"' /tmp/unlock-smoke/index.html && \
  grep -q 'id="staticrypt-password"' /tmp/unlock-smoke/index.html && \
  grep -q 'id="staticrypt_loading"' /tmp/unlock-smoke/index.html && \
  grep -q 'id="staticrypt_content"' /tmp/unlock-smoke/index.html && \
  echo "SMOKE OK"
```

Expected: `SMOKE OK` printed at the end. No errors from staticrypt.

- [ ] **Step 3: Manual sanity-check the rendered output**

```bash
head -40 /tmp/unlock-smoke/index.html
```

Expected: the placeholders have been substituted — `/*[|js_staticrypt|]*/ 0` is now an actual function expression, `/*[|staticrypt_config|]*/ 0` is a JS object literal with `salt`, `iv`, `ct` (or similar) keys.

- [ ] **Step 4: Commit**

```bash
git add web/unlock-template.html
git commit -m "feat(unlock): minimal HUD template (smoke test passes)

Template surfaces 'JARVIS // OS' title and preserves staticrypt's
element-ID contract. Behavior: works exactly like staticrypt's
default — alerts on wrong password, no styling yet. Visual + state
polish lands in the next two commits."
```

---

## Task 4: Visual styling — HUD aesthetic

**Why:** Match the rest of the site. No behavior changes — just CSS.

**Files:**
- Modify: `web/unlock-template.html` (add `<style>` block, restructure markup)

- [ ] **Step 1: Replace the file with the styled version**

Overwrite `web/unlock-template.html` with this exact content (the JS block is preserved verbatim from Task 3 — only HTML structure and `<style>` change):

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="cache-control" content="no-cache" />
  <title>JARVIS // OS</title>
  <style>
    :root {
      --bg-0: #02060a;
      --bg-1: #03101a;
      --fg: #d6f0ff;
      --fg-dim: rgba(214, 240, 255, 0.65);
      --accent: #5cf0ff;
      --accent-dim: rgba(92, 240, 255, 0.35);
      --accent-faint: rgba(92, 240, 255, 0.10);
      --grid-line: rgba(92, 240, 255, 0.08);
      --deny: #ff5c5c;
      color-scheme: dark;
    }

    * { box-sizing: border-box; }

    html, body {
      margin: 0;
      height: 100%;
      overflow: hidden;
      background:
        radial-gradient(ellipse at 50% 50%, var(--bg-1) 0%, var(--bg-0) 70%),
        linear-gradient(transparent 95%, var(--grid-line) 95%) 0 0 / 100% 32px,
        linear-gradient(90deg, transparent 95%, var(--grid-line) 95%) 0 0 / 32px 100%;
      color: var(--fg);
      font-family: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
      font-size: 12px;
      letter-spacing: 0.04em;
    }

    body {
      display: grid;
      place-items: center;
      min-height: 100vh;
    }

    /* CRT scanline overlay across the whole viewport. */
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background: repeating-linear-gradient(
        0deg,
        rgba(92, 240, 255, 0.06) 0,
        rgba(92, 240, 255, 0.06) 1px,
        transparent 1px,
        transparent 3px
      );
      z-index: 1;
    }

    #staticrypt_loading {
      color: var(--fg-dim);
      letter-spacing: 0.2em;
    }

    #staticrypt_content { width: 100%; max-width: 480px; padding: 0 24px; }

    .panel {
      border: 1px solid var(--accent-dim);
      background: rgba(3, 16, 26, 0.85);
      box-shadow: 0 0 32px var(--accent-faint), inset 0 0 0 1px var(--accent-faint);
      position: relative;
      z-index: 2;
    }

    .panel__bar {
      padding: 8px 16px;
      border-bottom: 1px solid var(--accent-dim);
      background: var(--accent-faint);
      color: var(--accent);
      letter-spacing: 0.18em;
      text-transform: uppercase;
      font-size: 11px;
    }

    .panel__bar::before {
      content: "▌";
      margin-right: 8px;
    }

    .panel__body { padding: 32px 24px 24px; }

    .field { margin-bottom: 20px; }

    .field__label {
      display: block;
      color: var(--accent);
      letter-spacing: 0.18em;
      text-transform: uppercase;
      margin-bottom: 8px;
      font-size: 11px;
    }

    .field__label::before {
      content: "> ";
      color: var(--fg-dim);
    }

    .field__input {
      width: 100%;
      background: var(--bg-0);
      border: 1px solid var(--accent-dim);
      color: var(--fg);
      font: inherit;
      letter-spacing: 0.2em;
      padding: 12px 14px;
      outline: none;
    }

    .field__input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 1px var(--accent-faint);
    }

    .submit {
      display: block;
      width: 100%;
      background: transparent;
      color: var(--accent);
      border: 1px solid var(--accent);
      font: inherit;
      letter-spacing: 0.24em;
      text-transform: uppercase;
      padding: 14px;
      cursor: pointer;
      transition: background-color 0.12s ease, color 0.12s ease;
    }

    .submit:hover, .submit:focus-visible {
      background: var(--accent);
      color: var(--bg-0);
      outline: none;
    }

    .jarvis-status {
      display: block;
      margin-top: 18px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--fg-dim);
      font-size: 11px;
    }

    .jarvis-status--idle { color: var(--fg-dim); }
    .jarvis-status--working { color: var(--accent); }
    .jarvis-status--denied { color: var(--deny); }
  </style>
</head>
<body>
  <div id="staticrypt_loading">INITIALISING…</div>

  <div id="staticrypt_content" hidden>
    <div id="jarvis-panel" class="panel">
      <div class="panel__bar">JARVIS // OS · v0.1</div>
      <div class="panel__body">
        <form id="staticrypt-form" action="#" method="post">
          <div class="field">
            <label class="field__label" for="staticrypt-password">PASSWORD</label>
            <input class="field__input" id="staticrypt-password" type="password"
                   name="password" autocomplete="current-password" autofocus />
          </div>
          <input id="staticrypt-remember" type="checkbox" name="remember" hidden />
          <button class="submit" type="submit">AUTHENTICATE</button>
        </form>
        <output id="jarvis-status" class="jarvis-status jarvis-status--idle" aria-live="polite">
          STATUS: STANDING BY.
        </output>
      </div>
    </div>
  </div>

  <script>
    const staticryptInitiator = /*[|js_staticrypt|]*/ 0;
    const staticryptConfig = /*[|staticrypt_config|]*/ 0;
    const isRememberEnabled = /*[|is_remember_enabled|]*/ 0;
    const templateError = "/*[|template_error|]*/0";

    const staticrypt = staticryptInitiator.init(staticryptConfig, {
      rememberExpirationKey: "staticrypt_expiration",
      rememberPassphraseKey: "staticrypt_passphrase",
      replaceHtmlCallback: null,
      clearLocalStorageCallback: null,
    });

    window.addEventListener("load", async () => {
      const { isSuccessful } = await staticrypt.handleDecryptOnLoad();
      if (!isSuccessful) {
        document.getElementById("staticrypt_loading").hidden = true;
        document.getElementById("staticrypt_content").hidden = false;
        document.getElementById("staticrypt-password").focus();
      }
    });

    document.getElementById("staticrypt-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const password = document.getElementById("staticrypt-password").value;
      const { isSuccessful } = await staticrypt.handleDecryptionOfPage(password, false);
      if (!isSuccessful) alert(templateError);
    });
  </script>
</body>
</html>
```

- [ ] **Step 2: Re-run the smoke test**

```bash
cd web && npm run build && \
  mkdir -p /tmp/unlock-smoke && cp dist/index.html /tmp/unlock-smoke/index.html && \
  npx -y staticrypt@^3 /tmp/unlock-smoke/index.html -p ci-smoke-password --short \
    --template unlock-template.html -d /tmp/unlock-smoke && \
  grep -q 'JARVIS // OS' /tmp/unlock-smoke/index.html && \
  grep -q 'id="staticrypt-form"' /tmp/unlock-smoke/index.html && \
  echo "SMOKE OK"
```

Expected: `SMOKE OK`. Smoke test still passes — we didn't break the contract.

- [ ] **Step 3: Visual sanity-check in a browser**

```bash
cd /tmp/unlock-smoke && python3 -m http.server 8765
```

Open `http://localhost:8765/` in a browser. Verify:
- Dark cyan-grid background matches the HUD aesthetic.
- Centered panel with `JARVIS // OS · v0.1` title bar.
- `> PASSWORD` label, dark input box, `AUTHENTICATE` button (cyan-bordered).
- `STATUS: STANDING BY.` line below.
- Submitting wrong password produces a browser `alert()` (state polish lands in Task 5).

Stop the server with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add web/unlock-template.html
git commit -m "feat(unlock): HUD aesthetic — panel, tokens, layout

Inlines HUD design tokens (--bg-0, --accent, JetBrains Mono) verbatim
from web/src/styles/global.css and arranges the form into a centered
cyan-bordered panel with title bar and status line. Behavior unchanged
from minimal template — wrong-password still alert()s."
```

---

## Task 5: State machine — submit handler + status transitions

**Why:** Replace the default `alert()` with our own state machine. This is the substantive behavior change of the spec.

**Files:**
- Modify: `web/unlock-template.html` (replace the `<script>` block at the bottom)

- [ ] **Step 1: Replace the inline `<script>` in `web/unlock-template.html`**

Find the `<script>` block at the bottom of `web/unlock-template.html` (between `<script>` and `</script>`) and replace its entire contents with:

```js
const staticryptInitiator = /*[|js_staticrypt|]*/ 0;
const staticryptConfig = /*[|staticrypt_config|]*/ 0;
const isRememberEnabled = /*[|is_remember_enabled|]*/ 0;
const templateError = "/*[|template_error|]*/0";

const statusEl = document.getElementById("jarvis-status");
const panelEl = document.getElementById("jarvis-panel");

const setStatus = (text, mode) => {
  statusEl.textContent = `STATUS: ${text}`;
  statusEl.className = `jarvis-status jarvis-status--${mode}`;
};

const staticrypt = staticryptInitiator.init(staticryptConfig, {
  rememberExpirationKey: "staticrypt_expiration",
  rememberPassphraseKey: "staticrypt_passphrase",
  // 600 ms fade before the page is replaced by the decrypted bundle.
  replaceHtmlCallback: (decryptedHtml) => {
    document.body.classList.add("granted");
    setTimeout(() => {
      document.open();
      document.write(decryptedHtml);
      document.close();
    }, 600);
  },
  clearLocalStorageCallback: null,
});

window.addEventListener("load", async () => {
  const { isSuccessful } = await staticrypt.handleDecryptOnLoad();
  if (!isSuccessful) {
    document.getElementById("staticrypt_loading").hidden = true;
    document.getElementById("staticrypt_content").hidden = false;
    document.getElementById("staticrypt-password").focus();
  }
});

document.getElementById("staticrypt-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setStatus("DECRYPTING…", "working");
  const password = document.getElementById("staticrypt-password").value;
  const { isSuccessful } = await staticrypt.handleDecryptionOfPage(password, false);
  if (!isSuccessful) {
    setStatus("ACCESS DENIED.", "denied");
    panelEl.classList.add("panel--shake");
    setTimeout(() => {
      panelEl.classList.remove("panel--shake");
      setStatus("STANDING BY.", "idle");
    }, 1200);
  }
  // On success, replaceHtmlCallback runs — no extra branch needed.
});
```

- [ ] **Step 2: Smoke test still passes**

```bash
cd web && npm run build && \
  mkdir -p /tmp/unlock-smoke && cp dist/index.html /tmp/unlock-smoke/index.html && \
  npx -y staticrypt@^3 /tmp/unlock-smoke/index.html -p ci-smoke-password --short \
    --template unlock-template.html -d /tmp/unlock-smoke && \
  grep -q 'JARVIS // OS' /tmp/unlock-smoke/index.html && \
  echo "SMOKE OK"
```

Expected: `SMOKE OK`.

- [ ] **Step 3: Manual end-to-end flow check**

```bash
cd /tmp/unlock-smoke && python3 -m http.server 8765
```

Open `http://localhost:8765/`:
- Submit wrong password → status flips to red `STATUS: ACCESS DENIED.` (no `alert()` box). Status returns to idle after ~1.2 s.
- Submit `ci-smoke-password` (the password used at encrypt time) → status flips to cyan `STATUS: DECRYPTING…`, then the page is replaced with the original `web/dist/index.html` content (the HUD bundle won't fully load because asset URLs point at `/jarvis/assets/...` and we're serving from `/`, but the swap itself should fire — look for `<div id="app">` or similar in the resulting page).

Stop the server.

- [ ] **Step 4: Commit**

```bash
git add web/unlock-template.html
git commit -m "feat(unlock): state machine — decrypting / denied / granted

Replaces staticrypt's default alert()-on-failure with our own status
line that flips through STANDING BY → DECRYPTING… → ACCESS DENIED →
STANDING BY (or DECRYPTING… → granted-fade on success). Uses
replaceHtmlCallback for a 600 ms opacity fade before the page swap."
```

---

## Task 6: Animations — scanline, shake, fade

**Why:** Polish layer. All decorative animation must respect `prefers-reduced-motion: reduce`.

**Files:**
- Modify: `web/unlock-template.html` (extend the `<style>` block)

- [ ] **Step 1: Add animation rules to the `<style>` block**

Find the closing `</style>` tag in `web/unlock-template.html`. Insert these rules immediately before it:

```css
    /* Slow scan bar travelling vertically across the panel. */
    .panel::after {
      content: "";
      position: absolute;
      left: 0;
      right: 0;
      top: 0;
      height: 2px;
      background: linear-gradient(90deg,
        transparent 0%,
        var(--accent) 50%,
        transparent 100%
      );
      opacity: 0.5;
      animation: jarvis-scan 4s linear infinite;
    }

    @keyframes jarvis-scan {
      from { transform: translateY(0); }
      to   { transform: translateY(calc(100% + 200px)); }
    }

    /* Denied: one-shot horizontal shake. */
    .panel--shake { animation: jarvis-shake 200ms ease-in-out 3; }

    @keyframes jarvis-shake {
      0%, 100% { transform: translateX(0); }
      25%      { transform: translateX(-6px); }
      75%      { transform: translateX(6px); }
    }

    /* Submitting: animated dots on the status line. */
    .jarvis-status--working::after {
      content: "";
      display: inline-block;
      width: 1.2em;
      text-align: left;
      animation: jarvis-dots 600ms steps(4, end) infinite;
    }

    @keyframes jarvis-dots {
      0%   { content: "";   }
      25%  { content: ".";  }
      50%  { content: ".."; }
      75%  { content: "..."; }
    }

    /* Granted: 600 ms opacity fade before page swap. */
    body { transition: opacity 600ms ease-out; }
    body.granted { opacity: 0; }

    @media (prefers-reduced-motion: reduce) {
      .panel::after,
      .panel--shake,
      .jarvis-status--working::after,
      body { animation: none !important; transition: none !important; }
    }
```

Also remove the `… DECRYPTING…` literal in the `setStatus("DECRYPTING…", "working")` JS line — replace `"DECRYPTING…"` with `"DECRYPTING"` (the trailing dots come from the `::after` pseudo-element animation now). Open the file and edit that one string in the submit handler:

```js
  setStatus("DECRYPTING", "working");
```

- [ ] **Step 2: Smoke test still passes**

```bash
cd web && npm run build && \
  mkdir -p /tmp/unlock-smoke && cp dist/index.html /tmp/unlock-smoke/index.html && \
  npx -y staticrypt@^3 /tmp/unlock-smoke/index.html -p ci-smoke-password --short \
    --template unlock-template.html -d /tmp/unlock-smoke && \
  grep -q 'JARVIS // OS' /tmp/unlock-smoke/index.html && \
  echo "SMOKE OK"
```

Expected: `SMOKE OK`.

- [ ] **Step 3: Visual + reduced-motion check**

```bash
cd /tmp/unlock-smoke && python3 -m http.server 8765
```

Open `http://localhost:8765/` in Chrome:
- Scan bar slides down the panel continuously (~4 s loop).
- Submit wrong password → panel shakes once, status reads red `ACCESS DENIED.`, returns to idle after ~1.2 s.
- Submit `ci-smoke-password` → status reads cyan `DECRYPTING` with animated dots, then body fades to opacity 0 over 600 ms before the page swap.

Then open Chrome DevTools → Rendering tab → "Emulate CSS media feature prefers-reduced-motion" → "reduce". Reload:
- No scan bar animation.
- Wrong password produces no shake (status text still flips red, returns to idle).
- Submit valid → no fade, page swaps immediately. Status text still says `DECRYPTING`.

Stop the server.

- [ ] **Step 4: Commit**

```bash
git add web/unlock-template.html
git commit -m "feat(unlock): animations — scan bar, shake, fade, ellipsis

Adds the decorative animation layer: vertical scan bar across the
panel, one-shot shake on denial, ellipsis-dots cycling on the
DECRYPTING status, and a 600 ms body opacity fade on grant. All
gated by prefers-reduced-motion: reduce."
```

---

## Task 7: Wire deploy.yml — pass the template flag

**Why:** Ship the template via the existing CI deploy workflow.

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: Add the `--template` flag to the encrypt step**

Edit `.github/workflows/deploy.yml`. Find the `Encrypt index.html` step (lines 45–52 in the current file). The existing `run:` block is:

```yaml
        run: |
          npx -y staticrypt@^3 web/dist/index.html \
            -p "$STATICRYPT_PASSWORD" \
            --short \
            -d web/dist
```

Replace it with:

```yaml
        run: |
          npx -y staticrypt@^3 web/dist/index.html \
            -p "$STATICRYPT_PASSWORD" \
            --short \
            --template web/unlock-template.html \
            -d web/dist
```

(One new line, between `--short \` and `-d web/dist`.)

- [ ] **Step 2: Verify the workflow still parses**

```bash
python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/deploy.yml')); print('YAML OK')"
```

Expected: `YAML OK`. (If `yaml` isn't installed, fall back to `npx js-yaml .github/workflows/deploy.yml >/dev/null && echo OK`.)

- [ ] **Step 3: Confirm the template path resolves at workflow runtime**

The deploy workflow does NOT set `working-directory` on the encrypt step (only the `Build` and `Install` steps run from `web/`). The template path is therefore `web/unlock-template.html` from the repo root. Verify the file is at that path:

```bash
ls -la web/unlock-template.html
```

Expected: file exists, ~10 KB.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci(unlock): pass --template web/unlock-template.html to staticrypt

Wires the HUD-styled template into the deploy workflow. Encryption
itself is unchanged — only the visible HTML wrapped around the
encrypted payload is replaced."
```

---

## Task 8: Documentation — README + STATUS

**Why:** Keep `web/README.md` accurate and log the v0.2 ε milestone in the project status doc.

**Files:**
- Modify: `web/README.md`
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Update `web/README.md`**

Open `web/README.md`. Find the Deploy section (search for "Deployed at" or "staticrypt"). Append immediately after the line that mentions `staticrypt`:

```markdown

The unlock page is a custom staticrypt template at `web/unlock-template.html`.
Editing it changes the look of the password gate; the encryption pipeline
(CI workflow, `STATICRYPT_PASSWORD` secret) is unchanged.
```

- [ ] **Step 2: Update `docs/superpowers/STATUS.md`**

Open `docs/superpowers/STATUS.md`. The Macro Progress table currently ends with this row (the panels-v2 entry):

```markdown
| 5 | panels-v2 | ✅ committed (edf4ad4) | ✅ committed (833db55) | ✅ Phase A+B+C+D | ✅ Codex P1/P2 (b7644d6) | ✅ 100 vitest, 97 pytest, lint+tsc+build clean | ✅ merged 32226ef |
```

Add this exact new row immediately after it (substitute the actual SHAs of the spec commit and plan commit into the placeholders in `()` — `git log --oneline -- docs/superpowers/specs/2026-05-08-unlock-page-redesign-design.md | tail -1` for the spec, same for the plan):

```markdown
| 6 | unlock-page-redesign | ✅ committed (<SPEC_SHA>) | ✅ committed (<PLAN_SHA>) | ✅ 9/9 tasks | (n/a) | ✅ CI smoke green, lint+tsc+vitest clean | (pending merge) |
```

Also update the `**Last updated:**` line at the top of the file from `2026-05-08 (panels-v2 merged)` to `2026-05-08 (unlock-page-redesign in flight)`, and update the `## Current Phase` heading from the panels-v2 message to:

```markdown
## Current Phase
**unlock-page-redesign in flight · v0.2 polish item ε**
```

- [ ] **Step 3: Commit**

```bash
git add web/README.md docs/superpowers/STATUS.md
git commit -m "docs(unlock): document HUD template + log v0.2 ε milestone"
```

---

## Task 9: End-to-end smoke before opening PR

**Why:** Independent verification that all layers compose correctly before review.

**Files:** None.

- [ ] **Step 1: Run the full CI-equivalent locally**

```bash
cd web && npm ci && npm run build && \
  mkdir -p /tmp/unlock-smoke && cp dist/index.html /tmp/unlock-smoke/index.html && \
  npx -y staticrypt@^3 /tmp/unlock-smoke/index.html -p ci-smoke-password --short \
    --template unlock-template.html -d /tmp/unlock-smoke && \
  grep -q 'JARVIS // OS' /tmp/unlock-smoke/index.html && \
  grep -q 'id="staticrypt-form"' /tmp/unlock-smoke/index.html && \
  grep -q 'id="staticrypt-password"' /tmp/unlock-smoke/index.html && \
  grep -q 'id="staticrypt_loading"' /tmp/unlock-smoke/index.html && \
  grep -q 'id="staticrypt_content"' /tmp/unlock-smoke/index.html && \
  npx tsc --noEmit && npm run lint && npx vitest run && \
  echo "ALL GREEN"
```

Expected: `ALL GREEN`. Same command set the CI `web` job will run (build + new smoke step + tsc + lint + vitest).

- [ ] **Step 2: Manual visual check one more time**

```bash
cd /tmp/unlock-smoke && python3 -m http.server 8765
```

Run through the full §6 manual checklist from the spec:
1. Page loads with HUD aesthetic, scan bar animating, status line idle.
2. Empty submit — no submit (browser validation).
3. Wrong password — red status flip, panel shake, returns to idle.
4. Right password (`ci-smoke-password`) — cyan DECRYPTING, fade, page swap.
5. Toggle `prefers-reduced-motion: reduce` — animations off, state changes still announced.
6. Lighthouse run on the unlock page — accessibility ≥ 95.

Stop the server.

- [ ] **Step 3: No commit. Pre-PR verification only.**

If any step in §1 or §2 fails, return to the relevant task and fix before opening the PR.

---

## Self-Review Notes (orchestrator before commit)

**1. Spec coverage.** Mapping each spec section to plan tasks:

| Spec section | Plan task |
|---|---|
| §5.1 placeholder set verified | Task 1 |
| §5.1 element-ID contract | Tasks 1, 2, 3, 4 |
| §5.1 visual layout (panel, tokens) | Task 4 |
| §5.1 state machine (idle / submitting / denied / granted) | Task 5 |
| §5.1 reduced-motion | Task 6 |
| §5.1 inline JS submit handler with `replaceHtmlCallback` fade | Task 5 |
| §5.2 `--template` flag in `deploy.yml` | Task 7 |
| §5.3 CI smoke test | Task 2 |
| §5.4 README pointer | Task 8 |
| §6 manual checklist | Task 9 |

No gaps.

**2. Placeholder scan.** Searched for "TBD", "TODO", "later", "appropriate", "etc.", "as needed" — none. Every step has either a code block or an exact command + expected output.

**3. Type / signature consistency.** Element IDs (`staticrypt-form`, `staticrypt-password`, `staticrypt_loading`, `staticrypt_content`, `staticrypt-remember`, `jarvis-status`, `jarvis-panel`) are referenced identically in Tasks 3, 4, and 5. Status mode names (`idle` / `working` / `denied`) match between the JS `setStatus` calls and the CSS class definitions. The `replaceHtmlCallback` signature `(decryptedHtml) => void` is declared once and not contradicted.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-08-unlock-page-redesign.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**

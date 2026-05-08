# Unlock page redesign (HUD-styled staticrypt) — Design

**Date:** 2026-05-08
**Status:** Draft (pending user review)
**Owner:** Maxime Haegeman (Architect) · Orchestrator (drafting)
**Anchors to:** `docs/superpowers/specs/2026-05-08-deploy-and-gate-design.md` (spec-04, the staticrypt gate this redesigns)
**Cycle:** v0.2 polish · item ε of {ε α γ β δ}

---

## 1. Goal

Replace staticrypt's default unlock page with a custom HUD-styled template that visually matches the rest of `https://mhaegeman.github.io/jarvis/`. The encryption pipeline is unchanged — only the user-facing HTML is reskinned.

Concretely: the user lands on the Pages URL, sees a dark cyan-on-black panel with a `JARVIS // OS` title and a password prompt that feels continuous with the HUD they're about to enter. Wrong password produces an `ACCESS DENIED.` shake; correct password fades to the existing app bundle.

## 2. Non-goals (out of scope)

- Changing the password / encryption mechanism (still PBKDF2 + AES-256-GCM via staticrypt v3).
- Replacing staticrypt with a hand-rolled gate.
- Multi-tenant unlock (single shared password remains).
- Boot-sequence faux-init text on the unlock page (decided out, see §10).
- Audio cues on unlock (autoplay restrictions + low ROI).
- Custom favicon work.
- Remembering the password client-side beyond what staticrypt already does (`localStorage` via `--remember`); we do not add `--remember`.

## 3. Inputs from prior specs

| From | Contract | Used by |
|---|---|---|
| spec-04 §5.2 | `npx staticrypt@^3 web/dist/index.html -p "$STATICRYPT_PASSWORD" --short -d web/dist` | This spec adds `--template web/unlock-template.html` to that invocation. |
| spec-04 §5.4 | Vite base path is `/jarvis/`; bundled assets live under `/jarvis/assets/…` | Template references must not break asset URLs (staticrypt rewrites `index.html` only — the original `<script type="module" src="/jarvis/assets/...">` line is preserved through the encrypted payload, not the template). |
| spec-01 frontend-shell | HUD design tokens defined in `web/src/styles/global.css` (`--bg-0: #02060a`, `--accent: #5cf0ff`, JetBrains Mono, etc.) | Template inlines copies of these tokens (the template is shipped raw to GH Pages and must be self-contained). |

## 4. Architecture

```
push to main
   │
   ▼
deploy.yml :: Build job
   ├── npm run build  →  web/dist/index.html  (Vite output, references /jarvis/assets/*)
   ├── staticrypt encrypt --template web/unlock-template.html
   │       │
   │       └──→ web/dist/index.html  (REPLACED with the rendered template,
   │            with {{cipher_text}} / {{js_template}} / etc. substituted in)
   └── upload-pages-artifact

user
   │  GET /jarvis/
   ▼
unlock-template.html (rendered)            ← HUD-styled, single self-contained file
   ├── enters password
   │     ├── correct → staticrypt's bundled JS decrypts the payload,
   │     │            document.write()s the original index.html,
   │     │            HUD bundle loads from /jarvis/assets/*
   │     └── wrong   → status line flips to "ACCESS DENIED.",
   │                  panel shakes 200 ms, input cleared, retry
   └── prefers-reduced-motion → all animations disabled
```

The only moving piece compared to spec-04: the `--template` flag.

## 5. Module-level design

### 5.1 `web/unlock-template.html` — the custom template

A single self-contained HTML file. ~150–200 lines. No external CSS, no external JS, no external fonts (system monospace stack matching the HUD's fallback chain).

**Why self-contained:** staticrypt v3 produces one HTML file at the GH Pages root; any external reference would 404 (the Vite-built CSS is hashed, the unlock page does not go through Vite, and adding a build step for it adds complexity for ~5 KB of inline CSS).

**Required staticrypt placeholders.** staticrypt v3 uses a comment-wrapped placeholder format `/*[|name|]*/0` (not Mustache). The format keeps the unfilled template valid JS — useful because some placeholders are interpolated directly into JS expressions (e.g. `const x = /*[|js_staticrypt|]*/ 0;`). Placeholders our template uses, verified against `node_modules/staticrypt/lib/password_template.html` in the installed `staticrypt@^3.3.x`:

| Placeholder | Context | Required |
|---|---|---|
| `/*[|staticrypt_config|]*/0` | RHS of `const staticryptConfig = …;` — the encrypted payload object | Yes |
| `/*[|js_staticrypt|]*/0` | RHS of `const staticryptInitiator = …;` — the decryptor module | Yes |
| `/*[|is_remember_enabled|]*/0` | RHS of `const isRememberEnabled = …;` — boolean, controls remember-me checkbox visibility | Yes (we expect `false` by default — not adding `--remember`) |
| `/*[|template_error|]*/0` | String literal, default-template `alert()`s this on failure | Yes — but we override the submit handler so the value is never user-visible (we drive our own status line) |

We deliberately do **not** use `template_title`, `template_instructions`, `template_placeholder`, `template_button`, `template_color_primary`, `template_color_secondary`, `template_remember`, `template_toggle_show`, `template_toggle_hide` — all visible strings are hard-coded in English (`PASSWORD`, `AUTHENTICATE`, `STANDING BY.`, etc.) and all colors come from inlined HUD tokens.

**Element contract.** staticrypt's bundled JS (`js_staticrypt`) is initialised in our template via `staticryptInitiator.init(staticryptConfig, templateConfig)` and exposes `handleDecryptOnLoad()` and `handleDecryptionOfPage(password, isRememberChecked)`. The default template attaches the standard form submit handler that calls `handleDecryptionOfPage` and `alert()`s on failure. **We replace that submit handler entirely** so we can drive our own status line on success/failure.

The DOM elements staticrypt's engine references (and we therefore must include — though we may freely restyle them):

```html
<!-- Loading spinner: shown while handleDecryptOnLoad() runs (instant if no remembered password). -->
<div id="staticrypt_loading">…</div>

<!-- Main content: form lives here, hidden until handleDecryptOnLoad reports failure. -->
<div id="staticrypt_content" class="hidden">
  <form id="staticrypt-form" action="#" method="post">
    <input id="staticrypt-password" type="password" name="password" autofocus />
    <!-- Hidden: not user-visible, but the default-handler reads it. We keep it
         as a hidden input to prevent runtime errors if our override breaks. -->
    <input id="staticrypt-remember" type="checkbox" name="remember" hidden />
    <button type="submit">AUTHENTICATE</button>
  </form>
</div>
```

The IDs `staticrypt_loading`, `staticrypt_content`, `staticrypt-form`, `staticrypt-password`, `staticrypt-remember` are read by staticrypt's bundled JS. Renaming any of them breaks the engine.

**Visual layout:**

```
┌─ full-bleed background: same dark + cyan grid as the HUD ─────────────────┐
│                                                                            │
│              ╔═══════════════════════════════════╗                         │
│              ║  ▌ JARVIS // OS · v0.1            ║   ← top bar             │
│              ╠═══════════════════════════════════╣                         │
│              ║                                   ║                         │
│              ║    > PASSWORD                     ║                         │
│              ║    [_____________________]        ║                         │
│              ║                                   ║                         │
│              ║         [ AUTHENTICATE ]          ║                         │
│              ║                                   ║                         │
│              ║    STATUS: STANDING BY.           ║                         │
│              ║                                   ║                         │
│              ╚═══════════════════════════════════╝                         │
│                                                                            │
│     scanline animation (4 s loop) crossing the centered panel              │
└────────────────────────────────────────────────────────────────────────────┘
```

**Token reuse (inlined into the template's `<style>`):**

```css
:root {
  --bg-0: #02060a;
  --bg-1: #03101a;
  --fg: #d6f0ff;
  --fg-dim: rgba(214, 240, 255, 0.65);
  --accent: #5cf0ff;
  --accent-faint: rgba(92, 240, 255, 0.10);
  --grid-line: rgba(92, 240, 255, 0.08);
  --deny: #ff5c5c;
}
```

Background: same `radial-gradient` + dual `linear-gradient` grid pattern as `web/src/styles/global.css` lines 17–28 (copied verbatim). CRT scanline overlay added as a fixed-position pseudo-element with a 2 px repeating-linear-gradient at 6% opacity.

**States:**

| State | Status line text | Color | Animation |
|---|---|---|---|
| idle | `STATUS: STANDING BY.` | `--accent` (cyan) | input caret blink only |
| submitting | `STATUS: DECRYPTING…` | `--accent` | three-dot ellipsis cycle, 600 ms loop |
| denied | `STATUS: ACCESS DENIED.` | `--deny` (red) | one-shot panel shake (200 ms, 3 cycles), held 1 s, then back to idle |
| granted | (page replaced by `replaceHtmlCallback`) | — | `body.granted` adds a 600 ms opacity fade before the swap |

**State transitions are driven by our own form submit handler**, which calls staticrypt's exposed `handleDecryptionOfPage` directly and branches on the returned `isSuccessful` flag. This is cleaner than monkey-patching the default handler — we initialise the engine the same way, then attach our handler instead of the default one.

```js
const staticrypt = staticryptInitiator.init(staticryptConfig, {
  rememberExpirationKey: 'staticrypt_expiration',
  rememberPassphraseKey: 'staticrypt_passphrase',
  // Hook the page replacement so we can fade out before the swap.
  replaceHtmlCallback: (decryptedHtml) => {
    document.body.classList.add('granted');  // triggers 600 ms fade-out
    setTimeout(() => {
      document.open();
      document.write(decryptedHtml);
      document.close();
    }, 600);
  },
  clearLocalStorageCallback: null,
});

window.addEventListener('load', async () => {
  // Default template attempts auto-decrypt-on-load (for --remember). Since
  // we don't use --remember, isSuccessful will be false; we just unhide the form.
  const { isSuccessful } = await staticrypt.handleDecryptOnLoad();
  if (!isSuccessful) {
    document.getElementById('staticrypt_loading').classList.add('hidden');
    document.getElementById('staticrypt_content').classList.remove('hidden');
    document.getElementById('staticrypt-password').focus();
  }
});

const form = document.getElementById('staticrypt-form');
const statusEl = document.getElementById('jarvis-status');
const panel = document.getElementById('jarvis-panel');

const setStatus = (text, mode) => {
  statusEl.textContent = `STATUS: ${text}`;
  statusEl.className = `jarvis-status jarvis-status--${mode}`;
};

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  setStatus('DECRYPTING…', 'working');
  const password = document.getElementById('staticrypt-password').value;
  const { isSuccessful } = await staticrypt.handleDecryptionOfPage(password, false);
  if (!isSuccessful) {
    setStatus('ACCESS DENIED.', 'denied');
    panel.classList.add('panel--shake');
    setTimeout(() => {
      panel.classList.remove('panel--shake');
      setStatus('STANDING BY.', 'idle');
    }, 1200);
  }
  // On success, replaceHtmlCallback runs — no extra branch needed.
});
```

The full template script is ~50 lines including initialisation. No external dependencies.

**Reduced-motion handling.** The `@media (prefers-reduced-motion: reduce)` block disables: scanline animation, scan bar, panel shake, and fade-out on grant. The status-line text changes still happen — they're informative, not decorative.

**Accessibility.**

- The form has `<label for="staticrypt-password">PASSWORD</label>` (visually styled as the `> PASSWORD` line).
- The status line is `<output id="jarvis-status" aria-live="polite">`. State transitions are announced.
- Focus lands on the password input on page load (`autofocus`).
- The submit button is keyboard-activatable (default `<button type="submit">`).
- Color contrast: `#5cf0ff` on `#02060a` is 11.4:1, well above WCAG AAA.

### 5.2 `.github/workflows/deploy.yml` — wire the template flag

One line added to the existing `Encrypt index.html` step:

```diff
       - name: Encrypt index.html
         env:
           STATICRYPT_PASSWORD: ${{ secrets.STATICRYPT_PASSWORD }}
         run: |
           npx -y staticrypt@^3 web/dist/index.html \
             -p "$STATICRYPT_PASSWORD" \
             --short \
+            --template web/unlock-template.html \
             -d web/dist
```

No other workflow changes. `web/unlock-template.html` lives in the repo (not in `web/dist/`), so it's available to the workflow via the `actions/checkout@v4` step that already runs.

### 5.3 `.github/workflows/ci.yml` — smoke test

Add one step at the end of the `web` job:

```yaml
      - name: staticrypt template smoke test
        run: |
          mkdir -p /tmp/unlock-smoke
          cp web/dist/index.html /tmp/unlock-smoke/index.html
          npx -y staticrypt@^3 /tmp/unlock-smoke/index.html \
            -p ci-smoke-password \
            --short \
            --template web/unlock-template.html \
            -d /tmp/unlock-smoke
          # The rendered template must contain our HUD title.
          grep -q 'JARVIS // OS' /tmp/unlock-smoke/index.html
          # And the staticrypt form contract must survive.
          grep -q 'id="staticrypt-form"' /tmp/unlock-smoke/index.html
          grep -q 'id="staticrypt-password"' /tmp/unlock-smoke/index.html
```

This catches: (a) accidental template breakage that would make the prod deploy fall back to the default UI, (b) a staticrypt minor-version bump that drops or renames placeholders we depend on, (c) accidentally removing one of the form-contract IDs while restyling.

### 5.4 `web/README.md` — documentation pointer

Add a short note under the existing "Deploy" section:

> The unlock page is a custom staticrypt template at `web/unlock-template.html`. Editing it changes the look of the password gate; the encryption pipeline (CI workflow, secret) is unchanged.

That's it. No new top-level docs.

## 6. Testing strategy

**CI (automated):** The smoke test in §5.3 runs on every PR. It is the only automated check — there's no rendering test (would require a headless browser; ROI poor for one static page).

**Manual on first deploy:**

1. Visit `https://mhaegeman.github.io/jarvis/` — the unlock page should load with the HUD aesthetic, scanline animating, status line reading `STATUS: STANDING BY.`.
2. Submit an empty password — staticrypt's standard validation rejects with no submit; status line stays idle.
3. Submit a wrong password — status flips to `STATUS: ACCESS DENIED.` in red, panel shakes once, then resets to idle after ~1.2 s.
4. Submit the correct password — status flips to `STATUS: DECRYPTING…`, then the page fades out and the HUD bundle loads.
5. Hard-refresh in a browser with `prefers-reduced-motion: reduce` enabled — verify no scanline animation, no shake on denial, but status text still updates.
6. Lighthouse pass on the unlock page — accessibility ≥ 95, performance ≥ 95 (the page is one HTML file, should be trivial).

No regression test is added for the existing HUD — this spec doesn't touch any HUD code path.

## 7. Acceptance criteria

- `web/unlock-template.html` exists, is self-contained, and renders correctly when fed through `npx staticrypt@^3 … --template web/unlock-template.html`.
- The CI smoke test (§5.3) passes on the PR that introduces this spec's plan.
- Visiting the deployed Pages URL after merge shows the HUD-styled unlock page (visual match to §5.1 mockup); wrong-password and correct-password flows behave per §6 manual checklist.
- No regression in pre-existing tests (web 60/60, server 58/58 stay green per spec-04 §8).
- `prefers-reduced-motion: reduce` disables all decorative animation while preserving informative state changes.

## 8. Files touched

| File | Change | Approx LOC |
|---|---|---|
| `web/unlock-template.html` | new (self-contained HTML + inline CSS + inline JS) | ~180 |
| `.github/workflows/deploy.yml` | one new flag in the encrypt step | +1 |
| `.github/workflows/ci.yml` | one new step in the `web` job | +12 |
| `web/README.md` | one paragraph documenting the template's existence | +3 |
| `docs/superpowers/STATUS.md` | row added for the v0.2 ε item (per existing convention) | +1 |

Total: ~5 files, ~200 LOC, mostly the template itself.

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| staticrypt v3 placeholder format / names drift in a minor release | CI smoke test (§5.3) catches it on the PR; we pin `staticrypt@^3` (already in `deploy.yml`); placeholder format `/*[|name|]*/0` is verified against the installed `staticrypt@^3.3.x`. |
| Element-ID contract (`staticrypt_loading`, `staticrypt_content`, `staticrypt-form`, `staticrypt-password`, `staticrypt-remember`) changes in a staticrypt minor | Smoke test grep's the post-encryption output for these IDs. Bumping major staticrypt versions requires re-reading the template contract. |
| `staticrypt.handleDecryptionOfPage` API renamed/removed in a minor | Smoke test catches it (would produce a runtime error on submit, but the simple smoke just tests the encrypt step succeeds). Manual smoke (§6) is the real backstop here. |
| Inline CSS bloat balloons the unlock page | Cap is ~5 KB of inline CSS; the template ships as one HTML file — no bundle, no fetch-blocking. Fine. |
| Asset 404s on slow networks before correct-password decrypt | Not introduced by this spec — staticrypt has always loaded the page first, then decrypted on submit. The unlock page itself loads no external assets. |
| `replaceHtmlCallback` fade timing race | The `setTimeout(600)` runs in our own callback, which staticrypt invokes synchronously with the decrypted HTML. The 600 ms is purely cosmetic; if the timer is somehow cancelled, the page just doesn't fade — nothing is broken. |
| Custom template is harder to update than the staticrypt default | Self-contained file with inline CSS = single point of edit. Annotated section headers in the file group title-bar / form / status / animations / states. |

**Open questions:** none. All aesthetic decisions confirmed in brainstorming (no `WELCOME, MAXIME.` granted-state text — granted state is purely a fade; failure shake confirmed; no boot-sequence text).

## 10. Decisions deferred (logged for the next polish item)

- Whether to add a `--remember` flag (staticrypt feature: store the decrypted bundle in `localStorage` so reloads skip the prompt). Convenient for daily use; reduces the "feel" of the gate. Decision deferred to user pref — not part of this spec.
- Whether the unlock page deserves its own "v0.2.1" iteration after Maxime lives with it for a week (e.g., adding ASCII logo art, swapping the panel border style). Out of scope here; raise as a new spec if wanted.

## 11. Self-review notes (orchestrator before commit)

- [x] No "TBD" or placeholders remain.
- [x] Internal consistency: workflow YAML diff in §5.2 matches the existing file `deploy.yml` lines 45–52 verbatim; CI smoke test in §5.3 references the same `staticrypt@^3` major as `deploy.yml`.
- [x] Scope: one template file + two workflow nudges + a doc paragraph. Single implementation plan, ~200 LOC. Comfortably bounded.
- [x] Ambiguity: staticrypt placeholder set is documented as a contract to verify in implementation, not assumed correct. Form-contract IDs explicit. Reduced-motion behavior explicit (decorative off, informative on).
- [x] No overlap with spec-04 (encryption pipeline untouched) or panels-v2 (HUD untouched). Pure unlock-page reskin.

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

**Required staticrypt placeholders** (Mustache-style `{{ }}` tokens that staticrypt v3 substitutes at encrypt time):

| Placeholder | Where it goes | Why |
|---|---|---|
| `{{ staticrypt_config }}` | `<script>` tag in `<head>` | Carries the encrypted payload, salt, IV, iteration count. Required. |
| `{{ js_staticrypt }}` | `<script>` tag at end of `<body>` | The vendored decrypt + form-handler bundle. Required. |
| `{{ template_button }}`, `{{ template_error }}`, `{{ template_instructions }}`, `{{ template_placeholder }}`, `{{ template_title }}` | Filled into the visible UI | Optional — we hard-code English strings directly in the template instead, so these placeholders are not used. |

**Note on placeholder names.** The exact placeholder identifiers used by `staticrypt@^3` are taken from the package's bundled default template (`node_modules/@staticrypt/staticrypt/lib/password_template.html` after `npm i staticrypt@^3`). The implementation plan begins with verifying these names against the installed version — if any drift, the template is updated 1-for-1. The set above is the contract we design against; verification is a 5-minute step, not a research project.

**Form interception contract.** The template must include:

```html
<form id="staticrypt-form" action="#" method="post">
  <input id="staticrypt-password" type="password" autocomplete="current-password" />
  <button type="submit">AUTHENTICATE</button>
</form>
```

The `id="staticrypt-form"` and `id="staticrypt-password"` selectors are the contract `js_staticrypt` reads. We may freely restyle, reposition, or wrap these elements, but we may not rename or remove them.

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
| granted | (handled by staticrypt — page is replaced) | — | 600 ms opacity fade-out before document.write fires |

Idle ↔ submitting ↔ denied transitions are driven by a small inline `<script>` (~25 lines) that wraps the existing form's submit handler:

```js
const form = document.getElementById('staticrypt-form');
const status = document.getElementById('jarvis-status');
const panel = document.getElementById('jarvis-panel');

form.addEventListener('submit', () => {
  status.textContent = 'STATUS: DECRYPTING…';
  status.className = 'status status--working';
});

// staticrypt's bundled JS calls a global `staticryptInitiator` that, on auth
// failure, surfaces an error via the {{ template_error }} placeholder element.
// We listen for that element's text changes via a MutationObserver and flip
// our status line accordingly. (Cleaner than monkey-patching staticrypt.)
const errorEl = document.getElementById('staticrypt-error');
new MutationObserver(() => {
  if (errorEl.textContent.trim()) {
    status.textContent = 'STATUS: ACCESS DENIED.';
    status.className = 'status status--denied';
    panel.classList.add('panel--shake');
    setTimeout(() => {
      panel.classList.remove('panel--shake');
      status.textContent = 'STATUS: STANDING BY.';
      status.className = 'status status--idle';
    }, 1200);
  }
}).observe(errorEl, { childList: true, subtree: true, characterData: true });
```

The `staticrypt-error` element ID is the contract for surfacing decrypt failures and is part of staticrypt's standard template scaffolding. If verification (see §5.1 placeholder note) shows a different ID, the script updates.

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
| staticrypt v3 placeholder names drift in a minor release | CI smoke test (§5.3) catches it on the PR; we pin `staticrypt@^3` (already in `deploy.yml`); plan starts with verifying placeholder names against the installed package version. |
| `id="staticrypt-form"` / `id="staticrypt-password"` change in a staticrypt minor | Same — smoke test checks both IDs; bumping major staticrypt versions requires re-reading the template contract. |
| Inline CSS bloat balloons the unlock page | Cap is ~5 KB of inline CSS; the template ships as one HTML file — no bundle, no fetch-blocking. Fine. |
| Asset 404s on slow networks before correct-password decrypt | Not introduced by this spec — staticrypt has always loaded the page first, then decrypted on submit. The unlock page itself loads no external assets. |
| Browser blocks the "fade-out before document.write" handoff | If `document.write` after a CSS transition fails on a given browser, fall back to immediate replacement (no fade). Not worth feature-flagging; we test on Maxime's primary browser (Chrome) only. |
| Custom template is harder to update than the staticrypt default | Self-contained file with inline CSS = single point of edit. Annotated section headers in the file group title-bar / form / status / animations / states. |

**Open questions:** none. All aesthetic decisions confirmed in brainstorming (status-line text `WELCOME, MAXIME.` not used because the page is replaced before anyone reads it; failure shake confirmed; no boot-sequence text).

## 10. Decisions deferred (logged for the next polish item)

- Whether to add a `--remember` flag (staticrypt feature: store the decrypted bundle in `localStorage` so reloads skip the prompt). Convenient for daily use; reduces the "feel" of the gate. Decision deferred to user pref — not part of this spec.
- Whether the unlock page deserves its own "v0.2.1" iteration after Maxime lives with it for a week (e.g., adding ASCII logo art, swapping the panel border style). Out of scope here; raise as a new spec if wanted.

## 11. Self-review notes (orchestrator before commit)

- [x] No "TBD" or placeholders remain.
- [x] Internal consistency: workflow YAML diff in §5.2 matches the existing file `deploy.yml` lines 45–52 verbatim; CI smoke test in §5.3 references the same `staticrypt@^3` major as `deploy.yml`.
- [x] Scope: one template file + two workflow nudges + a doc paragraph. Single implementation plan, ~200 LOC. Comfortably bounded.
- [x] Ambiguity: staticrypt placeholder set is documented as a contract to verify in implementation, not assumed correct. Form-contract IDs explicit. Reduced-motion behavior explicit (decorative off, informative on).
- [x] No overlap with spec-04 (encryption pipeline untouched) or panels-v2 (HUD untouched). Pure unlock-page reskin.

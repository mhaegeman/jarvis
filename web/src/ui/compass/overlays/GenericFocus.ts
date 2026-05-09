/**
 * Generic focus overlay for Tasks and System panels.
 * Renders a titled 720px card with an informational body.
 */
export function buildGenericFocus(
  kicker: string,
  title: string,
  body: string,
  onClose: () => void,
): HTMLElement {
  const overlay = document.createElement("div");
  overlay.className = "overlay";
  overlay.addEventListener("click", (e) => { if (e.target === overlay) onClose(); });

  overlay.innerHTML = `
    <div class="focus-card" style="width:min(720px,80vw);">
      <button class="close" aria-label="Close">esc · close</button>
      <div class="focus-head">
        <div>
          <div class="kicker">${escHtml(kicker)}</div>
          <div class="title">${escHtml(title)}</div>
        </div>
      </div>
      <div style="font-family:var(--mono);font-size:11px;color:var(--ink-2);line-height:1.7;overflow:auto;flex:1;min-height:0;">
        ${body}
      </div>
    </div>`;

  overlay.querySelector(".close")?.addEventListener("click", onClose);
  return overlay;
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

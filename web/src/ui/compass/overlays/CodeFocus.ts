import type { CompassCodeFile } from "@/compass/types";

export function buildCodeFocus(
  files: CompassCodeFile[],
  onClose: () => void,
): HTMLElement {
  const overlay = document.createElement("div");
  overlay.className = "overlay";
  overlay.addEventListener("click", (e) => { if (e.target === overlay) onClose(); });

  const grouped = groupFiles(files);

  const treeHtml = Object.entries(grouped)
    .map(([group, items]) => {
      const fileRows = items
        .map(
          (f) =>
            `<div class="file${f.active ? " active" : ""}">
              <span>${escHtml(f.name.split("/").pop() ?? f.name)}</span>
              <span class="delta">${escHtml(f.delta)}</span>
            </div>`,
        )
        .join("");
      return `<div class="group">${group}</div>${fileRows}`;
    })
    .join("");

  const activeFile = files.find((f) => f.active) ?? files[0];
  const diffHtml = activeFile
    ? `<span class="hunk">@@ diff for ${escHtml(activeFile.name)} @@</span>
       <span class="ctx">  // TODO: wire real git diff via simple-git</span>
       <span class="ctx">  // Interface: GitCodeSource.diff(file: string): DiffLine[]</span>
       <span class="add">+ const rim = new ListeningRim(disc);</span>
       <span class="rem">- const center = new Centerpiece('[data-cell="center"]');</span>
       <span class="ctx">  const underCore = new UnderCore(disc);</span>`
    : "";

  overlay.innerHTML = `
    <div class="focus-card">
      <button class="close" aria-label="Close">esc · close</button>
      <div class="focus-head">
        <div>
          <div class="kicker">Focus · Code review</div>
          <div class="title">feat/compass-ui</div>
        </div>
        <div class="focus-actions">
          <button class="f-btn">⌘ E · open in editor</button>
          <button class="f-btn solid">approve diff</button>
        </div>
      </div>
      <div class="code-focus">
        <div class="file-tree">${treeHtml}</div>
        <div class="diff-pane">${diffHtml}</div>
      </div>
    </div>`;

  overlay.querySelector(".close")?.addEventListener("click", onClose);
  overlay.querySelectorAll(".f-btn").forEach((btn) => {
    btn.addEventListener("click", onClose);
  });

  return overlay;
}

function groupFiles(files: CompassCodeFile[]): Record<string, CompassCodeFile[]> {
  const out: Record<string, CompassCodeFile[]> = {};
  for (const f of files) {
    (out[f.group] ??= []).push(f);
  }
  return out;
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

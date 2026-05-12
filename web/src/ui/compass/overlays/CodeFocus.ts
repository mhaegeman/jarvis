import type { CompassCodeFile } from "@/compass/types";
import type { ServerGitDiffLine } from "@/api/gitStatus";

export interface CodeFocusProps {
  branch: string;
  files: CompassCodeFile[];
  /** Loads a unified diff for one file. Returning an empty list renders an empty pane. */
  loadDiff: (path: string) => Promise<ServerGitDiffLine[]>;
}

export function buildCodeFocus(
  props: CodeFocusProps,
  onClose: () => void,
): HTMLElement {
  const { branch, files, loadDiff } = props;
  const overlay = document.createElement("div");
  overlay.className = "overlay";
  overlay.addEventListener("click", (e) => { if (e.target === overlay) onClose(); });

  const grouped = groupFiles(files);

  const treeHtml = Object.entries(grouped)
    .map(([group, items]) => {
      const fileRows = items
        .map(
          (f) =>
            `<div class="file${f.active ? " active" : ""}" data-path="${escHtml(f.name)}">
              <span>${escHtml(f.name.split("/").pop() ?? f.name)}</span>
              <span class="delta">${escHtml(f.delta)}</span>
            </div>`,
        )
        .join("");
      return `<div class="group">${escHtml(group)}</div>${fileRows}`;
    })
    .join("");

  overlay.innerHTML = `
    <div class="focus-card">
      <button class="close" aria-label="Close">esc · close</button>
      <div class="focus-head">
        <div>
          <div class="kicker">Focus · Code review</div>
          <div class="title">${escHtml(branch)}</div>
        </div>
        <div class="focus-actions">
          <button class="f-btn">Ctrl E · open in editor</button>
          <button class="f-btn solid">approve diff</button>
        </div>
      </div>
      <div class="code-focus">
        <div class="file-tree">${treeHtml}</div>
        <div class="diff-pane" data-diff-pane>
          <span class="ctx">  loading diff…</span>
        </div>
      </div>
    </div>`;

  const diffPane = overlay.querySelector<HTMLElement>("[data-diff-pane]");
  const renderDiff = (lines: ServerGitDiffLine[], path: string): void => {
    if (!diffPane) return;
    if (lines.length === 0) {
      diffPane.innerHTML = `<span class="ctx">  no diff for ${escHtml(path)}</span>`;
      return;
    }
    diffPane.innerHTML = [
      `<span class="hunk">@@ diff for ${escHtml(path)} @@</span>`,
      ...lines.map((line) => {
        const cls = line.kind === "+" ? "add" : line.kind === "-" ? "rem" : "ctx";
        const prefix = line.kind === "+" ? "+ " : line.kind === "-" ? "- " : "  ";
        return `<span class="${cls}">${escHtml(prefix + line.text)}</span>`;
      }),
    ].join("\n");
  };

  const loadAndRender = (path: string): void => {
    if (!diffPane) return;
    diffPane.innerHTML = `<span class="ctx">  loading ${escHtml(path)}…</span>`;
    loadDiff(path)
      .then((lines) => renderDiff(lines, path))
      .catch(() => {
        if (diffPane) {
          diffPane.innerHTML = `<span class="rem">  failed to load diff for ${escHtml(path)}</span>`;
        }
      });
  };

  const active = files.find((f) => f.active) ?? files[0];
  if (active) {
    loadAndRender(active.name);
  } else if (diffPane) {
    diffPane.innerHTML = `<span class="ctx">  no files changed</span>`;
  }

  // Clicking a file in the tree loads its diff.
  overlay.querySelectorAll<HTMLElement>(".file").forEach((row) => {
    row.addEventListener("click", (e) => {
      e.stopPropagation();
      const path = row.getAttribute("data-path");
      if (!path) return;
      overlay.querySelectorAll(".file.active").forEach((n) => n.classList.remove("active"));
      row.classList.add("active");
      loadAndRender(path);
    });
  });

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

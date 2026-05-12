import { describe, it, expect, beforeEach } from "vitest";
import { buildCodeFocus } from "@/ui/compass/overlays/CodeFocus";
import type { CompassCodeFile } from "@/compass/types";
import type { ServerGitDiffLine } from "@/api/gitStatus";

const FILES: CompassCodeFile[] = [
  { group: "modified", name: "src/a.ts", delta: "M", active: true },
  { group: "added",    name: "src/b.ts", delta: "new", active: false },
];

const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

describe("buildCodeFocus", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("renders the branch name in the focus header", () => {
    const overlay = buildCodeFocus(
      { branch: "feat/git-status", files: FILES, loadDiff: async () => [] },
      () => {},
    );
    document.body.appendChild(overlay);
    expect(overlay.querySelector(".title")?.textContent).toBe("feat/git-status");
  });

  it("renders one row per file in the tree", () => {
    const overlay = buildCodeFocus(
      { branch: "main", files: FILES, loadDiff: async () => [] },
      () => {},
    );
    document.body.appendChild(overlay);
    expect(overlay.querySelectorAll(".file").length).toBe(2);
  });

  it("loads the diff for the active file on mount", async () => {
    let requested = "";
    const lines: ServerGitDiffLine[] = [
      { kind: " ", text: "@@" },
      { kind: "+", text: "added line" },
    ];
    const overlay = buildCodeFocus(
      {
        branch: "main",
        files: FILES,
        loadDiff: async (path) => {
          requested = path;
          return lines;
        },
      },
      () => {},
    );
    document.body.appendChild(overlay);
    await flush();
    expect(requested).toBe("src/a.ts");
    expect(overlay.querySelector("[data-diff-pane]")?.textContent).toContain("added line");
  });

  it("re-loads the diff when a different file in the tree is clicked", async () => {
    const calls: string[] = [];
    const overlay = buildCodeFocus(
      {
        branch: "main",
        files: FILES,
        loadDiff: async (path) => {
          calls.push(path);
          return [{ kind: "+", text: `body of ${path}` }];
        },
      },
      () => {},
    );
    document.body.appendChild(overlay);
    await flush();
    const second = overlay.querySelectorAll<HTMLElement>(".file")[1];
    second.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await flush();
    expect(calls).toEqual(["src/a.ts", "src/b.ts"]);
    expect(second.classList.contains("active")).toBe(true);
  });

  it("renders an empty-state message when there are no files", () => {
    const overlay = buildCodeFocus(
      { branch: "main", files: [], loadDiff: async () => [] },
      () => {},
    );
    document.body.appendChild(overlay);
    expect(overlay.querySelector("[data-diff-pane]")?.textContent).toMatch(
      /no files changed/,
    );
  });

  it("invokes onClose when the close button is clicked", () => {
    let closed = false;
    const overlay = buildCodeFocus(
      { branch: "main", files: FILES, loadDiff: async () => [] },
      () => { closed = true; },
    );
    document.body.appendChild(overlay);
    overlay.querySelector<HTMLElement>(".close")?.click();
    expect(closed).toBe(true);
  });
});

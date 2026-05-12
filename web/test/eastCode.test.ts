import { describe, it, expect, beforeEach } from "vitest";
import { EastCode } from "@/ui/compass/zones/EastCode";
import type { CompassCodeFile } from "@/compass/types";

const FILES: CompassCodeFile[] = [
  { group: "modified", name: "src/a.ts", delta: "M", active: true },
  { group: "added",    name: "src/b.ts", delta: "new", active: false },
  { group: "deleted",  name: "src/c.ts", delta: "D", active: false },
];

describe("EastCode", () => {
  let parent: HTMLElement;

  beforeEach(() => {
    document.body.innerHTML = `<div id="app"></div>`;
    parent = document.getElementById("app")!;
  });

  it("renders the branch name in the title slot", () => {
    const zone = new EastCode(parent);
    zone.render({ branch: "feat/git-status", files: FILES, buildStatus: null });
    expect(parent.querySelector(".title")?.textContent).toBe("feat/git-status");
  });

  it("renders 'build —' when buildStatus is null", () => {
    const zone = new EastCode(parent);
    zone.render({ branch: "main", files: [], buildStatus: null });
    expect(parent.textContent).toMatch(/build —/);
  });

  it("renders a build glyph for non-null buildStatus", () => {
    const zone = new EastCode(parent);
    zone.render({ branch: "main", files: FILES, buildStatus: "ok" });
    expect(parent.textContent).toMatch(/build ✓/);
  });

  it("counts files per group and renders the summary row", () => {
    const zone = new EastCode(parent);
    zone.render({ branch: "main", files: FILES, buildStatus: null });
    const what = parent.querySelector(".what")?.textContent ?? "";
    expect(what).toContain("1 modified");
    expect(what).toContain("1 added");
    expect(what).toContain("1 deleted");
  });

  it("falls back gracefully when no files are changed", () => {
    const zone = new EastCode(parent);
    zone.render({ branch: "main", files: [], buildStatus: null });
    expect(parent.textContent).toMatch(/no changes/);
  });

  it("fires onClick when the zone is clicked", () => {
    const zone = new EastCode(parent);
    zone.render({ branch: "main", files: FILES, buildStatus: null });
    let clicks = 0;
    zone.onClick(() => clicks++);
    parent.querySelector(".zone")?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(clicks).toBe(1);
  });
});

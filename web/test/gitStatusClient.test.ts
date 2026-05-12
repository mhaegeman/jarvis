import { describe, it, expect } from "vitest";
import {
  fetchGitStatus,
  fetchGitDiff,
  mapStatusGroup,
  toCompassFiles,
  pollIfVisible,
} from "@/api/gitStatus";

const ok = (body: unknown): Response =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

const notFound = (): Response =>
  new Response(JSON.stringify({ detail: "missing" }), { status: 404 });

describe("mapStatusGroup", () => {
  it("maps A and ?? to 'added'", () => {
    expect(mapStatusGroup("A")).toBe("added");
    expect(mapStatusGroup("??")).toBe("added");
  });
  it("maps D to 'deleted'", () => {
    expect(mapStatusGroup("D")).toBe("deleted");
  });
  it("maps M and R to 'modified'", () => {
    expect(mapStatusGroup("M")).toBe("modified");
    expect(mapStatusGroup("R")).toBe("modified");
  });
});

describe("toCompassFiles", () => {
  it("marks the first file active and preserves order", () => {
    const out = toCompassFiles([
      { path: "a.ts", status: "M" },
      { path: "b.ts", status: "A" },
      { path: "c.ts", status: "??" },
    ]);
    expect(out).toHaveLength(3);
    expect(out[0].active).toBe(true);
    expect(out[1].active).toBe(false);
    expect(out[2].active).toBe(false);
    expect(out.map((f) => f.name)).toEqual(["a.ts", "b.ts", "c.ts"]);
  });

  it("renders 'new' delta for untracked files", () => {
    const out = toCompassFiles([{ path: "x.ts", status: "??" }]);
    expect(out[0].delta).toBe("new");
  });
});

describe("fetchGitStatus", () => {
  it("returns mapped CompassCodeFile[] on success", async () => {
    const stub: typeof fetch = async () =>
      ok({
        branch: "feat/x",
        files: [
          { path: "a.ts", status: "M" },
          { path: "b.ts", status: "A" },
        ],
        buildStatus: null,
      });
    const out = await fetchGitStatus("", stub);
    expect(out.branch).toBe("feat/x");
    expect(out.files).toHaveLength(2);
    expect(out.files[0].group).toBe("modified");
    expect(out.files[1].group).toBe("added");
    expect(out.buildStatus).toBeNull();
  });

  it("throws on non-2xx", async () => {
    const stub: typeof fetch = async () =>
      new Response("boom", { status: 500 });
    await expect(fetchGitStatus("", stub)).rejects.toThrow(/HTTP 500/);
  });
});

describe("fetchGitDiff", () => {
  it("returns an empty list on 404 (no file/no diff)", async () => {
    const stub: typeof fetch = async () => notFound();
    const out = await fetchGitDiff("missing.ts", "", stub);
    expect(out).toEqual([]);
  });

  it("returns the parsed diff lines on success", async () => {
    const stub: typeof fetch = async () =>
      ok({
        lines: [
          { kind: " ", text: "@@ -1,3 +1,3 @@" },
          { kind: "+", text: "added" },
          { kind: "-", text: "removed" },
        ],
      });
    const out = await fetchGitDiff("a.ts", "", stub);
    expect(out).toHaveLength(3);
    expect(out[1]).toEqual({ kind: "+", text: "added" });
  });

  it("url-encodes the path query parameter", async () => {
    let captured = "";
    const stub: typeof fetch = async (input) => {
      captured = typeof input === "string" ? input : input.toString();
      return ok({ lines: [] });
    };
    await fetchGitDiff("src/has space.ts", "", stub);
    expect(captured).toContain("path=src%2Fhas%20space.ts");
  });

  it("forwards a truncation-marker line untouched", async () => {
    const stub: typeof fetch = async () =>
      ok({
        lines: [
          { kind: "+", text: "x" },
          { kind: "…", text: "diff truncated at 200 lines" },
        ],
      });
    const out = await fetchGitDiff("a.ts", "", stub);
    expect(out[1].kind).toBe("…");
    expect(out[1].text).toMatch(/truncated/);
  });
});

describe("pollIfVisible", () => {
  it("runs the poll when the tab is visible", async () => {
    let called = 0;
    const ran = await pollIfVisible(async () => {
      called++;
    }, "visible");
    expect(called).toBe(1);
    expect(ran).toBe(true);
  });

  it("skips the poll when the tab is hidden", async () => {
    let called = 0;
    const ran = await pollIfVisible(async () => {
      called++;
    }, "hidden");
    expect(called).toBe(0);
    expect(ran).toBe(false);
  });

  it("treats 'prerender' as not-visible", async () => {
    let called = 0;
    const ran = await pollIfVisible(
      async () => {
        called++;
      },
      "prerender" as DocumentVisibilityState,
    );
    expect(called).toBe(0);
    expect(ran).toBe(false);
  });
});

describe("authorization", () => {
  it("sends Authorization: Bearer <token> on fetchGitStatus when a token is cached", async () => {
    sessionStorage.setItem("jarvis_token", "tok123");
    let seenAuth = "";
    const stub: typeof fetch = async (_input, init) => {
      const headers = new Headers(init?.headers);
      seenAuth = headers.get("Authorization") ?? "";
      return ok({ branch: "main", files: [], buildStatus: null });
    };
    await fetchGitStatus("", stub);
    expect(seenAuth).toBe("Bearer tok123");
    sessionStorage.removeItem("jarvis_token");
  });

  it("sends Authorization on fetchGitDiff when a token is cached", async () => {
    sessionStorage.setItem("jarvis_token", "tok456");
    let seenAuth = "";
    const stub: typeof fetch = async (_input, init) => {
      const headers = new Headers(init?.headers);
      seenAuth = headers.get("Authorization") ?? "";
      return ok({ lines: [] });
    };
    await fetchGitDiff("a.ts", "", stub);
    expect(seenAuth).toBe("Bearer tok456");
    sessionStorage.removeItem("jarvis_token");
  });

  it("does not send Authorization when no token is cached", async () => {
    sessionStorage.removeItem("jarvis_token");
    let seenAuth: string | null = null;
    const stub: typeof fetch = async (_input, init) => {
      const headers = new Headers(init?.headers);
      seenAuth = headers.get("Authorization");
      return ok({ branch: "main", files: [], buildStatus: null });
    };
    await fetchGitStatus("", stub);
    expect(seenAuth).toBeNull();
  });
});

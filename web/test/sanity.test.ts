import { describe, it, expect } from "vitest";

describe("toolchain sanity", () => {
  it("runs vitest with jsdom and TS", () => {
    const el = document.createElement("div");
    el.textContent = "ok";
    expect(el.textContent).toBe("ok");
  });
});

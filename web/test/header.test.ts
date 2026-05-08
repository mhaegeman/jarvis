import { describe, it, expect } from "vitest";
import { Header } from "@/ui/Header";

describe("Header", () => {
  it("renders the wsState badge with data-ws-state='live'", () => {
    document.body.innerHTML = `<header id="h"></header>`;
    const h = new Header("#h");
    h.mount({ uptimeMs: 3661000, wsState: "live" });
    const badge = document.querySelector(".ws-badge");
    expect(badge?.getAttribute("data-ws-state")).toBe("live");
    expect(badge?.textContent?.trim()).toBe("LIVE");
  });

  it("renders the wsState badge with data-ws-state='demo'", () => {
    document.body.innerHTML = `<header id="h"></header>`;
    const h = new Header("#h");
    h.mount({ uptimeMs: 0, wsState: "demo" });
    const badge = document.querySelector(".ws-badge");
    expect(badge?.getAttribute("data-ws-state")).toBe("demo");
    expect(badge?.textContent?.trim()).toBe("DEMO");
  });

  it("renders the wsState badge with data-ws-state='reconnecting'", () => {
    document.body.innerHTML = `<header id="h"></header>`;
    const h = new Header("#h");
    h.mount({ uptimeMs: 0, wsState: "reconnecting" });
    const badge = document.querySelector(".ws-badge");
    expect(badge?.getAttribute("data-ws-state")).toBe("reconnecting");
    expect(badge?.textContent?.trim()).toBe("RECONNECT…");
  });

  it("still renders the uptime and clock spans", () => {
    document.body.innerHTML = `<header id="h"></header>`;
    const h = new Header("#h");
    h.mount({ uptimeMs: 3661000, wsState: "live" });
    const uptime = document.querySelector(".uptime");
    const clock = document.querySelector(".clock");
    // 3661000ms = 1h 1m 1s
    expect(uptime?.textContent?.trim()).toBe("01:01:01");
    expect(clock).not.toBeNull();
    // clock renders HH:MM:SS format
    expect(clock?.textContent?.trim()).toMatch(/^\d{2}:\d{2}:\d{2}$/);
  });
});

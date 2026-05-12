import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// We test the auth fetch logic in isolation by testing the helper directly.
// The helper is extracted from LoginPage.ts as a pure function.
import { attemptLogin } from "@/ui/login/attemptLogin";

describe("attemptLogin", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it("returns ok:true and stores token on 200", async () => {
    const token = "a".repeat(64);
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ token }), { status: 200 }),
    );
    const result = await attemptLogin("correctphrase123");
    expect(result.ok).toBe(true);
    expect(sessionStorage.getItem("jarvis_token")).toBe(token);
  });

  it("returns ok:false on 401", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Invalid passphrase" }), { status: 401 }),
    );
    const result = await attemptLogin("wrongpassphrase");
    expect(result.ok).toBe(false);
    expect(sessionStorage.getItem("jarvis_token")).toBeNull();
  });

  it("returns ok:true (offline fallback) when fetch throws", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError("Failed to fetch"));
    // Offline fallback: any passphrase ≥12 chars succeeds
    const result = await attemptLogin("offlinepassphrase");
    expect(result.ok).toBe(true);
  });

  it("offline fallback returns ok:false for short passphrase", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const result = await attemptLogin("short");
    expect(result.ok).toBe(false);
  });
});

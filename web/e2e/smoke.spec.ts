import { test, expect } from "@playwright/test";

test("HUD boots, cycles through full conversation", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto("/?dev=1");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 5000 });

  // All 9 cells exist
  for (const cell of ["top", "tl", "tr", "left", "center", "right", "bl", "bottom", "br"]) {
    await expect(page.locator(`[data-cell="${cell}"]`)).toBeVisible();
  }

  // Run a scenario
  await page.locator('[data-action="run-scenario"]').click();

  // State should reach speaking, then return to idle
  await expect(page.locator("body")).toHaveAttribute("data-state", "speaking", { timeout: 8000 });
  await expect(page.locator("body")).toHaveAttribute("data-state", "idle", { timeout: 30000 });

  // Transcript should have content
  const text = (await page.locator(".transcript .body").textContent()) ?? "";
  expect(text.length).toBeGreaterThan(5);

  expect(consoleErrors, `console errors: ${consoleErrors.join(" | ")}`).toEqual([]);
});

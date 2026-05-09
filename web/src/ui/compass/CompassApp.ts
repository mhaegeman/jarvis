import type { Surface } from "@/router";

/**
 * Compass main surface — orchestrates all compass sub-components.
 * Step 1 stub: renders a placeholder; full implementation in Step 2.
 */
export function createCompassApp(): Surface {
  const app = document.getElementById("app")!;
  app.innerHTML = `
    <div style="display:grid;place-items:center;height:100%;font-family:var(--serif);font-size:22px;font-weight:300;color:var(--ink-3);">
      compass loading…
    </div>`;

  return {
    destroy(): void {
      app.innerHTML = "";
    },
  };
}

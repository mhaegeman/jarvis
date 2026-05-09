/** Minimal two-surface router — no page reloads, mounts into #app. */

export type Surface = { destroy(): void };
export type SurfaceFactory = () => Surface;

let current: Surface | null = null;

export function mount(factory: SurfaceFactory): void {
  current?.destroy();
  current = null;
  const app = document.getElementById("app");
  if (!app) throw new Error("Missing #app mount point");
  app.innerHTML = "";
  current = factory();
}

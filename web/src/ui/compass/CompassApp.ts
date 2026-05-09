import type { Surface } from "@/router";
import { store, events, mic, ensureMic, stopMicStream, tryTransition, log } from "@/main";
import { mapCalendarEntries, mapSystem, mapTasks, STUB_CODE_FILES } from "@/compass/types";
import { Topbar } from "./Topbar";
import { Bottombar } from "./Bottombar";
import { OrreryCore } from "./OrreryCore";
import { Ring } from "./Ring";
import { HourLabels } from "./HourLabels";
import { ListeningRim } from "./ListeningRim";
import { UnderCore } from "./UnderCore";
import { NorthCalendar } from "./zones/NorthCalendar";
import { EastCode } from "./zones/EastCode";
import { SouthSystem } from "./zones/SouthSystem";
import { WestTasks } from "./zones/WestTasks";
import { buildCodeFocus } from "./overlays/CodeFocus";
import { buildCalendarTakeover } from "./overlays/CalendarTakeover";
import { buildGenericFocus } from "./overlays/GenericFocus";

let micHeld = false;
let micReady = false;

export function createCompassApp(): Surface {
  const app = document.getElementById("app")!;

  // Build DOM scaffold
  app.innerHTML = `
    <div id="compass-topbar"></div>
    <div class="stage">
      <div class="compass" id="compass-disc"></div>
    </div>
    <div id="compass-bottombar"></div>`;

  const disc = document.getElementById("compass-disc")!;

  // Mount sub-components
  const topbar = new Topbar(document.getElementById("compass-topbar")!);
  const bottombar = new Bottombar(document.getElementById("compass-bottombar")!);
  const ring = new Ring(disc);
  const hourLabels = new HourLabels(disc);
  const orrery = new OrreryCore(disc);
  const rim = new ListeningRim(disc);
  const underCore = new UnderCore(disc);

  // Cardinal zones (appended directly to #app so they position relative to viewport)
  const northCal  = new NorthCalendar(app);
  const eastCode  = new EastCode(app);
  const southSys  = new SouthSystem(app);
  const westTasks = new WestTasks(app);

  const start = Date.now();

  // State
  let zenMode = false;
  let overlayEl: HTMLElement | null = null;

  function closeOverlay(): void {
    overlayEl?.remove();
    overlayEl = null;
    app.classList.remove("dim");
  }

  // Mic / voice actions (mirroring old main.ts logic)
  const actions = {
    onMicDown: async (): Promise<void> => {
      if (store.get().state !== "idle") return;
      micHeld = true;
      micReady = false;
      const ok = await ensureMic();
      if (!ok) { micHeld = false; return; }
      tryTransition("startListening");
      store.update(() => ({ centerTitle: "Listening." }));
      try {
        await events.beginListening();
      } catch (err) {
        log("warn", `mic start failed: ${String(err)}`);
        events.endListening();
        stopMicStream();
        micHeld = false;
        tryTransition("interrupt");
        store.update(() => ({ centerTitle: "Standing by." }));
        return;
      }
      micReady = true;
      if (!micHeld) {
        events.endListening();
        mic.stop();
        stopMicStream();
        tryTransition("cancelListening");
        store.update(() => ({ centerTitle: "Standing by." }));
      }
    },

    onMicUp: (): void => {
      micHeld = false;
      if (store.get().state !== "listening") {
        events.endListening();
        mic.stop();
        stopMicStream();
        return;
      }
      if (!micReady) {
        events.endListening();
        mic.stop();
        stopMicStream();
        tryTransition("cancelListening");
        store.update(() => ({ centerTitle: "Standing by." }));
        return;
      }
      events.endListening();
      mic.stop();
      stopMicStream();
      tryTransition("stopListening");
      store.update(() => ({ centerTitle: "Thinking." }));
    },
  };

  // Keyboard shortcuts
  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === "Escape") { closeOverlay(); return; }
    if ((e.metaKey || e.ctrlKey) && e.key === "e") { e.preventDefault(); openCodeFocus(); return; }
    if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); openCalendarTakeover(); return; }
    if ((e.metaKey || e.ctrlKey) && e.key === " ") { e.preventDefault(); actions.onMicDown().catch(() => {}); return; }
  }
  function handleKeyup(e: KeyboardEvent): void {
    if ((e.metaKey || e.ctrlKey) || e.key === " ") actions.onMicUp();
  }
  window.addEventListener("keydown", handleKeydown);
  window.addEventListener("keyup", handleKeyup);

  function openCodeFocus(): void {
    if (overlayEl) return;
    app.classList.add("dim");
    overlayEl = buildCodeFocus(STUB_CODE_FILES, closeOverlay);
    app.appendChild(overlayEl);
  }

  function openCalendarTakeover(): void {
    if (overlayEl) return;
    app.classList.add("dim");
    const entries = mapCalendarEntries(store.get().panelData.calendar.entries);
    overlayEl = buildCalendarTakeover(entries, closeOverlay);
    app.appendChild(overlayEl);
  }

  function openGenericFocus(section: "System" | "Tasks"): void {
    if (overlayEl) return;
    app.classList.add("dim");
    const s = store.get();
    const uptime = Date.now() - start;
    const body =
      section === "System"
        ? buildSystemBody(mapSystem(s.panelData.system, s.panelData.memory, uptime))
        : buildTasksBody(mapTasks(s.panelData.tasks));
    overlayEl = buildGenericFocus(`Focus · ${section}`, section, body, closeOverlay);
    app.appendChild(overlayEl);
  }

  // Wire zone click → overlay
  northCal.onClick(() => openCalendarTakeover());
  eastCode.onClick(() => openCodeFocus());
  southSys.onClick(() => openGenericFocus("System"));
  westTasks.onClick(() => openGenericFocus("Tasks"));

  // Render loop — rAF-driven, renders everything each frame
  let rafId: number;
  let lastCalRender = 0;
  function tick(): void {
    const s = store.get();
    const uptime = Date.now() - start;

    topbar.render({ convState: s.state });
    bottombar.render({
      tokensPerMin: s.panelData.system?.tokensPerMin ?? 0,
      load: s.panelData.system?.load ?? 0,
      uptimeMs: uptime,
    });

    ring.render(s.state);
    hourLabels.render();
    orrery.render(s.state);

    if (s.state === "listening") rim.show();
    else rim.hide();

    underCore.render(s.state, s.centerTitle);

    // Zones — throttled to 1Hz (data changes slowly)
    const now = Date.now();
    if (now - lastCalRender > 1000) {
      lastCalRender = now;
      northCal.render(mapCalendarEntries(s.panelData.calendar.entries));
      eastCode.render(STUB_CODE_FILES);
      southSys.render(mapSystem(s.panelData.system, s.panelData.memory, uptime));
      westTasks.render(mapTasks(s.panelData.tasks));
    }

    // Zen mode sync
    app.classList.toggle("zen", zenMode);

    rafId = requestAnimationFrame(tick);
  }
  rafId = requestAnimationFrame(tick);

  return {
    destroy(): void {
      cancelAnimationFrame(rafId);
      window.removeEventListener("keydown", handleKeydown);
      window.removeEventListener("keyup", handleKeyup);
      topbar.destroy();
      bottombar.destroy();
      rim.destroy();
      underCore.destroy();
      northCal.destroy();
      eastCode.destroy();
      southSys.destroy();
      westTasks.destroy();
      app.innerHTML = "";
    },
  };
}

function buildSystemBody(sys: ReturnType<typeof mapSystem>): string {
  return `
    <div style="display:grid;grid-template-columns:auto 1fr;gap:4px 24px;margin-bottom:16px;">
      <span style="color:var(--ink-3);">uptime</span><span>${escHtml(sys.uptime)}</span>
      <span style="color:var(--ink-3);">load</span><span>${escHtml(sys.load)}</span>
      <span style="color:var(--ink-3);">tok/m</span><span>${escHtml(sys.tokens)}</span>
      <span style="color:var(--ink-3);">model</span><span>${escHtml(sys.model)}</span>
      <span style="color:var(--ink-3);">context</span><span>${sys.contextUsed}K / ${sys.contextMax}K</span>
    </div>`;
}

function buildTasksBody(tasks: ReturnType<typeof mapTasks>): string {
  if (tasks.length === 0) return `<p style="color:var(--ink-3);">no active tasks</p>`;
  return tasks
    .map(
      (t) =>
        `<div style="margin-bottom:8px;padding:8px;background:var(--paper-2);border-radius:3px;">
           <span style="color:var(--ink-3);margin-right:8px;">${escHtml(t.state)}</span>
           <span>${escHtml(t.label)}</span>
           ${t.meta ? `<span style="color:var(--ink-3);margin-left:8px;">${escHtml(t.meta)}</span>` : ""}
         </div>`,
    )
    .join("");
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

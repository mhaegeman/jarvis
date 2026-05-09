import type { Surface } from "@/router";
import { store, events, mic, ensureMic, stopMicStream, tryTransition, log } from "@/main";
import { mapCalendarEntries, mapSystem, mapTasks, STUB_CODE_FILES, STUB_NOTIFS } from "@/compass/types";
import { Topbar } from "./Topbar";
import { Bottombar } from "./Bottombar";
import { OrreryCore } from "./OrreryCore";
import { Ring } from "./Ring";
import { HourLabels } from "./HourLabels";
import { ListeningRim } from "./ListeningRim";
import { UnderCore } from "./UnderCore";
import { NotifRing } from "./NotifRing";
import { VoiceDock } from "./VoiceDock";
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

  // Notification chips (viewport-positioned, relative to disc centre)
  const notifRing = new NotifRing(app);

  // Voice dock (shows while ⌘+Space is held)
  const voiceDock = new VoiceDock(disc);

  const start = Date.now();

  // Time-of-day palette drift — cosine-lerp accent + paper toward night values on minute tick
  // Gated: skip entirely under prefers-reduced-motion (no visual change, no overhead)
  let driftInterval: ReturnType<typeof setInterval> | null = null;
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    applyTimeDrift(app);
    driftInterval = setInterval(() => applyTimeDrift(app), 60_000);
  }

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
      voiceDock.show();
      const ok = await ensureMic();
      if (!ok) { micHeld = false; voiceDock.hide(); return; }
      tryTransition("startListening");
      store.update(() => ({ centerTitle: "Listening." }));
      try {
        await events.beginListening();
      } catch (err) {
        log("warn", `mic start failed: ${String(err)}`);
        events.endListening();
        stopMicStream();
        micHeld = false;
        voiceDock.hide();
        tryTransition("interrupt");
        store.update(() => ({ centerTitle: "Standing by." }));
        return;
      }
      micReady = true;
      if (!micHeld) {
        events.endListening();
        mic.stop();
        stopMicStream();
        voiceDock.hide();
        tryTransition("cancelListening");
        store.update(() => ({ centerTitle: "Standing by." }));
      }
    },

    onMicUp: (): void => {
      micHeld = false;
      voiceDock.hide();
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
    if (e.key === "z" && !e.metaKey && !e.ctrlKey && !e.altKey && !(e.target instanceof HTMLInputElement)) {
      zenMode = !zenMode; return;
    }
    if ((e.metaKey || e.ctrlKey) && e.key === "e") { e.preventDefault(); openCodeFocus(); return; }
    if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); openCalendarTakeover(); return; }
    if ((e.metaKey || e.ctrlKey) && e.key === " ") { e.preventDefault(); actions.onMicDown().catch(() => {}); return; }
  }
  function handleKeyup(e: KeyboardEvent): void {
    if (e.key === " ") actions.onMicUp();
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

    // Zones + notifs — throttled to 1Hz (data changes slowly)
    const now = Date.now();
    if (now - lastCalRender > 1000) {
      lastCalRender = now;
      northCal.render(mapCalendarEntries(s.panelData.calendar.entries));
      eastCode.render(STUB_CODE_FILES);
      southSys.render(mapSystem(s.panelData.system, s.panelData.memory, uptime));
      westTasks.render(mapTasks(s.panelData.tasks));
      notifRing.render(STUB_NOTIFS);
    }

    // Zen mode sync
    app.classList.toggle("zen", zenMode);

    rafId = requestAnimationFrame(tick);
  }
  rafId = requestAnimationFrame(tick);

  return {
    destroy(): void {
      cancelAnimationFrame(rafId);
      if (driftInterval !== null) clearInterval(driftInterval);
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
      notifRing.destroy();
      voiceDock.destroy();
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

/**
 * Time-of-day colour drift.
 * Uses a cosine curve (peak warmth at solar noon, coolest at 3am) to shift
 * --paper and --accent toward slightly warmer/dimmer night values.
 * Applied as inline style overrides on #app so tokens.css defaults remain intact.
 *
 * Night targets (hand-tuned to feel like a candle-lit room):
 *   --paper:        #f0ece2  →  #e8e2d6
 *   --accent:       #8a3e26  →  #7a3418
 *   --ink-3:        #9e9b93  →  #8a8780
 */
function applyTimeDrift(app: HTMLElement): void {
  const h = new Date().getHours() + new Date().getMinutes() / 60;
  // t: 1.0 at noon, 0.0 at 3am (cosine, clamped to [0,1])
  const t = Math.max(0, Math.min(1, (Math.cos(((h - 12) / 12) * Math.PI) + 1) / 2));

  const lerp = (a: number, b: number) => Math.round(a + (b - a) * (1 - t));

  // paper: #f4f1ea (244,241,234) → #e8e2d6 (232,226,214)
  const pr = lerp(244, 232); const pg = lerp(241, 226); const pb = lerp(234, 214);
  // accent: #8a3e26 (138,62,38) → #7a3418 (122,52,24)
  const ar = lerp(138, 122); const ag = lerp(62, 52); const ab = lerp(38, 24);

  app.style.setProperty("--paper", `rgb(${pr},${pg},${pb})`);
  app.style.setProperty("--accent", `rgb(${ar},${ag},${ab})`);
  // paper-2 is paper darkened ~3%; approximate
  const p2r = Math.max(0, pr - 8); const p2g = Math.max(0, pg - 8); const p2b = Math.max(0, pb - 10);
  app.style.setProperty("--paper-2", `rgb(${p2r},${p2g},${p2b})`);
}

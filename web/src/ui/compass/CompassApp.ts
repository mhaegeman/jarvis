import type { Surface } from "@/router";
import { store, events, mic, ensureMic, stopMicStream, tryTransition, log } from "@/main";
import { Topbar } from "./Topbar";
import { Bottombar } from "./Bottombar";
import { OrreryCore } from "./OrreryCore";
import { Ring } from "./Ring";
import { HourLabels } from "./HourLabels";
import { ListeningRim } from "./ListeningRim";
import { UnderCore } from "./UnderCore";

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
  new HourLabels(disc);
  const orrery = new OrreryCore(disc);
  const rim = new ListeningRim(disc);
  const underCore = new UnderCore(disc);

  const hourLabels = { render: (): void => { /* HourLabels updates itself internally */ } };
  void hourLabels;

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

  // Overlay helpers — stubs until Step 4 wires real content
  function openCodeFocus(): void {
    if (overlayEl) return;
    app.classList.add("dim");
    overlayEl = document.createElement("div");
    overlayEl.className = "overlay";
    overlayEl.innerHTML = `<div class="focus-card">
      <button class="close" aria-label="Close">esc · close</button>
      <div class="focus-head"><span class="kicker">Focus · Code review</span></div>
      <p style="font-family:var(--mono);font-size:11px;color:var(--ink-3);margin:0">
        Code focus — wired in Step 4
      </p>
    </div>`;
    overlayEl.addEventListener("click", (e) => { if (e.target === overlayEl) closeOverlay(); });
    overlayEl.querySelector(".close")?.addEventListener("click", closeOverlay);
    app.appendChild(overlayEl);
  }
  function openCalendarTakeover(): void {
    if (overlayEl) return;
    app.classList.add("dim");
    overlayEl = document.createElement("div");
    overlayEl.className = "overlay";
    overlayEl.innerHTML = `<div class="takeover-card">
      <button class="close" style="position:absolute;top:14px;right:18px;font-family:var(--mono);font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:var(--ink-3);background:none;border:none;cursor:pointer;" aria-label="Close">esc · close</button>
      <div class="now-eyebrow">Calendar takeover — wired in Step 4</div>
    </div>`;
    overlayEl.addEventListener("click", (e) => { if (e.target === overlayEl) closeOverlay(); });
    overlayEl.querySelector(".close")?.addEventListener("click", closeOverlay);
    app.appendChild(overlayEl);
  }

  // Render loop
  let rafId: number;
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
    orrery.render(s.state);

    if (s.state === "listening") rim.show();
    else rim.hide();

    underCore.render(s.state, s.centerTitle);

    // Zen mode sync
    if (zenMode !== app.classList.contains("zen")) {
      app.classList.toggle("zen", zenMode);
    }

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
      app.innerHTML = "";
    },
  };
}

import type { EventSource as IEventSource } from "@/events/eventSource";
import { WSEventSource } from "@/events/wsEventSource";
import { MockEventSource } from "@/events/mockEventSource";

export interface ConnectOptions {
  url: string;
  audioCtx?: AudioContext;
  openTimeoutMs?: number;
}

export interface ConnectResult {
  events: IEventSource;
  mode: "live" | "demo";
}

export async function connect(opts: ConnectOptions): Promise<ConnectResult> {
  const timeoutMs = opts.openTimeoutMs ?? 1000;
  const live = new WSEventSource({
    url: opts.url,
    audioCtx: opts.audioCtx,
  });
  const mode = await new Promise<"live" | "demo">((resolve) => {
    let done = false;
    const finish = (m: "live" | "demo"): void => {
      if (done) return;
      done = true;
      resolve(m);
    };
    live
      .start()
      .then(() => finish("live"))
      .catch(() => finish("demo"));
    setTimeout(() => finish("demo"), timeoutMs);
  });
  if (mode === "live") return { events: live, mode };
  live.stop();
  const mock = new MockEventSource();
  await mock.start();
  return { events: mock, mode: "demo" };
}

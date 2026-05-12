import type { EventSource as IEventSource } from "@/events/eventSource";
import { WSEventSource } from "@/events/wsEventSource";
import { MockEventSource } from "@/events/mockEventSource";

export interface ConnectOptions {
  url: string;
  audioCtx?: AudioContext;
  openTimeoutMs?: number;
  micSource?: () => Promise<MediaStreamAudioSourceNode>;
}

export interface ConnectResult {
  events: IEventSource;
  mode: "live" | "demo";
}

/**
 * Append the cached bearer token (if any) to a WS URL as ``?token=…``.
 *
 * Browsers can't send custom headers on the WS upgrade, so the server
 * accepts the same bearer token via query string. Exported for tests.
 */
export function withAuthToken(url: string): string {
  if (typeof sessionStorage === "undefined") return url;
  const token = sessionStorage.getItem("jarvis_token");
  if (!token) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}

export async function connect(opts: ConnectOptions): Promise<ConnectResult> {
  const timeoutMs = opts.openTimeoutMs ?? 1000;
  const live = new WSEventSource({
    url: withAuthToken(opts.url),
    ...(opts.audioCtx ? { audioCtx: opts.audioCtx } : {}),
    ...(opts.micSource ? { micSource: opts.micSource } : {}),
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

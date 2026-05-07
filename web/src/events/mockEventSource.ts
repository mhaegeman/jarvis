import type { EventSource } from "./eventSource";
import type { EventName, EventMap, EventHandler } from "@/types";

export class MockEventSource implements EventSource {
  private handlers: { [K in EventName]?: Set<EventHandler<K>> } = {};
  private started = false;

  async start(): Promise<void> {
    this.started = true;
    await Promise.resolve();
    this.emit("ready", undefined);
  }

  stop(): void {
    this.started = false;
    this.handlers = {};
  }

  beginListening(): void {
    /* full impl in Task 18 */
  }
  endListening(): void {
    /* full impl in Task 18 */
  }
  sendText(_text: string): void {
    /* full impl in Task 18 */
  }
  interrupt(): void {
    /* full impl in Task 18 */
  }

  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void {
    let set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    if (!set) {
      set = new Set();
      this.handlers[event] = set as never;
    }
    set.add(handler);
    return () => {
      set?.delete(handler);
    };
  }

  protected emit<E extends EventName>(event: E, payload: EventMap[E]): void {
    if (!this.started && event !== "ready") return;
    const set = this.handlers[event] as Set<EventHandler<E>> | undefined;
    set?.forEach((h) => h(payload));
  }
}

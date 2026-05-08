import type { EventName, EventHandler } from "@/types";

export interface EventSource {
  start(): Promise<void>;
  stop(): void;
  beginListening(): void | Promise<void>;
  endListening(): void;
  sendText(text: string): void;
  interrupt(): void;
  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void;
}

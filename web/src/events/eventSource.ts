import type { EventName, EventHandler, Speaker } from "@/types";

export interface EventSource {
  start(): Promise<void>;
  stop(): void;
  beginListening(): void | Promise<void>;
  endListening(): void;
  sendText(text: string): void;
  interrupt(): void;
  /** Request a one-shot Google Calendar sync. Updates arrive as `calendar.update`. */
  syncCalendar(): void;
  /** Speaker of the currently-playing audio chunk (audio-driven, lags tokens). */
  currentSpeaker(): Speaker | null;
  on<E extends EventName>(event: E, handler: EventHandler<E>): () => void;
}

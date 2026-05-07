import type { ConvState } from "@/types";

export type ConvEvent =
  | "startListening"
  | "stopListening"
  | "cancelListening"
  | "replyStart"
  | "replyEnd"
  | "interrupt";

const TABLE: Record<ConvState, Partial<Record<ConvEvent, ConvState>>> = {
  idle: { startListening: "listening", interrupt: "idle" },
  listening: { stopListening: "thinking", cancelListening: "idle", interrupt: "idle" },
  thinking: { replyStart: "speaking", interrupt: "idle" },
  speaking: { replyEnd: "idle", interrupt: "idle" },
};

export function canTransition(from: ConvState, event: ConvEvent): boolean {
  return TABLE[from][event] !== undefined;
}

export function transition(from: ConvState, event: ConvEvent): ConvState {
  const next = TABLE[from][event];
  if (next === undefined) {
    throw new Error(`invalid transition: ${from} + ${event}`);
  }
  return next;
}

export type ConvState = "idle" | "listening" | "thinking" | "speaking";

export interface TelemetryEvent {
  ts: number; // epoch ms
  level: "info" | "ok" | "warn" | "error";
  message: string;
}

export interface SttPartial {
  text: string;
}
export interface SttFinal {
  text: string;
}
export interface LlmToken {
  delta: string;
}
export interface TtsSentence {
  text: string;
  audioId: string;
}
export interface TtsAudioChunk {
  audioId: string;
  samples: Float32Array;
}
export interface TtsEnd {
  audioId: string;
}
export interface ProtocolError {
  code: string;
  message: string;
}

export type EventMap = {
  ready: void;
  "stt.partial": SttPartial;
  "stt.final": SttFinal;
  "llm.token": LlmToken;
  "llm.end": void;
  "tts.sentence": TtsSentence;
  "tts.audioChunk": TtsAudioChunk;
  "tts.end": TtsEnd;
  error: ProtocolError;
  telemetry: TelemetryEvent;
};

export type EventName = keyof EventMap;
export type EventHandler<E extends EventName> = (payload: EventMap[E]) => void;

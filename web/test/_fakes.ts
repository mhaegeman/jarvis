type Listener = (ev: MessageEvent | Event | CloseEvent) => void;

export class FakeWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];
  static install(): { restore: () => void } {
    const original = (globalThis as { WebSocket?: typeof WebSocket }).WebSocket;
    (globalThis as { WebSocket: unknown }).WebSocket = FakeWebSocket;
    return {
      restore: () => {
        (globalThis as { WebSocket: unknown }).WebSocket = original as typeof WebSocket;
        FakeWebSocket.instances = [];
      },
    };
  }
  url: string;
  readyState = 0;
  binaryType: "arraybuffer" | "blob" = "arraybuffer";
  sent: (string | ArrayBuffer)[] = [];
  private listeners: Record<string, Listener[]> = {};
  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
  addEventListener(type: string, fn: Listener): void {
    (this.listeners[type] ??= []).push(fn);
  }
  removeEventListener(type: string, fn: Listener): void {
    this.listeners[type] = (this.listeners[type] ?? []).filter((f) => f !== fn);
  }
  send(data: string | ArrayBuffer): void {
    this.sent.push(data);
  }
  close(): void {
    if (this.readyState === FakeWebSocket.CLOSED) return;
    this.readyState = FakeWebSocket.CLOSED;
    this.fire("close", new Event("close"));
  }
  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.fire("open", new Event("open"));
  }
  receiveText(s: string): void {
    this.fire("message", new MessageEvent("message", { data: s }));
  }
  receiveBinary(buf: ArrayBuffer): void {
    this.fire("message", new MessageEvent("message", { data: buf }));
  }
  fail(): void {
    this.fire("error", new Event("error"));
    this.close();
  }
  private fire(type: string, ev: Event): void {
    for (const fn of this.listeners[type] ?? []) fn(ev);
  }
}

export class FakeAudioBuffer {
  duration: number;
  constructor(
    public numberOfChannels: number,
    public length: number,
    public sampleRate: number,
  ) {
    this.duration = length / sampleRate;
  }
  getChannelData(_ch: number): Float32Array {
    return new Float32Array(this.length);
  }
}

export class FakeAudioBufferSourceNode {
  buffer: FakeAudioBuffer | null = null;
  startCalls: number[] = [];
  stopCalls: number[] = [];
  connected: unknown[] = [];
  onended: (() => void) | null = null;
  connect(node: unknown): unknown {
    this.connected.push(node);
    return node;
  }
  start(t: number): void {
    this.startCalls.push(t);
  }
  stop(t?: number): void {
    this.stopCalls.push(t ?? 0);
    queueMicrotask(() => this.onended?.());
  }
}

export class FakeAnalyserNode {
  fftSize = 2048;
  frequencyBinCount = 1024;
  getFloatTimeDomainData(arr: Float32Array): void {
    arr.fill(0);
  }
  connect(node: unknown): unknown {
    return node;
  }
}

export class FakeAudioContext {
  currentTime = 0;
  sampleRate = 48000;
  destination = {};
  sources: FakeAudioBufferSourceNode[] = [];
  analyser = new FakeAnalyserNode();
  state: "running" | "suspended" | "closed" = "running";
  createBuffer(channels: number, length: number, rate: number): FakeAudioBuffer {
    return new FakeAudioBuffer(channels, length, rate);
  }
  createBufferSource(): FakeAudioBufferSourceNode {
    const src = new FakeAudioBufferSourceNode();
    this.sources.push(src);
    return src;
  }
  createAnalyser(): FakeAnalyserNode {
    return this.analyser;
  }
  resume(): Promise<void> {
    this.state = "running";
    return Promise.resolve();
  }
  close(): Promise<void> {
    this.state = "closed";
    return Promise.resolve();
  }
}

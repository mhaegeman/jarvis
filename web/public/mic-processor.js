class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frame = new Float32Array(1600);
    this.fill = 0;
  }
  process(inputs) {
    const ch = inputs[0]?.[0];
    if (!ch) return true;
    let i = 0;
    while (i < ch.length) {
      const room = this.frame.length - this.fill;
      const n = Math.min(room, ch.length - i);
      this.frame.set(ch.subarray(i, i + n), this.fill);
      this.fill += n;
      i += n;
      if (this.fill === this.frame.length) {
        this.port.postMessage(this.frame.slice());
        this.fill = 0;
      }
    }
    return true;
  }
}
registerProcessor("mic-processor", MicProcessor);

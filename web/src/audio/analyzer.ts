/** Root-mean-square amplitude of a buffer of mono float samples in [-1, 1]. */
export function rms(buf: Float32Array): number {
  if (buf.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < buf.length; i++) {
    const v = buf[i] ?? 0;
    sum += v * v;
  }
  return Math.sqrt(sum / buf.length);
}

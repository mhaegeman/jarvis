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

/**
 * Sample the analyser's time-domain data and return a peak-normalised dB value.
 * Returns -Infinity when silence is detected (RMS == 0). Otherwise returns
 * 20 * log10(rms), clamped to [-80, 0].
 *
 * Pure helper for unit testing; does not allocate per-call when the caller
 * passes a reusable buffer.
 */
export function analyserDb(analyser: AnalyserNode, buf?: Float32Array): number {
  const data = buf ?? new Float32Array(analyser.fftSize);
  analyser.getFloatTimeDomainData(data);
  const r = rms(data);
  if (r === 0) return -Infinity;
  return Math.max(-80, Math.min(0, 20 * Math.log10(r)));
}

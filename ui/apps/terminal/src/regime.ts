/** Data-derived regime indicators — Hurst (R/S) + Wilder ADX from real candle data.
 *  Computed client-side because the dashboard payload does not expose regime values. */

export interface Ohlc {
  h: number;
  l: number;
  c: number;
}

/** R/S Hurst exponent on log returns — 0.5 random walk, >0.5 persistent, <0.5 mean-reverting.
 *  Classic multi-scale R/S (Peters): mean-center the returns, build the cumulative deviate
 *  bridge, R = bridge range, S = return std, slope of log(R/S) vs log(lag) = H.
 *  Note: drift alone is invisible to R/S (returns are centered) — pair with ADX for trend. */
export function hurst(closes: number[]): number {
  if (closes.length < 40) return 0.5;
  const logP: number[] = closes.map((v) => Math.log(Math.max(v, 1e-12)));
  const rets: number[] = [];
  for (let i = 1; i < logP.length; i++) rets.push(logP[i]! - logP[i - 1]!);
  const n = rets.length;

  const logLags: number[] = [];
  const logRs: number[] = [];
  // start at lag 8 — the classic R/S small-lag artifact (every 2-point window gives
  // R/S≈1) otherwise anchors the regression and inflates the slope
  for (let lag = 8; lag <= Math.floor(n / 2); lag = Math.max(lag + 1, Math.floor(lag * 1.5))) {
    const m = Math.floor(n / lag);
    let rsSum = 0;
    let cnt = 0;
    for (let j = 0; j < m; j++) {
      const seg = rets.slice(j * lag, j * lag + lag);
      const mu = seg.reduce((a, b) => a + b, 0) / lag;
      const centered = seg.map((v) => v - mu);
      const cum: number[] = [];
      let acc = 0;
      for (const v of centered) {
        acc += v;
        cum.push(acc);
      }
      const R = Math.max(...cum) - Math.min(...cum);
      const S = Math.sqrt(centered.reduce((a, b) => a + b * b, 0) / lag);
      if (S > 0) {
        rsSum += R / S;
        cnt++;
      }
    }
    if (cnt > 0) {
      logLags.push(Math.log(lag));
      logRs.push(Math.log(rsSum / cnt));
    }
  }
  if (logLags.length < 2) return 0.5;
  const mx = logLags.reduce((a, b) => a + b, 0) / logLags.length;
  const my = logRs.reduce((a, b) => a + b, 0) / logLags.length;
  let num = 0;
  let den = 0;
  for (let i = 0; i < logLags.length; i++) {
    num += (logLags[i]! - mx) * (logRs[i]! - my);
    den += (logLags[i]! - mx) ** 2;
  }
  if (!den) return 0.5;
  return Math.max(0, Math.min(1, num / den));
}

/** Wilder ADX (14-period) from OHLC — 0–100, >25 = trending. */
export function adx(candles: Ohlc[], period = 14): number {
  if (candles.length < period + 2) return 0;
  let plusDM = 0;
  let minusDM = 0;
  let tr = 0;
  let prevH = candles[0]!.h;
  let prevL = candles[0]!.l;
  let prevC = candles[0]!.c;
  for (let i = 1; i <= period; i++) {
    const c = candles[i]!;
    const up = c.h - prevH;
    const dn = prevL - c.l;
    plusDM += up > dn && up > 0 ? up : 0;
    minusDM += dn > up && dn > 0 ? dn : 0;
    tr += Math.max(c.h - c.l, Math.abs(c.h - prevC), Math.abs(c.l - prevC));
    prevH = c.h;
    prevL = c.l;
    prevC = c.c;
  }
  let pDI = (plusDM / Math.max(tr, 1e-9)) * 100;
  let mDI = (minusDM / Math.max(tr, 1e-9)) * 100;
  let dx = (Math.abs(pDI - mDI) / Math.max(pDI + mDI, 1e-9)) * 100;
  for (let i = period + 1; i < candles.length; i++) {
    const c = candles[i]!;
    const up = c.h - prevH;
    const dn = prevL - c.l;
    const pdm = up > dn && up > 0 ? up : 0;
    const mdm = dn > up && dn > 0 ? dn : 0;
    plusDM = plusDM - plusDM / period + pdm;
    minusDM = minusDM - minusDM / period + mdm;
    tr = tr - tr / period + Math.max(c.h - c.l, Math.abs(c.h - prevC), Math.abs(c.l - prevC));
    pDI = (plusDM / Math.max(tr, 1e-9)) * 100;
    mDI = (minusDM / Math.max(tr, 1e-9)) * 100;
    dx = ((period - 1) * dx + (Math.abs(pDI - mDI) / Math.max(pDI + mDI, 1e-9)) * 100) / period;
    prevH = c.h;
    prevL = c.l;
    prevC = c.c;
  }
  return dx;
}

/** Linear scale — RFC §11: y-axis starts at meaningful zero or data-min. */

export type Scale = (v: number) => number;

export interface LinearScaleOpts {
  min: number;
  max: number;
  range: [number, number]; // [pixelStart, pixelEnd]
  nice?: boolean;
}

/** Pad a range by a fraction and optionally round to "nice" bounds. */
export function niceExtent(min: number, max: number, pad = 0.06): [number, number] {
  if (min === max) {
    const m = min === 0 ? 1 : Math.abs(min) * 0.1;
    return [min - m, max + m];
  }
  const span = max - min;
  return [min - span * pad, max + span * pad];
}

export function linearScale({ min, max, range }: LinearScaleOpts): Scale {
  const [r0, r1] = range;
  const span = max - min || 1;
  return (v: number) => r0 + ((v - min) / span) * (r1 - r0);
}

export function invertLinear(min: number, max: number, range: [number, number], px: number): number {
  const [r0, r1] = range;
  const span = max - min || 1;
  const t = (px - r0) / (r1 - r0);
  return min + t * span;
}

/** "Nice" ticks — returns ~count values including min and max. */
export function niceTicks(min: number, max: number, count = 4): number[] {
  const span = max - min || 1;
  const step0 = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const norm = step0 / mag;
  const step = (norm >= 5 ? 5 : norm >= 2.5 ? 2.5 : norm >= 2 ? 2 : norm >= 1.5 ? 1.5 : 1) * mag;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 0.001; v += step) {
    out.push(Math.round(v * 1e6) / 1e6);
  }
  return out;
}

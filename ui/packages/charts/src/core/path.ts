/** SVG path builders — RFC §11.4: line 1.5px primary / 1px secondary / 0.5px grid. */

export interface Pt {
  x: number;
  y: number;
}

/** Straight polyline. */
export function linePath(pts: Pt[]): string {
  if (!pts.length) return '';
  return pts
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(' ');
}

/** Smooth monotone-ish path (catmull-rom → bezier) for equity/area series. */
export function smoothPath(pts: Pt[]): string {
  if (!pts.length) return '';
  if (pts.length === 1) return `M${pts[0]!.x} ${pts[0]!.y}`;
  let d = `M${pts[0]!.x.toFixed(2)} ${pts[0]!.y.toFixed(2)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]!;
    const p1 = pts[i]!;
    const p2 = pts[i + 1]!;
    const p3 = pts[Math.min(pts.length - 1, i + 2)]!;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C${c1x.toFixed(2)} ${c1y.toFixed(2)} ${c2x.toFixed(2)} ${c2y.toFixed(2)} ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  return d;
}

/** Area fill under a path down to a baseline. */
export function areaPath(pts: Pt[], baseline: number): string {
  if (!pts.length) return '';
  const top = smoothPath(pts);
  const last = pts[pts.length - 1]!;
  const first = pts[0]!;
  return `${top} L${last.x.toFixed(2)} ${baseline} L${first.x.toFixed(2)} ${baseline} Z`;
}

/** Dotted grid — RFC §13.2 DOT MATRIX: pitch 4px, dot 2px, alpha ≤ 40%. */
export function dotGrid(w: number, h: number, pitch = 24): string {
  const dots: string[] = [];
  for (let y = pitch / 2; y < h; y += pitch) {
    for (let x = pitch / 2; x < w; x += pitch) {
      dots.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="1"/>`);
    }
  }
  return dots.join('');
}

/** Horizontal gridlines (RFC §11.2: horizontal 4 levels). */
export function hLines(ys: number[], w: number): string {
  return ys.map((y) => `<line x1="0" y1="${y}" x2="${w}" y2="${y}"/>`).join('');
}

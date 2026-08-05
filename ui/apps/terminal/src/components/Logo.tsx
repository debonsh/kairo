'use client';

/**
 * KAIRO mark — halftone sphere / dot-matrix globe split by a vertical gap
 * (the "K"), wave of probability/data flow inside. RFC §3.2:
 *   - 48×48 unit grid, radius 24, dot pitch 2, gap 4 units wide centered
 *   - sine wave: period 8, amplitude 6 — generated, not drawn
 */

const DOT = 2;
const PITCH = 4; // visually pleasing at small sizes: 2-unit pitch on a 48 grid
const R = 22;
const GAP = 3.5;

interface Pt {
  x: number;
  y: number;
}

function buildDots(): { grid: Pt[]; wave: Pt[] } {
  const grid: Pt[] = [];
  for (let y = -R; y <= R; y += PITCH) {
    for (let x = -R; x <= R; x += PITCH) {
      if (x * x + y * y > R * R) continue;
      // vertical gap (the K) — 4 units wide, centered
      if (Math.abs(x) < GAP) continue;
      grid.push({ x, y });
    }
  }
  const wave: Pt[] = [];
  for (let x = -R; x <= R; x += PITCH) {
    wave.push({ x, y: 6 * Math.sin((x / 8) * 2 * Math.PI) });
  }
  return { grid, wave };
}

export function LogoMark({ size = 44 }: { size?: number }) {
  const { grid, wave } = buildDots();
  const s = size / 48;
  return (
    <svg width={size} height={size} viewBox="-26 -26 52 52" aria-label="KAIRO logo" role="img">
      {grid.map((d, i) => (
        <circle key={`g${i}`} cx={d.x} cy={d.y} r={DOT * s * 0.55} fill="var(--text-primary)" opacity={0.85} />
      ))}
      {wave.map((d, i) => (
        <circle key={`w${i}`} cx={d.x} cy={d.y} r={DOT * s * 0.6} fill={i % 3 === 0 ? 'var(--signal-primary)' : 'var(--ai-primary)'} />
      ))}
      <circle cx={0} cy={0} r={R} fill="none" stroke="var(--border-default)" strokeWidth="1" />
    </svg>
  );
}

export function Wordmark({ size = 28 }: { size?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
      <span
        style={{
          fontFamily: 'var(--font-dot), "IBM Plex Mono", monospace',
          fontSize: size,
          letterSpacing: '0.08em',
          color: 'var(--text-primary)',
        }}
      >
        KAIRO
      </span>
      <span
        style={{
          fontFamily: 'var(--font-plex-mono), "IBM Plex Mono", monospace',
          fontSize: Math.max(7, size * 0.4),
          letterSpacing: '0.12em',
          color: 'var(--text-tertiary)',
          textTransform: 'uppercase',
          whiteSpace: 'nowrap',
        }}
      >
        Autonomous AI Trading System
      </span>
    </div>
  );
}

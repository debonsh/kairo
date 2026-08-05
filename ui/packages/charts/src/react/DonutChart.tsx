import { useMemo } from 'react';

export interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

export interface DonutChartProps {
  segments: DonutSegment[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerSub?: string;
  className?: string;
}

/** Allocation donut — segments colored per RFC §11.10 fixed map (BTC=blue, ETH=lime, …). */
export function DonutChart({ segments, size = 160, thickness = 14, centerLabel, centerSub, className }: DonutChartProps) {
  const arcs = useMemo(() => {
    const total = segments.reduce((a, s) => a + s.value, 0) || 1;
    const r = (size - thickness) / 2;
    const c = size / 2;
    let acc = 0;
    return segments.map((s) => {
      const frac = s.value / total;
      const start = acc * 2 * Math.PI - Math.PI / 2;
      const end = (acc + frac) * 2 * Math.PI - Math.PI / 2;
      acc += frac;
      const x1 = c + r * Math.cos(start);
      const y1 = c + r * Math.sin(start);
      const x2 = c + r * Math.cos(end);
      const y2 = c + r * Math.sin(end);
      const large = frac > 0.5 ? 1 : 0;
      return {
        ...s,
        d: `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`,
      };
    });
  }, [segments, size, thickness]);

  if (!segments.length) {
    return <div className={className} style={{ width: size, height: size, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5C6470', fontSize: 11 }}>NO ALLOCATION</div>;
  }

  return (
    <svg width={size} height={size} className={className} role="img" aria-label="portfolio allocation donut">
      <circle cx={size / 2} cy={size / 2} r={(size - thickness) / 2} fill="none" stroke="#1E2638" strokeWidth={thickness} />
      {arcs.map((a, i) => (
        <path key={i} d={a.d} fill="none" stroke={a.color} strokeWidth={thickness} strokeLinecap="butt" />
      ))}
      {centerLabel && (
        <text x={size / 2} y={size / 2 - 2} textAnchor="middle" fontSize={15} fill="#FFFFFF" fontFamily="'IBM Plex Mono',monospace" fontWeight={600}>
          {centerLabel}
        </text>
      )}
      {centerSub && (
        <text x={size / 2} y={size / 2 + 14} textAnchor="middle" fontSize={8} fill="#5C6470" fontFamily="'IBM Plex Mono',monospace" letterSpacing="0.08em">
          {centerSub}
        </text>
      )}
    </svg>
  );
}

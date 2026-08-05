import { useMemo } from 'react';
import { linearScale, niceExtent } from '../core/scale';

export interface ScatterPoint {
  x: number; // time index
  confidence: number;
  win: boolean;
}

export interface ConfidenceScatterProps {
  points: ScatterPoint[];
  width?: number;
  height?: number;
  winColor?: string;
  lossColor?: string;
  threshold?: number;
  className?: string;
}

/** RFC §12.2 — confidence scatter, threshold tick, outcome-colored dots. */
export function ConfidenceScatter({
  points,
  width = 320,
  height = 110,
  winColor = '#00FF9D',
  lossColor = '#FF6B6B',
  threshold = 0.55,
  className,
}: ConfidenceScatterProps) {
  const { x, y, px } = useMemo(() => {
    const [cmin, cmax] = niceExtent(0.3, 1, 0);
    const x = linearScale({ min: 0, max: Math.max(points.length - 1, 1), range: [8, width - 8] });
    const y = linearScale({ min: cmin, max: cmax, range: [height - 14, 4] });
    const px = points.map((p, i) => ({ ...p, cx: x(i), cy: y(p.confidence) }));
    return { x, y, px };
  }, [points, width, height]);

  if (!points.length) {
    return <div className={className} style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5C6470', fontSize: 11 }}>NO SIGNALS</div>;
  }

  const ty = y(threshold);

  return (
    <svg width={width} height={height} className={className} role="img" aria-label="signal confidence scatter">
      {/* threshold line */}
      <line x1={0} y1={ty} x2={width} y2={ty} stroke="#7C4DFF" strokeWidth="0.5" strokeDasharray="3 3" opacity="0.8" />
      <text x={width - 2} y={ty - 3} textAnchor="end" fontSize={7} fill="#7C4DFF" fontFamily="'IBM Plex Mono',monospace">
        THRESH {threshold.toFixed(2)}
      </text>
      {/* stems + dots */}
      {px.map((p, i) => (
        <g key={i}>
          <line x1={p.cx} y1={p.cy} x2={p.cx} y2={height - 8} stroke={p.win ? winColor : lossColor} strokeWidth="0.5" opacity="0.35" />
          <circle cx={p.cx} cy={p.cy} r={2.4} fill={p.win ? winColor : lossColor} />
        </g>
      ))}
      <text x={2} y={height - 2} fontSize={7} fill="#5C6470" fontFamily="'IBM Plex Mono',monospace">
        12:00 → NOW
      </text>
    </svg>
  );
}

import { useMemo } from 'react';
import { linearScale, niceExtent } from '../core/scale';

export interface HistogramProps {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
  negativeColor?: string;
  format?: (v: number) => string;
  className?: string;
}

/** RFC §11.7 risk gauges & sharpe histogram — bars encode data, never decoration. */
export function Histogram({
  values,
  width = 200,
  height = 80,
  color = '#7C4DFF',
  negativeColor = '#FF6B6B',
  format = (v) => v.toFixed(2),
  className,
}: HistogramProps) {
  const { bars, zero, barW } = useMemo(() => {
    if (!values.length) return { bars: [] as { x: number; y: number; h: number; up: boolean; v: number }[], zero: 0, barW: 6 };
    const [min, max] = niceExtent(Math.min(...values, 0), Math.max(...values, 0), 0.12);
    const x = linearScale({ min: 0, max: values.length - 1, range: [6, width - 6] });
    const y = linearScale({ min, max, range: [height - 12, 2] });
    const bw = Math.max(2, Math.min(14, (width - 12) / values.length * 0.6));
    const bars = values.map((v, i) => {
      const y0 = y(0);
      const yv = y(v);
      return { x: x(i) - bw / 2, y: Math.min(y0, yv), h: Math.max(1, Math.abs(yv - y0)), up: v >= 0, v };
    });
    return { bars, zero: y(0), barW: bw };
  }, [values, width, height]);

  if (!values.length) {
    return <div className={className} style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5C6470', fontSize: 11 }}>NO DATA</div>;
  }

  return (
    <svg width={width} height={height} className={className} role="img" aria-label="histogram">
      <line x1={0} y1={zero} x2={width} y2={zero} stroke="#1E2638" strokeWidth="0.5" />
      {bars.map((b, i) => (
        <rect key={i} x={b.x} y={b.y} width={barW} height={b.h} fill={b.up ? color : negativeColor} opacity="0.9" />
      ))}
    </svg>
  );
}

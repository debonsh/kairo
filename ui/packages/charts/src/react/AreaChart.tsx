import { useMemo, useId } from 'react';
import { linearScale, niceExtent, niceTicks } from '../core/scale';
import { smoothPath, areaPath, dotGrid, hLines } from '../core/path';
import { inrCompact } from '@kairo/lib';

export interface AreaChartProps {
  data: { t: number | string; v: number }[];
  width?: number;
  height?: number;
  color?: string;
  fill?: string;
  yFormat?: (v: number) => string;
  xLabels?: number; // how many time labels to draw
  dotted?: boolean;
  inset?: number;
  asOf?: string;
  className?: string;
}

/** RFC §11.5 equity curve: mist 1.5px line, cyan 8% fill, dotted grid, no truncation. */
export function AreaChart({
  data,
  width = 480,
  height = 160,
  color = '#FFFFFF',
  fill = '#00D4FF',
  yFormat = inrCompact,
  xLabels = 4,
  dotted = true,
  inset = 12,
  asOf,
  className,
}: AreaChartProps) {
  const gid = useId().replace(/:/g, '');
  const { line, area, hlines, yTicks, xTicks, w, h } = useMemo(() => {
    const w = width - inset * 2;
    const h = height - inset * 2 - 14; // reserve footer row
    if (data.length < 2) return { line: '', area: '', hlines: '', yTicks: [], xTicks: [], w, h };
    const [min, max] = niceExtent(Math.min(...data.map((d) => d.v)), Math.max(...data.map((d) => d.v)), 0.08);
    const x = linearScale({ min: 0, max: data.length - 1, range: [0, w] });
    const y = linearScale({ min, max, range: [h, 0] });
    const pts = data.map((d, i) => ({ x: x(i), y: y(d.v) }));
    const ticks = niceTicks(min, max, 4).map((v) => ({ v, y: y(v) }));
    const tIdx = Array.from({ length: Math.min(xLabels, data.length) }, (_, i) =>
      Math.round((i * (data.length - 1)) / Math.max(xLabels - 1, 1)),
    );
    const xTicks = tIdx.map((i) => ({ label: String(data[i]!.t), x: x(i) }));
    return {
      line: smoothPath(pts),
      area: areaPath(pts, h),
      hlines: hLines(ticks.map((t) => t.y), w),
      yTicks: ticks,
      xTicks,
      w,
      h,
    };
  }, [data, width, height, inset, xLabels]);

  if (data.length < 2) {
    return (
      <div className={className} style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5C6470', fontSize: 11 }}>
        NO DATA
      </div>
    );
  }

  return (
    <svg width={width} height={height} className={className} role="img" aria-label="time series chart">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fill} stopOpacity="0.16" />
          <stop offset="100%" stopColor={fill} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {/* plot area */}
      <g transform={`translate(${inset},${inset})`}>
        {dotted && <g fill="#1E2638" opacity="0.5">{dotGrid(w, h, 24)}</g>}
        {!dotted && <g stroke="#1E2638" strokeWidth="0.5" opacity="0.5">{hlines}</g>}
        <path d={area} fill={fill ? `url(#${gid})` : 'none'} />
        <path d={line} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
        {/* y labels */}
        {yTicks.map((t, i) => (
          <text key={i} x={-6} y={t.y + 3} textAnchor="end" fontSize={9} fill="#5C6470" fontFamily="'IBM Plex Mono',monospace">
            {yFormat(t.v)}
          </text>
        ))}
        {/* x labels */}
        {xTicks.map((t, i) => (
          <text key={i} x={t.x} y={h + 12} textAnchor="middle" fontSize={9} fill="#5C6470" fontFamily="'IBM Plex Mono',monospace">
            {t.label}
          </text>
        ))}
      </g>
      {asOf && (
        <text x={width} y={height - 2} textAnchor="end" fontSize={8} fill="#5C6470" fontFamily="'IBM Plex Mono',monospace">
          AS OF {asOf} IST
        </text>
      )}
    </svg>
  );
}

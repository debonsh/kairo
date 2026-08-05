import { useMemo, useId } from 'react';
import { linearScale, niceExtent } from '../core/scale';
import { smoothPath, areaPath, dotGrid } from '../core/path';
import { inrCompact, shortDate } from '@kairo/lib';

export interface EquityDrawdownProps {
  series: { t: number | string; equity: number; drawdown: number }[];
  width?: number;
  height?: number;
  equityColor?: string;
  ddColor?: string;
  className?: string;
}

/** Dual-axis: equity line (mist) on top, drawdown underwater histogram (coral) below. */
export function EquityDrawdown({
  series,
  width = 420,
  height = 220,
  equityColor = '#FFFFFF',
  ddColor = '#FF6B6B',
  className,
}: EquityDrawdownProps) {
  const gid = useId().replace(/:/g, '');
  const padL = 40;
  const padR = 30;
  const padT = 8;
  const ddH = 64;
  const eqH = height - padT - ddH - 22;

  const { eqLine, eqArea, ddBars, ticks, xTicks, x } = useMemo(() => {
    const w = width - padL - padR;
    const [min, max] = niceExtent(Math.min(...series.map((s) => s.equity)), Math.max(...series.map((s) => s.equity)), 0.05);
    const x = linearScale({ min: 0, max: series.length - 1, range: [0, w] });
    const y = linearScale({ min, max, range: [eqH, 2] });
    const pts = series.map((s, i) => ({ x: x(i), y: y(s.equity) }));
    const dmin = Math.min(0, ...series.map((s) => s.drawdown));
    const dy = linearScale({ min: dmin, max: 0, range: [ddH, 0] });
    const ddBars = series.map((s, i) => ({ x: x(i), y: padT + eqH + 4 + dy(s.drawdown), h: Math.max(0, (padT + eqH + 4 + ddH) - (padT + eqH + 4 + dy(s.drawdown))), v: s.drawdown }));
    const ticks = [min, (min + max) / 2, max];
    const step = Math.max(1, Math.floor(series.length / 5));
    const xTicks = series.filter((_, i) => i % step === 0 || i === series.length - 1).map((s, i) => ({ label: shortDate(s.t), x: x(Math.min(i * step, series.length - 1)) }));
    return { eqLine: smoothPath(pts), eqArea: areaPath(pts, eqH), ddBars, ticks, xTicks, x };
  }, [series, width, height]);

  if (!series.length) {
    return <div className={className} style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5C6470', fontSize: 11 }}>NO HISTORY</div>;
  }

  const w = width - padL - padR;

  return (
    <svg width={width} height={height} className={className} role="img" aria-label="equity and drawdown">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={equityColor} stopOpacity="0.12" />
          <stop offset="100%" stopColor={equityColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <g transform={`translate(${padL},${padT})`}>
        <g fill="#1E2638" opacity="0.5">{dotGrid(w, eqH, 24)}</g>
        <path d={eqArea} fill={`url(#${gid})`} />
        <path d={eqLine} fill="none" stroke={equityColor} strokeWidth="1.5" strokeLinejoin="round" />
        {ticks.map((t, i) => (
          <text key={i} x={-6} y={((i / 2) * eqH) + 3} textAnchor="end" fontSize={9} fill="#5C6470" fontFamily="'IBM Plex Mono',monospace">
            {inrCompact(t)}
          </text>
        ))}
        {xTicks.map((t, i) => (
          <text key={i} x={t.x} y={eqH + 16} textAnchor="middle" fontSize={8} fill="#5C6470" fontFamily="'IBM Plex Mono',monospace">
            {t.label}
          </text>
        ))}
        {/* drawdown band */}
        <rect x={0} y={eqH + 4} width={w} height={ddH} fill="#0B0E14" stroke="#1E2638" strokeWidth="0.5" />
        {ddBars.map((b, i) => (
          <rect key={i} x={b.x} y={b.y} width={Math.max(1, w / series.length * 0.6)} height={b.h} fill={ddColor} opacity="0.85" />
        ))}
        <text x={-6} y={eqH + ddH + 3} textAnchor="end" fontSize={8} fill="#5C6470" fontFamily="'IBM Plex Mono',monospace">0%</text>
        <text x={-6} y={eqH + 8} textAnchor="end" fontSize={8} fill="#FF6B6B" fontFamily="'IBM Plex Mono',monospace">DD</text>
      </g>
    </svg>
  );
}

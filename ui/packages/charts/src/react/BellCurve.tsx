import { useMemo } from 'react';
import { linearScale } from '../core/scale';

export interface BellCurveProps {
  mean: number;
  std: number;
  varValue: number; // VaR at 95%
  width?: number;
  height?: number;
  color?: string;
  className?: string;
}

export function BellCurve({ mean, std, varValue, width = 200, height = 90, color = '#7C4DFF', className }: BellCurveProps) {
  const { path, fillPath, vx, x } = useMemo(() => {
    if (!std || std <= 0) return { path: '', fillPath: '', vx: 0, x: () => 0 };
    const lo = mean - 4 * std;
    const hi = mean + 4 * std;
    const x = linearScale({ min: lo, max: hi, range: [4, width - 4] });
    const y = linearScale({ min: 0, max: 1 / (std * Math.sqrt(2 * Math.PI)), range: [height - 6, 3] });
    const N = 80;
    const gauss = (v: number) => Math.exp(-0.5 * ((v - mean) / std) ** 2) / (std * Math.sqrt(2 * Math.PI));
    const pts: string[] = [];
    const fillPts: string[] = [];
    for (let i = 0; i <= N; i++) {
      const v = lo + (i / N) * (hi - lo);
      const px = x(v);
      const py = y(gauss(v));
      pts.push(`${i === 0 ? 'M' : 'L'}${px.toFixed(1)} ${py.toFixed(1)}`);
      if (v <= varValue) fillPts.push(`${i === 0 ? 'M' : 'L'}${px.toFixed(1)} ${py.toFixed(1)}`);
    }
    const vx = x(varValue);
    if (fillPts.length) fillPts.push(`L${vx.toFixed(1)} ${height - 3} L${x(lo).toFixed(1)} ${height - 3} Z`);
    return { path: pts.join(' '), fillPath: fillPts.join(' '), vx, x };
  }, [mean, std, varValue, width, height]);

  if (!std || std <= 0) {
    return <div className={className} style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5C6470', fontSize: 11 }}>NO DIST</div>;
  }

  return (
    <svg width={width} height={height} className={className} role="img" aria-label="returns distribution with VaR">
      {fillPath && <path d={fillPath} fill={color} opacity="0.35" stroke="none" />}
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" />
      <line x1={vx} y1={0} x2={vx} y2={height - 3} stroke="#FF6B6B" strokeWidth="1" />
      <text x={vx} y={height - 6} textAnchor="middle" fontSize={8} fill="#FF6B6B" fontFamily="'IBM Plex Mono',monospace">
        VaR 95%
      </text>
    </svg>
  );
}

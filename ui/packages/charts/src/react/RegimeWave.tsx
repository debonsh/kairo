import { useMemo } from 'react';
import { linearScale, niceExtent } from '../core/scale';
import { smoothPath, dotGrid } from '../core/path';

export interface RegimeWaveProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  className?: string;
}

/** Multicolored wave of normalized closes — regime flavor, data-derived. */
export function RegimeWave({ data, width = 280, height = 84, color = '#00D4FF', className }: RegimeWaveProps) {
  const { path, area, wave } = useMemo(() => {
    if (data.length < 2) return { path: '', area: '', wave: '' };
    const [min, max] = niceExtent(Math.min(...data), Math.max(...data), 0.15);
    const x = linearScale({ min: 0, max: data.length - 1, range: [4, width - 4] });
    const y = linearScale({ min, max, range: [height - 8, 4] });
    const pts = data.map((v, i) => ({ x: x(i), y: y(v) }));
    return {
      path: smoothPath(pts),
      area: pts.length ? `M${pts[0]!.x} ${height - 4} L${pts[0]!.x} ${pts[0]!.y} ` + smoothPath(pts).slice(1) + ` L${pts[pts.length - 1]!.x} ${height - 4} Z` : '',
      wave: '',
    };
  }, [data, width, height]);
  void wave;

  if (data.length < 2) {
    return <div className={className} style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5C6470', fontSize: 11 }}>NO REGIME</div>;
  }

  return (
    <svg width={width} height={height} className={className} role="img" aria-label="market regime wave">
      <g fill="#1E2638" opacity="0.4">{dotGrid(width, height, 20)}</g>
      <path d={area} fill={color} opacity="0.08" stroke="none" />
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

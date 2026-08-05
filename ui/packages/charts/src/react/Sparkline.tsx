import { useId } from 'react';
import { linearScale, niceExtent } from '../core/scale';
import { linePath, areaPath } from '../core/path';

export interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  fill?: string;
  strokeWidth?: number;
  className?: string;
}

/** Minimal inline series — no axes, no grid. Dot-matrix aesthetic on request. */
export function Sparkline({
  data,
  width = 96,
  height = 28,
  color = '#00D4FF',
  fill,
  strokeWidth = 1.5,
  className,
}: SparklineProps) {
  const gid = useId().replace(/:/g, '');
  if (data.length < 2) {
    return <svg width={width} height={height} className={className} aria-label="no data" />;
  }
  const [min, max] = niceExtent(Math.min(...data), Math.max(...data), 0.1);
  const x = linearScale({ min: 0, max: data.length - 1, range: [0, width] });
  const y = linearScale({ min, max, range: [height, 2] });
  const pts = data.map((v, i) => ({ x: x(i), y: y(v) }));
  const line = linePath(pts);
  const area = fill ? areaPath(pts, height) : '';

  return (
    <svg width={width} height={height} className={className} aria-hidden="true" role="img">
      {fill && <defs><linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={fill} stopOpacity="0.35" />
        <stop offset="100%" stopColor={fill} stopOpacity="0" />
      </linearGradient></defs>}
      {area && <path d={area} fill={fill ? `url(#${gid})` : 'none'} stroke="none" />}
      <path d={line} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

import { useMemo, useRef, useState } from 'react';
import { linearScale, niceExtent } from '../core/scale';
import { price } from '@kairo/lib';

export interface Candle {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export interface CandleChartProps {
  candles: Candle[];
  width?: number;
  height?: number;
  upColor?: string;
  downColor?: string;
  grid?: string;
  onSelect?: (c: Candle | null) => void;
  className?: string;
}

/** RFC §11.6: body 1px stroke, up=lime, down=coral; volume sub-pane 40% alpha. */
export function CandleChart({
  candles,
  width = 640,
  height = 320,
  upColor = '#00FF9D',
  downColor = '#FF6B6B',
  grid = '#1E2638',
  onSelect,
  className,
}: CandleChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const volH = 56;
  const mainH = height - volH - 24;
  const padL = 8;
  const padR = 8;

  interface CandleItem {
    c: Candle;
    cx: number;
    up: boolean;
    bodyTop: number;
    bodyBot: number;
    wickTop: number;
    wickBot: number;
    vb: number;
    vt: number;
  }

  const { candleW, x, y, volY, items, last } = useMemo(() => {
    if (!candles.length) {
      return { candleW: 0, x: (() => 0) as (v: number) => number, y: (() => 0) as (v: number) => number, volY: (() => 0) as (v: number) => number, items: [] as CandleItem[], last: null as Candle | null };
    }
    const n = candles.length;
    const w = width - padL - padR;
    const cw = Math.max(1, w / n);
    const [lo, hi] = niceExtent(Math.min(...candles.map((c) => c.l)), Math.max(...candles.map((c) => c.h)), 0.04);
    const [vlo, vhi] = [0, Math.max(...candles.map((c) => c.v)) || 1];
    const x = linearScale({ min: 0, max: n - 1, range: [0, w] });
    const y = linearScale({ min: lo, max: hi, range: [mainH, 4] });
    const volY = linearScale({ min: vlo, max: vhi, range: [volH, 0] });
    const items = candles.map((c, i) => ({
      c,
      cx: padL + x(i) + cw / 2,
      up: c.c >= c.o,
      bodyTop: y(Math.max(c.o, c.c)),
      bodyBot: y(Math.min(c.o, c.c)),
      wickTop: y(c.h),
      wickBot: y(c.l),
      vb: padL + mainH + 6 + volY(c.v),
      vt: padL + mainH + 6,
    }));
    const last = candles[candles.length - 1]!;
    return { candleW: cw, x, y, volY, items, last };
  }, [candles, width, height]);

  if (!candles.length || !last) {
    return <div className={className} style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5C6470', fontSize: 11 }}>NO CANDLE DATA</div>;
  }

  const hi = Math.max(...candles.map((c) => c.h));
  const lo = Math.min(...candles.map((c) => c.l));

  const onMove = (e: React.MouseEvent) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = e.clientX - rect.left - padL;
    const idx = Math.min(candles.length - 1, Math.max(0, Math.floor(px / (candleW || 1))));
    setHover(idx);
    onSelect?.(candles[idx] ?? null);
  };

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      className={className}
      onMouseMove={onMove}
      onMouseLeave={() => {
        setHover(null);
        onSelect?.(null);
      }}
      role="img"
      aria-label="candlestick price chart"
    >
      {/* grid */}
      {[0.2, 0.4, 0.6, 0.8].map((t) => (
        <line key={t} x1={padL} y1={mainH * t} x2={width - padR} y2={mainH * t} stroke={grid} strokeWidth="0.5" opacity="0.5" />
      ))}
      {/* candles */}
      {items.map((it, i) => (
        <g key={i}>
          <line x1={it.cx} x2={it.cx} y1={it.wickTop} y2={it.wickBot} stroke={it.up ? upColor : downColor} strokeWidth="1" />
          <rect
            x={it.cx - Math.max(0.75, candleW * 0.32)}
            y={it.bodyTop}
            width={Math.max(1.5, candleW * 0.64)}
            height={Math.max(1, it.bodyBot - it.bodyTop)}
            fill={it.up ? upColor : downColor}
          />
          {/* volume */}
          <rect x={it.cx - Math.max(0.75, candleW * 0.32)} y={it.vb} width={Math.max(1.5, candleW * 0.64)} height={Math.max(0.5, it.vt - it.vb)} fill={it.up ? upColor : downColor} opacity="0.4" />
        </g>
      ))}
      {/* price labels */}
      <text x={padL + 4} y={10} fontSize={9} fill="#5C6470" fontFamily="'IBM Plex Mono',monospace">{price(hi)}</text>
      <text x={padL + 4} y={mainH + 14} fontSize={9} fill="#5C6470" fontFamily="'IBM Plex Mono',monospace">{price(lo)}</text>
      {/* crosshair */}
      {hover !== null && items[hover] && (
        <g pointerEvents="none">
          <line x1={items[hover]!.cx} x2={items[hover]!.cx} y1={0} y2={height} stroke="#FFFFFF" strokeWidth="0.75" opacity="0.4" />
          <line x1={padL} x2={width - padR} y1={items[hover]!.bodyTop} y2={items[hover]!.bodyTop} stroke="#FFFFFF" strokeWidth="0.5" opacity="0.3" />
          <rect x={items[hover]!.cx + 6} y={4} width={118} height={58} fill="#1E2638" stroke="#1E2638" strokeWidth="0.5" />
          <text x={items[hover]!.cx + 10} y={16} fontSize={8} fill="#9AA3B2" fontFamily="'IBM Plex Mono',monospace">
            {new Date(items[hover]!.c.t).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' })}
          </text>
          {(['o', 'h', 'l', 'c'] as const).map((k, idx) => (
            <text key={k} x={items[hover]!.cx + 10} y={28 + idx * 11} fontSize={8} fill="#FFFFFF" fontFamily="'IBM Plex Mono',monospace">
              {k.toUpperCase()} {price(items[hover]!.c[k])}
            </text>
          ))}
        </g>
      )}
    </svg>
  );
}

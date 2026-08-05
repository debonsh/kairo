import { useMemo } from 'react';

export interface BookLevel {
  price: number;
  size: number;
}

export interface OrderBookProps {
  bids: BookLevel[]; // descending price
  asks: BookLevel[]; // ascending price
  width?: number;
  height?: number;
  bidColor?: string;
  askColor?: string;
  className?: string;
}

/** RFC §11.11 order flow — buy (cyan) vs sell (coral) depth bars. */
export function OrderBook({ bids, asks, width = 260, height = 220, bidColor = '#00D4FF', askColor = '#FF6B6B', className }: OrderBookProps) {
  const mid = useMemo(() => {
    const b = bids[0]?.price ?? 0;
    const a = asks[0]?.price ?? 0;
    return b && a ? (b + a) / 2 : b || a;
  }, [bids, asks]);

  const maxSize = useMemo(
    () => Math.max(1, ...bids.map((b) => b.size), ...asks.map((a) => a.size)),
    [bids, asks],
  );

  if (!bids.length && !asks.length) {
    return <div className={className} style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5C6470', fontSize: 11 }}>NO DEPTH</div>;
  }

  const rowH = Math.max(8, Math.min(14, height / Math.max(bids.length + asks.length, 8)));
  const asksTop = Math.max(0, (height - (bids.length + asks.length) * rowH) / 2);

  return (
    <svg width={width} height={height} className={className} role="img" aria-label="order book depth">
      {/* asks (top, coral) */}
      {asks.map((a, i) => {
        const y = asksTop + i * rowH;
        const w = (a.size / maxSize) * (width - 70);
        return (
          <g key={`a${i}`}>
            <rect x={width - 70 - w} y={y} width={w} height={rowH - 1} fill={askColor} opacity="0.22" />
            <text x={width - 68} y={y + rowH - 3} fontSize={8} fill="#9AA3B2" textAnchor="start" fontFamily="'IBM Plex Mono',monospace">
              {a.price.toFixed(4)}
            </text>
          </g>
        );
      })}
      {/* bids (bottom, cyan) */}
      {bids.map((b, i) => {
        const y = asksTop + (asks.length + i) * rowH;
        const w = (b.size / maxSize) * (width - 70);
        return (
          <g key={`b${i}`}>
            <rect x={2} y={y} width={w} height={rowH - 1} fill={bidColor} opacity="0.22" />
            <text x={4} y={y + rowH - 3} fontSize={8} fill="#9AA3B2" fontFamily="'IBM Plex Mono',monospace">
              {b.price.toFixed(4)}
            </text>
          </g>
        );
      })}
      {/* mid line */}
      <line x1={0} y1={asksTop + asks.length * rowH} x2={width} y2={asksTop + asks.length * rowH} stroke="#1E2638" strokeWidth="0.75" />
      <text x={width - 2} y={asksTop + asks.length * rowH - 3} fontSize={8} fill="#5C6470" textAnchor="end" fontFamily="'IBM Plex Mono',monospace">
        {mid.toFixed(4)}
      </text>
    </svg>
  );
}

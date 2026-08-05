import type { ReactNode } from 'react';

export interface Column<T> {
  key: string;
  label: string;
  align?: 'left' | 'right' | 'center';
  width?: string;
  render: (row: T) => ReactNode;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  empty?: string;
  /** Must return a unique key per row. Receives the index for feeds with duplicate field values. */
  rowKey: (row: T, index: number) => string;
}

/** RFC §10.6 — sticky header, tabular nums, row hover 8% raised. */
export function DataTable<T>({ columns, rows, empty = 'NO DATA', rowKey }: DataTableProps<T>) {
  return (
    <div style={{ overflow: 'auto', maxHeight: '100%' }} role="grid" aria-label="data table">
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: "'IBM Plex Mono',monospace" }}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                style={{
                  textAlign: c.align ?? 'left',
                  padding: '6px 12px',
                  fontSize: 10,
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  color: '#5C6470',
                  fontWeight: 500,
                  borderBottom: '1px solid #1E2638',
                  position: 'sticky',
                  top: 0,
                  background: '#12161F',
                  whiteSpace: 'nowrap',
                }}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={rowKey(row, index)}
              style={{ borderBottom: '1px solid #1E2638', transition: 'background 120ms', cursor: 'default' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#1E263814')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  style={{
                    textAlign: c.align ?? 'left',
                    padding: '5px 12px',
                    fontSize: 11,
                    color: '#9AA3B2',
                    fontVariantNumeric: 'tabular-nums',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={columns.length} style={{ padding: 24, textAlign: 'center', fontSize: 11, color: '#5C6470' }}>
                {empty}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

/** Side badge: LONG (lime) / SHORT (coral) with glyph (R4.4). */
export function SideBadge({ side }: { side: string }) {
  const long = /long|buy/i.test(side);
  const color = long ? '#00FF9D' : '#FF6B6B';
  const glyph = long ? '▲' : '▼';
  return (
    <span style={{ color, fontWeight: 600, fontSize: 11 }}>
      {glyph} {side.toUpperCase()}
    </span>
  );
}

/** Signed P/L cell with +/− glyph and color (R4.4: never color-only). */
export function PnlCell({ value, decimals = 2, prefix = '₹' }: { value: number; decimals?: number; prefix?: string }) {
  const color = value > 0 ? '#00FF9D' : value < 0 ? '#FF6B6B' : '#9AA3B2';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return (
    <span style={{ color, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
      {sign}
      {prefix}
      {Math.abs(value).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}
    </span>
  );
}

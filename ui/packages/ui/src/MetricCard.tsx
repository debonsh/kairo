import type { ReactNode } from 'react';
import { Badge } from './primitives';

export interface MetricCardProps {
  label: string;
  value: string;
  delta?: string;
  deltaColor?: string;
  spark?: ReactNode;
  badge?: ReactNode;
  sub?: string;
  valueColor?: string;
  dataSource?: string;
}

/** One L1 metric per card (RFC R7.4). Label above, value 24–36px mono. */
export function MetricCard({ label, value, delta, deltaColor = '#9AA3B2', spark, badge, sub, valueColor = '#FFFFFF', dataSource }: MetricCardProps) {
  return (
    <div style={{ padding: '14px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#5C6470' }}>
          {label}
        </span>
        {badge}
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8 }}>
        <div>
          <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 26, lineHeight: 1.1, fontWeight: 600, color: valueColor, fontVariantNumeric: 'tabular-nums' }}>
            {value}
          </div>
          {delta && (
            <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, color: deltaColor, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>
              {delta}
            </div>
          )}
          {sub && <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 10, color: '#5C6470', marginTop: 2 }}>{sub}</div>}
        </div>
        {spark}
      </div>
      {dataSource && (
        <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 8, color: '#5C6470', marginTop: 8, letterSpacing: '0.04em' }}>
          {dataSource}
        </div>
      )}
    </div>
  );
}

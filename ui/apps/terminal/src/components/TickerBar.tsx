'use client';

import { useEffect, useRef, useState } from 'react';
import { istTime } from '@kairo/lib';
import type { LogLine } from '@kairo/ui';
import { useKairo } from '../kairo-data';
import { useLogStream } from '../log-stream';

const LEVEL_COLOR: Record<LogLine['level'], string> = {
  INFO: 'var(--text-secondary)',
  WARN: 'var(--status-warn)',
  ERROR: 'var(--status-danger)',
  OK: 'var(--status-live)',
  LLM: 'var(--ai-primary)',
};

/** Z3 — 28px live log ticker (dashboard-2 sheet): newest lines on the right, ● LIVE + IST clock. */
export function TickerBar() {
  const lines = useLogStream((s) => s.lines);
  const apiOnline = useKairo((s) => s.apiOnline);
  const [clock, setClock] = useState(istTime());
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const iv = setInterval(() => setClock(istTime()), 1000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [lines]);

  return (
    <footer
      style={{
        height: 28,
        display: 'flex',
        alignItems: 'center',
        background: 'var(--surface-panel)',
        borderTop: '1px solid var(--border-default)',
        position: 'sticky',
        bottom: 0,
        zIndex: 100,
        overflow: 'hidden',
        fontFamily: "'IBM Plex Mono',monospace",
        fontSize: 10,
        flexShrink: 0,
      }}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0 12px', letterSpacing: '0.08em', color: 'var(--text-secondary)', whiteSpace: 'nowrap', borderRight: '1px solid var(--border-default)', height: '100%' }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: apiOnline ? 'var(--status-live)' : 'var(--status-danger)', display: 'inline-block' }} />
        SYSTEM LOG
      </span>
      <div ref={scrollRef} style={{ flex: 1, overflowX: 'auto', overflowY: 'hidden', scrollbarWidth: 'none', height: '100%', display: 'flex', alignItems: 'center' }} aria-live="polite">
        <div style={{ display: 'inline-flex', gap: 24, whiteSpace: 'nowrap', paddingLeft: 12 }}>
          {lines.length === 0 && <span style={{ color: 'var(--text-tertiary)', letterSpacing: '0.06em' }}>AWAITING EVENTS…</span>}
          {lines.slice(-24).map((l, i) => (
            <span key={i} style={{ display: 'inline-flex', gap: 6 }}>
              <span style={{ color: 'var(--text-tertiary)' }}>{l.t}</span>
              <span style={{ color: LEVEL_COLOR[l.level], fontWeight: 600 }}>[{l.level}]</span>
              <span style={{ color: l.level === 'ERROR' ? 'var(--status-danger)' : 'var(--text-secondary)' }}>{l.text}</span>
            </span>
          ))}
        </div>
      </div>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0 12px', whiteSpace: 'nowrap', borderLeft: '1px solid var(--border-default)', height: '100%' }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--status-live)', display: 'inline-block', animation: 'kairoPulse 1.2s ease-in-out infinite' }} />
        <span style={{ color: 'var(--status-live)', letterSpacing: '0.08em', fontWeight: 600 }}>LIVE</span>
      </span>
      <span style={{ padding: '0 12px', color: 'var(--text-tertiary)', whiteSpace: 'nowrap', borderLeft: '1px solid var(--border-default)', height: '100%', display: 'inline-flex', alignItems: 'center', fontVariantNumeric: 'tabular-nums' }}>
        {clock} IST
      </span>
    </footer>
  );
}

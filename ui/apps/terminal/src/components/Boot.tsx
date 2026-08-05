'use client';

import { useEffect, useState } from 'react';
import { LogoMark } from './Logo';

const LINES = [
  '> kairo.run --live',
  'SYSTEM ONLINE',
  '[OK] DATA FEED / RISK ENGINE / LLM ENGINE / SAFETY GATE / TRADING',
];

export function Boot({ onDone }: { onDone: () => void }) {
  const [lineCount, setLineCount] = useState(0);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const t1 = setTimeout(() => setLineCount(1), 200);
    const t2 = setTimeout(() => setLineCount(2), 400);
    const t3 = setTimeout(() => setLineCount(3), 600);
    const t4 = setTimeout(() => setLeaving(true), 1400);
    const t5 = setTimeout(onDone, 1700);
    return () => [t1, t2, t3, t4, t5].forEach(clearTimeout);
  }, [onDone]);

  return (
    <div
      role="presentation"
      onClick={onDone}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 2000,
        background: 'var(--surface-base)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 18,
        cursor: 'pointer',
        transition: 'opacity 300ms linear',
        opacity: leaving ? 0 : 1,
      }}
      aria-label="KAIRO boot sequence — click to skip"
    >
      <div style={{ animation: 'kairoDotIn 200ms ease-out' }}>
        <LogoMark size={72} />
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontFamily: 'var(--font-dot), "IBM Plex Mono", monospace', fontSize: 44, letterSpacing: '0.08em', color: 'var(--text-primary)', animation: 'kairoDotIn 200ms ease-out' }}>
          KAIRO
        </div>
        <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, letterSpacing: '0.12em', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginTop: 4 }}>
          Autonomous AI Trading System
        </div>
      </div>
      <div style={{ width: 340, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.9, minHeight: 66 }}>
        {LINES.slice(0, lineCount).map((l, i) => (
          <div key={i} style={{ animation: 'kairoLineIn 120ms ease-out' }}>
            <span style={{ color: i > 0 ? 'var(--status-live)' : 'var(--text-tertiary)' }}>{l}</span>
          </div>
        ))}
        <span style={{ display: 'inline-block', width: 7, height: 12, background: 'var(--signal-primary)', animation: 'kairoBlink 1s steps(2) infinite', verticalAlign: 'text-bottom' }} />
      </div>
      <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: 'var(--text-tertiary)' }}>CLICK TO SKIP</div>
    </div>
  );
}

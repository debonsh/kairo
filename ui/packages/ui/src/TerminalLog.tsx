import { useEffect, useRef } from 'react';

export interface LogLine {
  t: string;
  text: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'OK' | 'LLM';
}

export interface TerminalLogProps {
  lines: LogLine[];
  height?: number | string;
  label?: string;
}

const LEVEL_COLOR: Record<LogLine['level'], string> = {
  INFO: '#9AA3B2',
  WARN: '#FFB800',
  ERROR: '#FF6B6B',
  OK: '#00FF9D',
  LLM: '#7C4DFF',
};

/** RFC §12.3 — terminal lines with block cursor ▍; no shimmer, no typewriter. */
export function TerminalLog({ lines, height = 120, label }: TerminalLogProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  return (
    <div
      ref={ref}
      aria-label={label ?? 'terminal log'}
      aria-live="polite"
      style={{
        height,
        overflowY: 'auto',
        background: '#0B0E14',
        border: '1px solid #1E2638',
        borderRadius: 2,
        padding: '8px 10px',
        fontFamily: "'IBM Plex Mono',monospace",
        fontSize: 11,
        lineHeight: 1.7,
      }}
    >
      {lines.map((l, i) => (
        <div key={i} style={{ whiteSpace: 'nowrap', color: '#9AA3B2' }}>
          <span style={{ color: '#5C6470' }}>[{l.t}]</span>{' '}
          <span style={{ color: LEVEL_COLOR[l.level], fontWeight: 500 }}>[{l.level}]</span>{' '}
          <span style={{ color: l.level === 'ERROR' ? '#FF6B6B' : '#9AA3B2' }}>{l.text}</span>
        </div>
      ))}
      <div style={{ display: 'inline-block', width: 7, height: 12, background: '#00D4FF', animation: 'kairoBlink 1s steps(2) infinite', verticalAlign: 'text-bottom', marginLeft: 2 }} aria-hidden="true" />
    </div>
  );
}

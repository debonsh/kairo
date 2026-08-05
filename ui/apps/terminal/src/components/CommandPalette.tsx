'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { postControl } from '@kairo/lib';

export interface PaletteAction {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
}

export interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  actions: PaletteAction[];
}

export function CommandPalette({ open, onClose, actions }: CommandPaletteProps) {
  const [q, setQ] = useState('');
  const [idx, setIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQ('');
      setIdx(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  const results = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return actions;
    return actions.filter((a) => a.label.toLowerCase().includes(query));
  }, [q, actions]);

  useEffect(() => {
    if (idx >= results.length) setIdx(0);
  }, [results, idx]);

  if (!open) return null;

  const pick = (i: number) => {
    const a = results[i];
    if (a) a.run();
    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="command palette"
      style={{ position: 'fixed', inset: 0, background: 'rgba(8, 8, 11, 0.6)', zIndex: 1500, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '18vh' }}
      onPointerDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div style={{ width: 520, maxWidth: '92vw', background: 'var(--surface-panel)', border: '1px solid var(--border-default)', borderRadius: 4, boxShadow: '0 8px 24px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 14px', borderBottom: '1px solid var(--border-default)' }}>
          <span style={{ color: 'var(--signal-primary)', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 13 }}>❯</span>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setIdx(0);
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault();
                setIdx((i) => Math.min(i + 1, results.length - 1));
              } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setIdx((i) => Math.max(i - 1, 0));
              } else if (e.key === 'Enter') {
                pick(idx);
              } else if (e.key === 'Escape') {
                onClose();
              }
            }}
            placeholder="Type a command…"
            aria-label="command input"
            style={{ flex: 1, height: 44, background: 'transparent', border: 'none', outline: 'none', color: 'var(--text-primary)', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 13 }}
          />
          <kbd style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: 'var(--text-tertiary)', border: '1px solid var(--border-default)', borderRadius: 2, padding: '2px 6px' }}>ESC</kbd>
        </div>
        <div style={{ maxHeight: 300, overflowY: 'auto', padding: 6 }}>
          {results.map((a, i) => (
            <button
              key={a.id}
              onMouseEnter={() => setIdx(i)}
              onClick={() => pick(i)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                padding: '8px 12px',
                background: i === idx ? 'rgba(0, 229, 255, 0.07)' : 'transparent',
                border: 'none',
                borderLeft: i === idx ? '2px solid var(--signal-primary)' : '2px solid transparent',
                color: i === idx ? 'var(--signal-primary)' : 'var(--text-secondary)',
                fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace",
                fontSize: 12,
                letterSpacing: '0.04em',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <span>{a.label}</span>
              {a.hint && <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{a.hint}</span>}
            </button>
          ))}
          {!results.length && (
            <div style={{ padding: 20, textAlign: 'center', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 11, color: 'var(--text-tertiary)' }}>
              NO MATCHES
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Build the palette actions. */
export function paletteActions(onLog: (level: 'INFO' | 'WARN' | 'ERROR' | 'OK' | 'LLM', text: string) => void): PaletteAction[] {
  return [
    { id: 'kill', label: 'KILL SWITCH — STOP TRADING', hint: 'DANGER', run: () => void postControl('stop').then(() => onLog('ERROR', 'KILL SWITCH EXECUTED — ALL POSITIONS LIQUIDATED')).catch(() => onLog('ERROR', 'KILL FAILED — API OFFLINE')) },
    { id: 'pause', label: 'PAUSE TRADING', run: () => void postControl('pause').then(() => onLog('OK', 'TRADING PAUSED')).catch(() => onLog('ERROR', 'PAUSE FAILED — API OFFLINE')) },
    { id: 'resume', label: 'RESUME TRADING', run: () => void postControl('resume').then(() => onLog('OK', 'TRADING RESUMED')).catch(() => onLog('ERROR', 'RESUME FAILED — API OFFLINE')) },
    { id: 'dense', label: 'DENSITY: DENSE (DEFAULT)', run: () => document.documentElement.style.setProperty('--density', 'dense') },
    { id: 'compact', label: 'DENSITY: COMPACT', run: () => document.documentElement.style.setProperty('--density', 'compact') },
    { id: 'comfortable', label: 'DENSITY: COMFORTABLE', run: () => document.documentElement.style.setProperty('--density', 'comfortable') },
  ];
}

import { useEffect, useRef, useState } from 'react';

export interface KillSwitchProps {
  armed: boolean;
  executing?: boolean;
  onExecute: () => Promise<void> | void;
  holdMs?: number;
  compact?: boolean;
}

/**
 * RFC §10.9 — hold-to-arm (1.2s) → modal with typed "CONFIRM" → execute.
 * UI reflects server state only (no optimistic "killed" state).
 */
export function KillSwitch({ armed, executing, onExecute, holdMs = 1200, compact }: KillSwitchProps) {
  const [holding, setHolding] = useState(false);
  const [progress, setProgress] = useState(0);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [typed, setTyped] = useState('');
  const raf = useRef<number>(0);
  const start = useRef(0);

  useEffect(() => {
    if (!holding) return;
    start.current = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - start.current) / holdMs);
      setProgress(p);
      if (p >= 1) {
        setHolding(false);
        setConfirmOpen(true);
        return;
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [holding, holdMs]);

  const canConfirm = typed.trim().toUpperCase() === 'CONFIRM';

  return (
    <>
      <button
        aria-label="kill switch — hold to arm"
        onPointerDown={() => !armed && setHolding(true)}
        onPointerUp={() => setHolding(false)}
        onPointerLeave={() => setHolding(false)}
        disabled={armed}
        style={{
          position: 'relative',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          height: 36,
          padding: '0 16px',
          fontFamily: "'IBM Plex Mono',monospace",
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: armed ? '#FFFFFF' : '#FF6B6B',
          background: armed ? '#FF6B6B' : 'transparent',
          border: `1px solid ${armed ? '#FF6B6B' : '#FF6B6B'}`,
          borderRadius: 4,
          cursor: holding ? 'grabbing' : armed ? 'default' : 'pointer',
          userSelect: 'none',
          overflow: 'hidden',
          touchAction: 'none',
        }}
      >
        {/* hold progress ring */}
        {holding && (
          <svg width="36" height="36" style={{ position: 'absolute', left: 0, top: -1 }} aria-hidden="true">
            <circle cx="18" cy="18" r="16" fill="none" stroke="#FF6B6B44" strokeWidth="2" />
            <circle
              cx="18"
              cy="18"
              r="16"
              fill="none"
              stroke="#FF6B6B"
              strokeWidth="2"
              strokeLinecap="round"
              strokeDasharray={2 * Math.PI * 16}
              strokeDashoffset={2 * Math.PI * 16 * (1 - progress)}
              transform="rotate(-90 18 18)"
            />
          </svg>
        )}
        <svg width={compact ? 14 : 16} height={compact ? 14 : 16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 3 L21 20 H3 Z" />
          <line x1="12" y1="9" x2="12" y2="14" />
          <circle cx="12" cy="17.5" r="0.5" fill="currentColor" />
        </svg>
        <span>{armed ? 'ARMED' : 'KILL SWITCH'}</span>
      </button>

      {confirmOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="kill switch confirmation"
          style={{
            position: 'fixed',
            inset: 0,
            background: '#0B0E14b8',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 16,
          }}
          onPointerDown={(e) => e.target === e.currentTarget && setConfirmOpen(false)}
        >
          <div style={{ width: 480, maxWidth: '100%', background: '#12161F', border: '1px solid #FF6B6B', borderRadius: 4, padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FF6B6B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 3 L21 20 H3 Z" />
                <line x1="12" y1="9" x2="12" y2="14" />
                <circle cx="12" cy="17.5" r="0.5" fill="#FF6B6B" />
              </svg>
              <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 14, fontWeight: 700, letterSpacing: '0.06em', color: '#FFFFFF', textTransform: 'uppercase' }}>
                Kill Switch Armed
              </span>
            </div>
            <p style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, color: '#9AA3B2', margin: '0 0 16px', lineHeight: 1.6 }}>
              TYPE <strong style={{ color: '#FF6B6B' }}>"CONFIRM"</strong> TO LIQUIDATE ALL POSITIONS AND STOP TRADING
            </p>
            <input
              autoFocus
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && canConfirm && execute()}
              placeholder="TYPE CONFIRM"
              aria-label="type CONFIRM to execute kill"
              style={{
                width: '100%',
                height: 36,
                padding: '0 12px',
                background: '#0B0E14',
                border: `1px solid ${canConfirm ? '#FF6B6B' : '#1E2638'}`,
                borderRadius: 4,
                color: '#FFFFFF',
                fontFamily: "'IBM Plex Mono',monospace",
                fontSize: 13,
                letterSpacing: '0.1em',
                outline: 'none',
                marginBottom: 16,
              }}
            />
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button onClick={() => setConfirmOpen(false)} style={btnGhost}>
                CANCEL
              </button>
              <button
                disabled={!canConfirm || executing}
                onClick={() => execute()}
                style={{ ...btnDanger, opacity: canConfirm && !executing ? 1 : 0.4, cursor: canConfirm && !executing ? 'pointer' : 'not-allowed' }}
              >
                {executing ? 'EXECUTING…' : 'EXECUTE'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );

  async function execute() {
    if (!canConfirm || executing) return;
    setConfirmOpen(false);
    await onExecute();
  }
}

const btnGhost: React.CSSProperties = {
  height: 36,
  padding: '0 16px',
  background: 'transparent',
  border: '1px solid #1E2638',
  borderRadius: 4,
  color: '#9AA3B2',
  fontFamily: "'IBM Plex Mono',monospace",
  fontSize: 12,
  letterSpacing: '0.06em',
  cursor: 'pointer',
};

const btnDanger: React.CSSProperties = {
  ...btnGhost,
  background: '#FF6B6B',
  border: '1px solid #FF6B6B',
  color: '#FFFFFF',
  fontWeight: 600,
};

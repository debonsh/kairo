'use client';

import { useEffect, useRef, useState } from 'react';
import { KillSwitch } from '@kairo/ui';
import { countdown, duration, istTime } from '@kairo/lib';
import { postControl, postMode } from '@kairo/lib';
import { useKairo } from '../kairo-data';
import { LogoMark } from './Logo';

const CYCLE_SECONDS = 120; // config/settings.yaml trading.cycle_seconds

interface TopBarProps {
  onRefresh: () => void;
  onOpenPalette: () => void;
  onLog: (level: 'INFO' | 'WARN' | 'ERROR' | 'OK' | 'LLM', text: string) => void;
}

/** Z0 global status bar — dashboard-2 sheet: KAIRO ●LIVE · CYCLE · UPTIME · MODE · BALANCED · IST clock · KILL SWITCH. */
export function TopBar({ onRefresh, onOpenPalette, onLog }: TopBarProps) {
  const d = useKairo((s) => s.dashboard);
  const set = useKairo((s) => s.set);
  const [cycle, setCycle] = useState(CYCLE_SECONDS);
  const [clock, setClock] = useState(istTime());
  const [modeOpen, setModeOpen] = useState(false);
  const modeRef = useRef<HTMLDivElement>(null);

  const summary = d?.summary;
  const control = summary?.control;
  const apiUp = Boolean(d);
  const running = apiUp ? (control?.state === 'RUNNING' || !control) : false;
  const stopped = control?.is_stopped ?? false;
  const mode = d?.futures?.mode ?? 'vanilla';
  const armed = stopped || !running;

  useEffect(() => {
    const tick = () => {
      const last = d?.t ? new Date(d.t).getTime() : Date.now();
      const elapsed = ((Date.now() - last) / 1000) % CYCLE_SECONDS;
      setCycle(Math.max(0, CYCLE_SECONDS - elapsed));
      setClock(istTime());
    };
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, [d?.t]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (modeRef.current && !modeRef.current.contains(e.target as Node)) setModeOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const setMode = async (m: 'vanilla' | 'aggressive') => {
    try {
      const r = await postMode(m);
      set({ futuresMode: r.mode });
      setModeOpen(false);
      onLog('OK', `MODE SWITCHED TO ${r.mode.toUpperCase()}`);
    } catch {
      onLog('ERROR', 'MODE SWITCH FAILED — API OFFLINE');
    }
  };

  const pauseResume = async () => {
    try {
      const cmd = control?.is_paused ? 'resume' : 'pause';
      await postControl(cmd);
      onLog('OK', cmd === 'pause' ? 'TRADING PAUSED' : 'TRADING RESUMED');
      onRefresh();
    } catch {
      onLog('ERROR', `${(control?.is_paused ? 'RESUME' : 'PAUSE').toUpperCase()} FAILED — API OFFLINE`);
    }
  };

  const statusColor = !apiUp ? 'var(--kairo-mute)' : running ? 'var(--kairo-lime)' : stopped ? 'var(--kairo-coral)' : 'var(--kairo-amber)';
  const statusLabel = !apiUp ? 'OFFLINE' : running ? 'LIVE' : stopped ? 'HALTED' : 'PAUSED';

  return (
    <header
      style={{
        height: 40,
        display: 'flex',
        alignItems: 'center',
        padding: '0 14px',
        background: 'var(--surface-panel)',
        borderBottom: '1px solid var(--border-default)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        fontFamily: "'IBM Plex Mono',monospace",
        fontSize: 11,
        flexShrink: 0,
      }}
    >
      {/* brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <LogoMark size={22} />
        <span style={{ fontFamily: 'var(--font-dot), "IBM Plex Mono", monospace', fontSize: 15, letterSpacing: '0.08em', color: 'var(--text-primary)', lineHeight: 1 }}>
          KAIRO
        </span>
      </div>

      <Sep />

      {/* ● LIVE — opens command palette (Ctrl+K) */}
      <button
        onClick={onOpenPalette}
        title="Command palette (Ctrl+K)"
        style={{ display: 'flex', alignItems: 'center', gap: 7, background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontFamily: 'inherit', fontSize: 11 }}
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: statusColor,
            animation: running ? 'kairoPulse 1.2s ease-in-out 3' : undefined,
          }}
        />
        <span style={{ color: statusColor, letterSpacing: '0.08em', fontWeight: 600 }}>{statusLabel}</span>
      </button>

      <Sep />

      <Stat label="CYCLE">
        <span style={{ color: 'var(--signal-primary)', fontVariantNumeric: 'tabular-nums' }}>{countdown(cycle)}</span>
      </Stat>

      <Sep />

      <Stat label="UPTIME">
        <span style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{duration(summary?.uptime_hours ?? 0)}</span>
      </Stat>

      <Sep />

      {/* mode (dropdown) */}
      <div style={{ display: 'flex', alignItems: 'center', position: 'relative' }} ref={modeRef}>
        <button
          onClick={() => setModeOpen((v) => !v)}
          aria-haspopup="menu"
          aria-expanded={modeOpen}
          style={{
            background: 'transparent',
            border: `1px solid ${mode === 'aggressive' ? 'var(--kairo-amber)' : 'var(--kairo-cyan)'}44`,
            borderRadius: 2,
            cursor: 'pointer',
            fontFamily: 'inherit',
            fontSize: 10,
            letterSpacing: '0.08em',
            padding: '2px 8px',
            color: mode === 'aggressive' ? 'var(--kairo-amber)' : 'var(--kairo-cyan)',
          }}
        >
          {mode.toUpperCase()}{summary?.paper_mode ? ' · PAPER' : ''}
        </button>
        {modeOpen && (
          <div
            role="menu"
            style={{
              position: 'absolute',
              top: 30,
              left: 0,
              background: 'var(--surface-panel)',
              border: '1px solid var(--border-default)',
              borderRadius: 4,
              boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
              zIndex: 300,
              padding: 6,
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              minWidth: 180,
            }}
          >
            <MenuItem label="MODE: VANILLA" active={mode === 'vanilla'} onClick={() => void setMode('vanilla')} />
            <MenuItem label="MODE: AGGRESSIVE" active={mode === 'aggressive'} onClick={() => void setMode('aggressive')} />
            <div style={{ height: 1, background: 'var(--border-default)', margin: '4px 0' }} />
            <MenuItem label={control?.is_paused ? 'RESUME TRADING' : 'PAUSE TRADING'} onClick={() => void pauseResume()} />
            <MenuItem label="MANUAL REFRESH" onClick={onRefresh} />
          </div>
        )}
      </div>

      <Sep />

      {/* risk profile */}
      <span style={{ color: 'var(--ai-primary)', letterSpacing: '0.08em', fontWeight: 600 }}>BALANCED</span>

      <div style={{ flex: 1 }} />

      {/* IST clock */}
      <span style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums', letterSpacing: '0.04em' }}>{clock} IST</span>

      <Sep />

      <KillSwitch
        armed={armed}
        onExecute={async () => {
          try {
            await postControl('stop');
            onLog('ERROR', 'KILL SWITCH EXECUTED — ALL POSITIONS LIQUIDATED');
            onRefresh();
          } catch {
            onLog('ERROR', 'KILL FAILED — API OFFLINE');
          }
        }}
      />
    </header>
  );
}

function Sep() {
  return <span style={{ width: 1, height: 16, background: 'var(--border-default)', margin: '0 14px', flexShrink: 0 }} aria-hidden="true" />;
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ color: 'var(--text-tertiary)', letterSpacing: '0.06em', fontSize: 10 }}>{label}</span>
      {children}
    </div>
  );
}

function MenuItem({ label, active, onClick }: { label: string; active?: boolean; onClick: () => void }) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      style={{
        textAlign: 'left',
        padding: '7px 12px',
        background: active ? 'rgba(0, 229, 255, 0.09)' : 'transparent',
        border: 'none',
        borderRadius: 2,
        color: active ? 'var(--signal-primary)' : 'var(--text-secondary)',
        fontFamily: "'IBM Plex Mono',monospace",
        fontSize: 11,
        letterSpacing: '0.06em',
        cursor: 'pointer',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = active ? 'rgba(0, 229, 255, 0.09)' : 'rgba(30, 35, 43, 0.13)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = active ? 'rgba(0, 229, 255, 0.09)' : 'transparent')}
    >
      {label}
    </button>
  );
}

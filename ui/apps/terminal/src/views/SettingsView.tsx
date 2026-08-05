'use client';

import { useState } from 'react';
import { Badge, Button, KillSwitch, MetricCard, Panel, Toggle } from '@kairo/ui';
import { postControl, postMode } from '@kairo/lib';
import { useKairo } from '../kairo-data';
import { C, TEXT, BORDER, SIGNAL, AI } from '../colors';

/** SETTINGS — runtime mode, trading control, kill switch, confidence sweep + joint sizer. */
export function SettingsView() {
  const d = useKairo((s) => s.dashboard);
  const summary = d?.summary;
  const control = summary?.control;
  const sweep = d?.confidence_sweep;
  const sizer = d?.joint_sizer;
  const mode = d?.futures?.mode ?? 'vanilla';
  const [busy, setBusy] = useState<string | null>(null);
  const [state, setState] = useState<string | null>(null);
  const paused = control?.is_paused ?? false;

  const run = async (key: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(key);
    setState(null);
    try {
      await fn();
      setState(ok);
    } catch {
      setState('FAILED — API OFFLINE');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard label="RUNTIME MODE" value={mode.toUpperCase()} badge={<Badge color={mode === 'aggressive' ? C.amber : SIGNAL.primary}>{summary?.paper_mode ? 'PAPER' : 'LIVE'}</Badge>} />
        <MetricCard label="CONTROL STATE" value={String(control?.state ?? 'RUNNING')} deltaColor={control?.is_stopped ? C.coral : control?.is_paused ? C.amber : C.lime} />
        <MetricCard label="CONFIDENCE THRESHOLD" value={sweep ? `${(sweep.current ?? 0.55).toFixed(2)}` : '0.55'} sub="confidence_sweep.tsv" />
        <MetricCard label="SUPPORTED THRESHOLD" value={sweep?.supported_threshold ? sweep.supported_threshold.toFixed(2) : '—'} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Panel title="TRADING CONTROL" asOf={d?.t} badge={<Badge color={paused ? C.amber : C.lime}>{paused ? 'PAUSED' : 'RUNNING'}</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Row k="AUTONOMOUS TRADING">
              <Toggle
                checked={!paused && !control?.is_stopped}
                disabled={control?.is_stopped || busy === 'pause'}
                onChange={(v) => void run('pause', () => postControl(v ? 'resume' : 'pause'), v ? 'TRADING RESUMED' : 'TRADING PAUSED')}
                label={paused ? 'PAUSED' : 'ACTIVE'}
              />
            </Row>
            <Row k="MODE: VANILLA (2% RISK, 1x LEVERAGE)">
              <Button variant={mode === 'vanilla' ? 'primary' : 'secondary'} size="sm" disabled={mode === 'vanilla' || busy === 'mode'} onClick={() => void run('mode', () => postMode('vanilla'), 'MODE → VANILLA')}>
                SELECT
              </Button>
            </Row>
            <Row k="MODE: AGGRESSIVE (AUTO-LEVERAGE SCALING)">
              <Button variant={mode === 'aggressive' ? 'primary' : 'secondary'} size="sm" disabled={mode === 'aggressive' || busy === 'mode'} onClick={() => void run('mode', () => postMode('aggressive'), 'MODE → AGGRESSIVE')}>
                SELECT
              </Button>
            </Row>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, borderTop: `1px solid ${BORDER.default}`, paddingTop: 12 }}>
              <KillSwitch
                armed={control?.is_stopped ?? false}
                onExecute={() => run('kill', () => postControl('stop'), 'KILL SWITCH EXECUTED — TRADING STOPPED')}
              />
              {busy === 'kill' && <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color: C.coral }}>EXECUTING…</span>}
            </div>
            {state && (
              <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color: state.includes('FAILED') ? C.coral : C.lime, borderTop: `1px solid ${BORDER.default}`, paddingTop: 8 }}>
                {state}
              </div>
            )}
          </div>
        </Panel>

        <Panel title="CONFIDENCE SWEEP + JOINT SIZER" asOf={d?.t} badge={<Badge color={AI.primary}>SCIENTIFIC SIZING</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color: TEXT.secondary, lineHeight: 1.7 }}>
              The nightly sweep backtests confidence thresholds to find the one with the best risk-adjusted return.
            </div>
            {sweep?.recommendation && (
              <div style={{ borderLeft: `2px solid ${AI.primary}`, paddingLeft: 10, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color: TEXT.primary }}>
                {sweep.recommendation}
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              <MiniStat k="SUPPORTED" v={sweep?.supported_threshold ? sweep.supported_threshold.toFixed(2) : '—'} />
              <MiniStat k="CURRENT" v={sweep?.current ? sweep.current.toFixed(2) : '0.55'} />
              <MiniStat k="SAMPLES" v={sweep?.n ? String(sweep.n) : '—'} />
            </div>
            {sizer && (
              <div style={{ borderTop: `1px solid ${BORDER.default}`, paddingTop: 10 }}>
                <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, letterSpacing: '0.06em', color: TEXT.tertiary, marginBottom: 6 }}>JOINT SIZER OUTPUT</div>
                <pre style={{ margin: 0, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: TEXT.secondary, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                  {JSON.stringify(sizer, null, 2).slice(0, 900)}
                </pre>
              </div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
      <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, letterSpacing: '0.06em', color: TEXT.secondary }}>{k}</span>
      {children}
    </div>
  );
}

function MiniStat({ k, v }: { k: string; v: string }) {
  return (
    <div style={{ border: `1px solid ${BORDER.default}`, borderRadius: 4, padding: '8px 10px', background: TEXT.inverse }}>
      <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 8, letterSpacing: '0.06em', color: TEXT.tertiary }}>{k}</div>
      <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 15, fontWeight: 600, color: TEXT.primary, marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>{v}</div>
    </div>
  );
}

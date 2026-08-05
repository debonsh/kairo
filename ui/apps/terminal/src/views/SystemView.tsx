'use client';

import { Badge, MetricCard, Panel, StatusDot } from '@kairo/ui';
import { duration, inr } from '@kairo/lib';
import { useKairo } from '../kairo-data';
import { C, TEXT, BORDER, SIGNAL, AI } from '../colors';

type ServiceState = 'live' | 'up' | 'info' | 'warn';

interface Service {
  name: string;
  state: ServiceState;
  label: string;
}

/** SYSTEM — service health, runtime stats, architecture non-negotiables. */
export function SystemView() {
  const d = useKairo((s) => s.dashboard);
  const s = useKairo((state) => state);
  const summary = d?.summary;
  const apiUp = Boolean(d);
  const llm = summary?.llm ?? 'QWEN 8B';

  const services: Service[] = [
    { name: 'EXCHANGE (BYBIT)', state: apiUp ? 'live' : 'warn', label: apiUp ? 'ONLINE' : 'UNREACHABLE' },
    { name: `LLM ENGINE (${llm.toUpperCase()})`, state: apiUp ? 'live' : 'warn', label: apiUp ? 'ONLINE' : 'UNREACHABLE' },
    { name: 'DATA FEED', state: apiUp ? 'live' : 'warn', label: apiUp ? 'ONLINE' : 'UNREACHABLE' },
    { name: 'TELEGRAM', state: 'info', label: 'CONNECTED' },
    { name: 'WATCHDOG', state: 'live', label: 'ACTIVE' },
    { name: 'DATABASE (DUCKDB)', state: 'live', label: 'HEALTHY' },
    { name: 'RISK ENGINE', state: 'live', label: 'ONLINE' },
    { name: 'WS PUSH CHANNEL', state: apiUp ? 'live' : 'warn', label: apiUp ? 'CONNECTED' : 'POLL ONLY' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard label="VERSION" value="v1.0.0" sub="PRODUCTION BUILD" />
        <MetricCard label="UPTIME" value={duration(summary?.uptime_hours ?? 0)} />
        <MetricCard label="CYCLES" value={String(summary?.cycles ?? 0)} sub="2-MINUTE CYCLE" />
        <MetricCard label="API LATENCY" value={s.latencyMs ? `${s.latencyMs}ms` : '—'} sub="LAST POLL" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Panel title="SYSTEM HEALTH" asOf={d?.t} badge={<Badge color={apiUp ? C.lime : C.coral}>{apiUp ? 'ALL SYSTEMS NOMINAL' : 'BACKEND DOWN'}</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {services.map((sv) => (
              <div key={sv.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid ${BORDER.default}`, padding: '6px 0' }}>
                <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, letterSpacing: '0.06em', color: TEXT.secondary }}>{sv.name}</span>
                <StatusDot state={sv.state} label={sv.label} />
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="RUNTIME STATE" asOf={d?.t} badge={<Badge color={SIGNAL.primary}>SERVER-OWNED</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Stat k="BALANCE" v={inr(summary?.balance ?? 0)} />
            <Stat k="EQUITY" v={inr(summary?.equity ?? 0)} />
            <Stat k="OPEN POSITIONS" v={String(summary?.open_positions ?? 0)} />
            <Stat k="TOTAL TRADES" v={String(summary?.total_trades ?? 0)} />
            <Stat k="WIN RATE" v={`${summary?.win_rate ?? 0}%`} />
            <Stat k="PAPER MODE" v={summary?.paper_mode ? 'YES' : 'NO'} tone={C.amber} />
            <Stat k="TOTAL PNL" v={inr(summary?.total_pnl ?? 0)} tone={(summary?.total_pnl ?? 0) >= 0 ? C.lime : C.coral} />
          </div>
        </Panel>
      </div>

      <Panel title="ARCHITECTURE NON-NEGOTIABLES" asOf={d?.t}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
          <Principle n="01" title="LLM = FILTER, NOT EXECUTOR" desc="Trades originate in the deterministic SignalEngine. The strategist LLM can VETO but can never force a trade." color="#7C4DFF" />
          <Principle n="02" title="GATE IS CODE, NOT PROMPT" desc="Every order passes hard Pydantic checks in gate.py that no agent — including the LLM — can override." color="#00FF9D" />
          <Principle n="03" title="DETERMINISTIC FALLBACK" desc="Every agent degrades gracefully: no LLM, no external service → the bot keeps trading on signals alone." color="#00D4FF" />
        </div>
      </Panel>
    </div>
  );
}

function Stat({ k, v, tone }: { k: string; v: string; tone?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${BORDER.default}`, paddingBottom: 6, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace" }}>
      <span style={{ fontSize: 10, letterSpacing: '0.06em', color: TEXT.tertiary }}>{k}</span>
      <span style={{ fontSize: 12, fontWeight: 600, color: tone ?? TEXT.primary, fontVariantNumeric: 'tabular-nums' }}>{v}</span>
    </div>
  );
}

function Principle({ n, title, desc, color }: { n: string; title: string; desc: string; color: string }) {
  return (
    <div style={{ border: `1px solid ${BORDER.default}`, borderRadius: 4, padding: 12, background: TEXT.inverse }}>
      <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color, fontWeight: 600, marginBottom: 6 }}>{n}</div>
      <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 11, color: TEXT.primary, fontWeight: 600, marginBottom: 4 }}>{title}</div>
      <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: TEXT.tertiary, lineHeight: 1.6 }}>{desc}</div>
    </div>
  );
}

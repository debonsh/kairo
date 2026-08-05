'use client';

import { useMemo } from 'react';
import { ConfidenceScatter } from '@kairo/charts';
import { Badge, DataTable, MetricCard, Panel, PnlCell, SideBadge } from '@kairo/ui';
import { inr, pct } from '@kairo/lib';
import { useKairo } from '../kairo-data';
import { C, TEXT, SIGNAL, AI } from '../colors';

/** LLM VETO LOG — the agent filters, never forces. Confidence scatter + veto stats + executed feed. */
export function VetoView() {
  const d = useKairo((s) => s.dashboard);
  const summary = d?.summary;
  const conf = useMemo(() => (d?.signal_confidence ?? []).slice(-80), [d]);
  const outcomes = useMemo(() => (d?.signal_outcome ?? []).slice(-80), [d]);
  const feed = d?.live_feed ?? d?.recent_trades ?? [];

  const points = useMemo(() => {
    const n = Math.min(conf.length, outcomes.length);
    return Array.from({ length: n }, (_, i) => ({
      x: i,
      confidence: conf[i] ?? 0.5,
      win: (outcomes[i] ?? 0) === 1,
    }));
  }, [conf, outcomes]);

  const total = points.length;
  const wins = points.filter((p) => p.win).length;
  const losses = total - wins;
  const winRate = total ? (wins / total) * 100 : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard label="SIGNALS ANALYZED" value={String(summary?.total_trades ?? total)} sub="EXECUTED + CLOSED" />
        <MetricCard label="WINNING SIGNALS" value={String(wins)} delta={pct(winRate)} deltaColor={C.lime} />
        <MetricCard label="LOSING SIGNALS" value={String(losses)} delta={pct(100 - winRate)} deltaColor={C.coral} />
        <MetricCard label="AVG CONFIDENCE" value={total ? `${(conf.reduce((a, c) => a + c, 0) / total).toFixed(2)}` : '—'} sub="THRESHOLD 0.55" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 12 }}>
        <Panel
          title="SIGNAL OUTCOMES"
          asOf={d?.t}
          badge={
            <Badge color={AI.primary}>
              LLM VETO — NOT CONTROL
            </Badge>
          }
        >
          <ConfidenceScatter points={points} width={560} height={180} threshold={0.55} />
          <div style={{ marginTop: 8, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: TEXT.tertiary, lineHeight: 1.6 }}>
            Each dot = one closed signal, positioned by entry confidence; <span style={{ color: C.lime }}>▲ lime</span> = winner, <span style={{ color: C.coral }}>▼ coral</span> = loser.
            Veto decisions are logged server-side per cycle (agent_decisions); the strategist LLM can{' '}
            <strong style={{ color: TEXT.primary }}>veto</strong> but can never force a trade — the Gate is code-enforced.
          </div>
        </Panel>

        <Panel title="EXECUTION POLICY" asOf={d?.t} badge={<Badge color={SIGNAL.primary}>SIGNAL → FILTER → GATE</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <Stage n="01" label="SIGNAL ENGINE" desc="5 backtest-validated strategies + ensemble vote. Deterministic — no LLM." color={SIGNAL.primary} />
            <Stage n="02" label="STRATEGIST LLM" desc="VETO only. Reviews analysis + memory + social context, may reject signals." color={AI.primary} />
            <Stage n="03" label="RISK MANAGER" desc="Vol-targeted + Kelly sizing. Advisory — never executes." color={C.blue} />
            <Stage n="04" label="GATE" desc="Hard Pydantic checks in code. No agent, including the LLM, can override." color={C.lime} />
          </div>
        </Panel>
      </div>

      <Panel title="EXECUTED FEED" asOf={d?.t} badge={<Badge color={TEXT.secondary}>{feed.length} RECENT</Badge>}>
        <DataTable
          rowKey={(t, i) => `${t.symbol}-${t.time ?? ''}-${t.pnl}-${i}`}
          empty="NO EXECUTED TRADES"
          columns={[
            { key: 'time', label: 'TIME', render: (t) => <span style={{ color: TEXT.tertiary }}>{t.time ? new Date(t.time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'Asia/Kolkata' }) : '—'}</span> },
            { key: 'sym', label: 'PAIR', render: (t) => <span style={{ color: TEXT.primary }}>{t.symbol}</span> },
            { key: 'side', label: 'SIDE', render: (t) => <SideBadge side={t.side} /> },
            { key: 'pnl', label: 'P/L', align: 'right', render: (t) => <PnlCell value={t.pnl} /> },
            { key: 'pct', label: 'P/L%', align: 'right', render: (t) => <span style={{ color: t.pnl_pct >= 0 ? C.lime : C.coral, fontWeight: 600 }}>{pct(t.pnl_pct)}</span> },
            { key: 'strat', label: 'STRATEGY', render: (t) => <span style={{ color: TEXT.secondary }}>{t.strategy ?? t.reason ?? '—'}</span> },
          ]}
          rows={feed}
        />
      </Panel>
    </div>
  );
}

function Stage({ n, label, desc, color }: { n: string; label: string; desc: string; color: string }) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 11, color, fontWeight: 600, border: `1px solid ${color}44`, background: `${color}11`, borderRadius: 3, padding: '2px 6px' }}>
        {n}
      </span>
      <div>
        <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 11, color: TEXT.primary, fontWeight: 600 }}>{label}</div>
        <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: TEXT.tertiary, marginTop: 2, lineHeight: 1.5 }}>{desc}</div>
      </div>
    </div>
  );
}

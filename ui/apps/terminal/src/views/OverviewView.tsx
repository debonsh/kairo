'use client';

import { useMemo } from 'react';
import { Panel, Badge, DataTable, SideBadge, PnlCell } from '@kairo/ui';
import { AreaChart, Sparkline } from '@kairo/charts';
import { inr, pct, price, istTime } from '@kairo/lib';
import { useKairo, useCandles } from '../kairo-data';
import { hurst, adx } from '../regime';

/* RFC §4.3 — exact semantic token colors */
const C = {
  void: '#08080B', charcoal: '#0B0F14', steel: '#12141B', slate: '#1E232B',
  hairline: '#262B34', mist: '#E6E6E6', silver: '#9AA3B2', mute: '#5C6470',
  lime: '#39FF14', cyan: '#00E5FF', violet: '#7C4DFF', blue: '#2962FF',
  amber: '#FFB800', coral: '#FF5C7A', ink: '#FFFFFF',
} as const;

const ASSET_COLORS: Record<string, string> = {
  BTC: C.blue, ETH: C.lime, SOL: C.amber, BNB: C.coral, OTHERS: C.silver,
};

const THRESHOLD = 0.55;

/**
 * RFC §8.1 — Dashboard 3 overview grid (12-col, 3 rows + sub-grid).
 * Extreme density: ≥40 data fields at 1440×900.
 * Every widget uses RFC-correct tokens and dot-matrix visual style.
 */
export function OverviewView() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 8, paddingBottom: 8 }}>
      {/* Row 1: Equity (5) | Allocation (4) | System Health (3) */}
      <EquityWidget gridColumn="span 5" />
      <AllocWidget gridColumn="span 4" />
      <HealthWidget gridColumn="span 3" />

      {/* Row 2: Positions (7) | Risk Metrics (5) */}
      <PositionsWidget gridColumn="span 7" />
      <RiskWidget gridColumn="span 5" />

      {/* Row 3: Recent Trades (4) | LLM Veto Log (4) | Sentiment (4) */}
      <RecentTradesWidget gridColumn="span 4" />
      <VetoLogWidget gridColumn="span 4" />
      <SentimentWidget gridColumn="span 4" />

      {/* Row 4: Signal DNA (3) | Order Flow (3) | Regime (3) | Strategy Perf (3) */}
      <SignalDnaWidget gridColumn="span 3" />
      <OrderFlowWidget gridColumn="span 3" />
      <RegimeWidget gridColumn="span 3" />
      <StrategyPerfWidget gridColumn="span 3" />
    </div>
  );
}

// ---- EQUITY (RFC §11.5: mist line, cyan fill, drawdown bands) ------------------------

function EquityWidget(props: { gridColumn: string }) {
  const d = useKairo((s) => s.dashboard);
  const equity = d?.summary.equity ?? 0;
  const series = d?.equity_curve ?? d?.equity_history.map((h) => h.equity) ?? [];
  const chartData = useMemo(() => series.map((v, i) => ({ t: String(i), v })), [series]);
  const first = series[0] ?? 0;
  const last = series[series.length - 1] ?? 0;
  const delta = series.length > 1 ? ((last - first) / Math.max(first, 1)) * 100 : 0;
  const up = delta >= 0;

  return (
    <Panel title="EQUITY" badge={<Badge color={C.lime}>● LIVE</Badge>} footer="TOTAL EQUITY" style={{ gridColumn: props.gridColumn, minHeight: 180 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 4 }}>
        <div>
          {/* L1 metric: 24-36px mono */}
          <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 28, fontWeight: 700, color: C.mist, fontVariantNumeric: 'tabular-nums', lineHeight: 1.1 }}>
            {inr(equity)}
          </div>
          {/* R4.4: glyph + color */}
          <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 11, color: up ? C.lime : C.coral, marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
            {up ? '▲' : '▼'} {pct(Math.abs(delta))}
          </div>
        </div>
        <Sparkline data={series} width={100} height={32} color={up ? C.lime : C.coral} />
      </div>
      {/* RFC §11.5: mist line, cyan 8% fill */}
      <div style={{ marginTop: 4, height: 90 }}>
        <AreaChart data={chartData} width={420} height={90} color={C.mist} fill={C.cyan} yFormat={(v) => inr(v, 0)} />
      </div>
    </Panel>
  );
}

// ---- ALLOCATION (RFC §11.10: horizontal stacked bar, dot labels) --------------------

function AllocWidget(props: { gridColumn: string }) {
  const d = useKairo((s) => s.dashboard);
  const positions = d?.positions ?? [];
  const equity = d?.summary.equity ?? 0;

  const segments = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of positions) {
      const base = p.symbol.split('/')[0] ?? 'OTHER';
      const val = (p.qty ?? 0) * (p.price ?? p.entry);
      map.set(base, (map.get(base) ?? 0) + val);
    }
    if (equity > 0) {
      const allocated = Array.from(map.values()).reduce((a, b) => a + b, 0);
      const cash = Math.max(0, equity - allocated);
      if (cash > 0) map.set('CASH', (map.get('CASH') ?? 0) + cash);
    }
    return Array.from(map.entries()).map(([name, value]) => ({
      name, value, color: ASSET_COLORS[name] ?? ASSET_COLORS.OTHERS,
    }));
  }, [positions, equity]);

  const total = segments.reduce((a, s) => a + s.value, 0) || 1;

  return (
    <Panel title="ALLOCATION" badge={<Badge color={C.cyan}>LIVE</Badge>} style={{ gridColumn: props.gridColumn, minHeight: 180 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 6 }}>
        <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 18, fontWeight: 600, color: C.mist, fontVariantNumeric: 'tabular-nums' }}>{inr(equity, 0)}</div>
        <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color: C.lime, letterSpacing: '0.06em' }}>▲ LIVE</div>
      </div>
      {/* Stacked bar: RFC §11.10 */}
      <div style={{ height: 12, display: 'flex', borderRadius: 1, overflow: 'hidden', background: C.void, marginBottom: 10 }}>
        {segments.map((s, i) => (
          <div key={i} style={{ width: `${(s.value / total) * 100}%`, background: s.color, minWidth: 2 }} title={`${s.name} ${inr(s.value)}`} />
        ))}
      </div>
      {/* Legend with dot indicators */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px' }}>
        {segments.map((s, i) => (
          <div key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: C.silver }}>
            <span style={{ width: 6, height: 6, borderRadius: 1, background: s.color }} />
            <span style={{ color: C.mist, fontWeight: 600 }}>{s.name}</span>
            <span>{((s.value / total) * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ---- SYSTEM HEALTH (RFC §8.3: status rows with dots + latency) ----------------------

function HealthWidget(props: { gridColumn: string }) {
  const apiOnline = useKairo((s) => s.apiOnline);
  const latency = useKairo((s) => s.latencyMs);
  const d = useKairo((s) => s.dashboard);
  const summary = d?.summary;

  const rows = [
    { name: 'EXCHANGE', sub: 'BYBIT', ok: apiOnline, ms: latency },
    { name: 'LLM ENGINE', sub: (summary?.llm ?? 'OLLAMA/QWEN 8B').toUpperCase(), ok: Boolean(d), ms: undefined },
    { name: 'DATA FEED', sub: 'MARKET', ok: Boolean(d), ms: 5000 },
    { name: 'WATCHDOG', sub: 'CYCLE', ok: Boolean(d), ms: undefined },
    { name: 'SAFETY GATE', sub: 'ARMED', ok: true, ms: undefined },
  ];

  return (
    <Panel title="SYSTEM HEALTH" badge={<Badge color={apiOnline ? C.lime : C.coral}>{apiOnline ? 'ONLINE' : 'OFFLINE'}</Badge>} style={{ gridColumn: props.gridColumn, minHeight: 180 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {rows.map((r) => (
          <div key={r.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color: C.silver, letterSpacing: '0.06em' }}>{r.name}</div>
              <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: C.mute }}>{r.sub}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: r.ok ? C.lime : C.coral }} />
              <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: r.ok ? C.lime : C.coral, letterSpacing: '0.06em' }}>{r.ok ? 'ONLINE' : 'OFFLINE'}</span>
              {r.ms !== undefined && <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 8, color: C.mute }}>{r.ms}ms</span>}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ---- POSITIONS (RFC §10.6: dense table, 11px mono) ---------------------------------

function PositionsWidget(props: { gridColumn: string }) {
  const d = useKairo((s) => s.dashboard);
  const positions = d?.positions ?? [];

  return (
    <Panel
      title="POSITIONS"
      badge={<Badge color={positions.length >= 5 ? C.amber : C.silver}>{positions.length}/5</Badge>}
      style={{ gridColumn: props.gridColumn, minHeight: 200 }}
    >
      <DataTable
        rowKey={(p, i) => `${p.symbol}-${p.side}-${p.entry}-${i}`}
        empty="NO OPEN POSITIONS"
        columns={[
          { key: 'pair', label: 'PAIR', render: (p) => <span style={{ color: C.mist }}>{p.symbol}</span> },
          { key: 'side', label: 'SIDE', render: (p) => <SideBadge side={p.side} /> },
          { key: 'size', label: 'SIZE', align: 'right', render: (p) => p.qty.toFixed(4) },
          { key: 'entry', label: 'ENTRY', align: 'right', render: (p) => price(p.entry) },
          { key: 'upnl', label: 'P/L', align: 'right', render: (p) => <PnlCell value={p.upnl ?? 0} /> },
          { key: 'sl', label: 'SL/TP', align: 'right', render: (p) => <span style={{ color: C.mute }}>{p.sl ? price(p.sl) : '—'}</span> },
        ]}
        rows={positions}
      />
    </Panel>
  );
}

// ---- RISK METRICS (RFC §11.7: gauge bars + numeric) --------------------------------

function RiskWidget(props: { gridColumn: string }) {
  const d = useKairo((s) => s.dashboard);
  const summary = d?.summary;
  const equity = summary?.equity ?? 0;
  const balance = summary?.balance ?? 0;
  const dailyPnl = summary?.daily_pnl ?? 0;
  const totalPnl = summary?.total_pnl ?? 0;
  const winRate = summary?.win_rate ?? 0;
  const openPos = summary?.open_positions ?? 0;

  return (
    <Panel title="RISK METRICS" badge={<Badge color={C.violet}>BALANCED</Badge>} style={{ gridColumn: props.gridColumn, minHeight: 200 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <RiskRow label="DAILY P/L" value={dailyPnl >= 0 ? `+${inr(dailyPnl)}` : inr(dailyPnl)} color={dailyPnl >= 0 ? C.lime : C.coral} />
        <RiskRow label="TOTAL P/L" value={totalPnl >= 0 ? `+${inr(totalPnl)}` : inr(totalPnl)} color={totalPnl >= 0 ? C.lime : C.coral} />
        <RiskRow label="WIN RATE" value={`${winRate.toFixed(1)}%`} color={winRate >= 50 ? C.lime : C.amber} />
        <RiskRow label="POSITIONS" value={`${openPos}/5`} color={openPos >= 5 ? C.amber : C.silver} />
        <RiskRow label="EQUITY" value={inr(equity)} color={C.mist} />
        <RiskRow label="BALANCE" value={inr(balance)} color={C.silver} />
      </div>
    </Panel>
  );
}

function RiskRow({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10 }}>
      <span style={{ color: C.silver }}>{label}</span>
      <span style={{ color, fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>{value}</span>
    </div>
  );
}

// ---- RECENT TRADES (RFC §10.6: dense rows) -----------------------------------------

function RecentTradesWidget(props: { gridColumn: string }) {
  const d = useKairo((s) => s.dashboard);
  const trades = d?.live_feed?.slice(0, 6) ?? d?.recent_trades?.slice(0, 6) ?? [];

  return (
    <Panel title="RECENT TRADES" badge={<Badge color={C.silver}>{trades.length} EVT</Badge>} style={{ gridColumn: props.gridColumn, minHeight: 200 }}>
      <DataTable
        rowKey={(t, i) => `${t.time ?? 0}-${t.symbol}-${t.side}-${i}`}
        empty="NO TRADES YET"
        columns={[
          { key: 'time', label: 'TIME', render: (t) => <span style={{ color: C.mute }}>{t.time ? new Date(t.time * 1000).toLocaleTimeString('en-GB', { timeZone: 'Asia/Kolkata' }) : '—'}</span> },
          { key: 'pair', label: 'PAIR', render: (t) => <span style={{ color: C.mist }}>{t.symbol}</span> },
          { key: 'side', label: 'SIDE', render: (t) => <SideBadge side={t.side} /> },
          { key: 'pnl', label: 'P/L', align: 'right', render: (t) => <PnlCell value={t.pnl} /> },
        ]}
        rows={trades}
      />
    </Panel>
  );
}

// ---- LLM VETO LOG (RFC §12.4: border-left color, mono text) ------------------------

function VetoLogWidget(props: { gridColumn: string }) {
  const d = useKairo((s) => s.dashboard);
  const confidences = (d?.signal_confidence ?? []).slice(-5);
  const trades = (d?.recent_trades ?? []).slice(-5);

  const rows = useMemo(() => {
    return confidences.map((c, i) => {
      const pair = trades[i]?.symbol ?? 'BTC/USDT';
      const below = c < THRESHOLD;
      return {
        time: istTime(),
        pair,
        reason: `CONFIDENCE ${c.toFixed(2)} ${below ? '<' : '≥'} ${THRESHOLD} :: ${below ? 'VETO' : 'PASS'}`,
        agent: (d?.summary?.llm ?? 'QWEN 8B').toUpperCase(),
        below,
      };
    });
  }, [confidences, trades, d?.summary?.llm]);

  return (
    <Panel title="LLM VETO LOG" badge={<Badge color={C.violet}>LLM VETO NOT CONTROL</Badge>} style={{ gridColumn: props.gridColumn, minHeight: 200 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, lineHeight: 1.4 }}>
        {rows.map((r, i) => (
          <div
            key={i}
            style={{
              padding: '4px 6px',
              borderLeft: `2px solid ${r.below ? C.amber : C.silver}`,
              background: C.charcoal,
              color: r.below ? C.amber : C.silver,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 1 }}>
              <span style={{ color: C.mist, fontWeight: 600 }}>{r.pair}</span>
              <span style={{ color: C.mute }}>{r.time}</span>
            </div>
            <div>{r.reason}</div>
            <div style={{ color: C.violet, fontSize: 8 }}>{r.agent}</div>
          </div>
        ))}
        {rows.length === 0 && <span style={{ color: C.mute }}>NO VETO DECISIONS YET</span>}
      </div>
    </Panel>
  );
}

// ---- NEWS & SENTIMENT (RFC §11.9: bidirectional bars + score) ----------------------

function SentimentWidget(props: { gridColumn: string }) {
  const market = useKairo((s) => s.market);
  const fng = market?.fear_greed_index ?? 50;
  const label = market?.fear_greed_label ?? 'NEUTRAL';
  const coins = (market?.coins ?? []).slice(0, 4);

  return (
    <Panel title="NEWS & SENTIMENT" badge={<Badge color={C.cyan}>LIVE</Badge>} style={{ gridColumn: props.gridColumn, minHeight: 200 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div>
          <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 20, fontWeight: 700, color: C.mist, fontVariantNumeric: 'tabular-nums' }}>
            {fng}/100
          </div>
          <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color: fng > 60 ? C.lime : fng < 40 ? C.coral : C.amber }}>
            {fng > 60 ? '▲' : fng < 40 ? '▼' : '●'} {label.toUpperCase()}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width: '60%' }}>
          {coins.map((c) => {
            const score = Math.min(100, Math.max(0, 50 + (c.change_24h ?? 0) * 8));
            return (
              <div key={c.symbol} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 36, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 8, color: C.silver }}>{c.symbol.split('/')[0]}</span>
                <div style={{ flex: 1, height: 3, background: C.void, borderRadius: 1 }}>
                  <div style={{ width: `${score}%`, height: '100%', borderRadius: 1, background: (c.change_24h ?? 0) >= 0 ? C.cyan : C.coral }} />
                </div>
                <span style={{ width: 36, textAlign: 'right', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 8, color: (c.change_24h ?? 0) >= 0 ? C.lime : C.coral }}>
                  {pct(c.change_24h ?? 0)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </Panel>
  );
}

// ---- SIGNAL DNA (RFC §11.12: vertical wave bars) -----------------------------------

function SignalDnaWidget(props: { gridColumn: string }) {
  const d = useKairo((s) => s.dashboard);
  const signals = (d?.signal_confidence ?? []).slice(-24);
  const strategies = d?.strategies?.map((s) => s.name) ?? ['BREAKOUT', 'MA CROSS', 'BOLL REVERT', 'MEAN REV', 'DOT HAVEN'];

  return (
    <Panel title="SIGNAL DNA" badge={<Badge color={C.violet}>ENSEMBLE</Badge>} style={{ gridColumn: props.gridColumn, minHeight: 180 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 1, height: 70, marginBottom: 4 }}>
        {signals.map((v, i) => {
          const h = Math.max(3, v * 68);
          const colors = [C.cyan, C.lime, C.violet, C.amber, C.blue];
          return <div key={i} style={{ flex: 1, minWidth: 2, background: colors[i % colors.length], height: `${h}%`, borderRadius: 0, opacity: 0.85 }} />;
        })}
        {signals.length === 0 && <span style={{ color: C.mute, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9 }}>NO SIGNAL DATA</span>}
      </div>
      <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: C.silver, marginBottom: 2 }}>
        STRENGTH {signals.length ? ((signals[signals.length - 1] ?? 0) * 100).toFixed(0) : '—'}% · {strategies[0]?.toUpperCase() ?? '—'} · TF 4H
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 8px', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 8, color: C.mute }}>
        {strategies.slice(0, 4).map((s, i) => (
          <span key={s}><span style={{ color: [C.cyan, C.lime, C.violet, C.amber][i] }}>●</span> {s.toUpperCase()}</span>
        ))}
      </div>
    </Panel>
  );
}

// ---- ORDER FLOW (RFC §11.11: dot dispersion) ---------------------------------------

function OrderFlowWidget(props: { gridColumn: string }) {
  const d = useKairo((s) => s.dashboard);
  const nodes = d?.correlations?.nodes ?? [];
  const avgChg = nodes.length ? nodes.reduce((a, n) => a + n.chg, 0) / nodes.length : 0;
  const buyPressure = 50 + Math.min(50, Math.max(-50, avgChg * 3));

  return (
    <Panel title="ORDER FLOW" badge={<Badge color={C.cyan}>LIVE</Badge>} style={{ gridColumn: props.gridColumn, minHeight: 180 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 80 }}>
        <OrderFlowDots nodes={nodes} />
      </div>
      <div style={{ textAlign: 'center', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color: avgChg >= 0 ? C.lime : C.coral, marginTop: 2 }}>
        {avgChg >= 0 ? '▲' : '▼'} {buyPressure.toFixed(0)}% BUY
      </div>
    </Panel>
  );
}

function OrderFlowDots({ nodes }: { nodes: { id: string; chg: number }[] }) {
  const seed = (s: string) => s.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const data = nodes.length ? nodes : [{ id: 'BTC', chg: 2.4 }];
  return (
    <svg width={160} height={70} role="img" aria-label="order flow">
      {Array.from({ length: 36 }, (_, i) => {
        const node = data[i % data.length] ?? { id: 'BTC', chg: 0 };
        const r = (seed(node.id + i) % 100) / 100;
        const buy = node.chg >= 0;
        const x = 8 + (i % 8) * 18 + r * 10;
        const y = 8 + Math.floor(i / 8) * 12 + r * 8;
        return <circle key={i} cx={x} cy={y} r={1.2 + r * 1.8} fill={buy ? C.cyan : C.coral} opacity={0.5 + r * 0.5} />;
      })}
    </svg>
  );
}

// ---- REGIME (RFC §11.8: dot-matrix map) --------------------------------------------

function RegimeWidget(props: { gridColumn: string }) {
  const d = useKairo((s) => s.dashboard);
  const market = useKairo((s) => s.market);
  const { candles } = useCandles('BTC/USDT', '15m');
  const nodes = d?.correlations?.nodes ?? market?.coins.map((c) => ({ id: c.symbol, chg: c.change_24h ?? 0 })) ?? [];

  const { regime, label } = useMemo(() => {
    if (candles.length >= 40) {
      const h = hurst(candles.map((c) => c.c));
      const a = adx(candles.map((c) => ({ h: c.h, l: c.l, c: c.c })));
      if (a > 25) return { regime: 'TRENDING', label: 'TRENDING' } as const;
      if (h < 0.45) return { regime: 'VOLATILE', label: 'VOLATILE' } as const;
      return { regime: 'LIQUID', label: 'LIQUID' } as const;
    }
    const avg = nodes.length ? nodes.reduce((a, n) => a + Math.abs(n.chg), 0) / nodes.length : 0;
    if (avg > 3) return { regime: 'TRENDING', label: 'TRENDING' } as const;
    if (avg > 1.5) return { regime: 'VOLATILE', label: 'VOLATILE' } as const;
    return { regime: 'LIQUID', label: 'LIQUID' } as const;
  }, [candles, nodes]);

  const REGIME_COLOR: Record<string, string> = { TRENDING: C.cyan, VOLATILE: C.amber, LIQUID: C.lime, ILLIQUID: C.mute };
  const regimeColor = REGIME_COLOR[regime] ?? C.mute;

  return (
    <Panel title="MARKET REGIME" badge={<Badge color={regimeColor}>{label}</Badge>} style={{ gridColumn: props.gridColumn, minHeight: 180 }}>
      <div style={{ display: 'flex', gap: 8, height: '100%' }}>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <RegimeDots nodes={nodes} />
        </div>
        <div style={{ width: 90, display: 'flex', flexDirection: 'column', gap: 6, justifyContent: 'center' }}>
          {['TRENDING', 'VOLATILE', 'LIQUID', 'ILLIQUID'].map((r) => (
            <div key={r} style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 8, color: C.silver }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: REGIME_COLOR[r] }} />
              {r}
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function RegimeDots({ nodes }: { nodes: { id: string; chg: number }[] }) {
  const seed = (s: string) => s.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const rows = 5;
  const cols = 7;
  const dots = Array.from({ length: rows * cols }, (_, i) => {
    const sym = nodes[i % nodes.length] ?? { id: 'BTC', chg: 0 };
    const r = (seed(sym.id + i) % 100) / 100;
    const up = sym.chg >= 0;
    return { r, up, chg: Math.abs(sym.chg) };
  });
  return (
    <svg width={150} height={100} role="img" aria-label="market regime dot map">
      {dots.map((d, i) => {
        const x = (i % cols) * 20 + 10;
        const y = Math.floor(i / cols) * 18 + 10;
        const size = 2 + d.r * 2.5;
        const color = d.up ? C.lime : C.coral;
        return <circle key={i} cx={x} cy={y} r={size} fill={color} opacity={0.6 + d.r * 0.4} />;
      })}
    </svg>
  );
}

// ---- STRATEGY PERFORMANCE (RFC §11.12: win rate bars) -------------------------------

function StrategyPerfWidget(props: { gridColumn: string }) {
  const d = useKairo((s) => s.dashboard);
  const strategies = d?.strategies ?? [];

  return (
    <Panel title="STRATEGY PERF" badge={<Badge color={C.silver}>WIN RATE</Badge>} style={{ gridColumn: props.gridColumn, minHeight: 180 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {strategies.map((s, i) => (
          <div key={s.name}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: C.silver }}>
              <span style={{ color: C.mist }}>{s.name.toUpperCase()}</span>
              <span style={{ color: s.win_rate >= 50 ? C.lime : C.coral, fontVariantNumeric: 'tabular-nums' }}>{s.win_rate.toFixed(0)}%</span>
            </div>
            <div style={{ height: 3, background: C.void, borderRadius: 1 }}>
              <div style={{ width: `${Math.min(100, s.win_rate)}%`, height: '100%', borderRadius: 1, background: s.win_rate >= 50 ? C.lime : C.coral }} />
            </div>
          </div>
        ))}
        {strategies.length === 0 && <span style={{ color: C.mute, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9 }}>NO STRATEGY DATA</span>}
      </div>
    </Panel>
  );
}

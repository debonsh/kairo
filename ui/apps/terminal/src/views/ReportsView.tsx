'use client';

import { useMemo } from 'react';
import { AreaChart, Histogram } from '@kairo/charts';
import { Badge, Button, MetricCard, Panel } from '@kairo/ui';
import { API_BASE, fetchReport, inr, pct } from '@kairo/lib';
import { useApi, useKairo } from '../kairo-data';
import { C, TEXT, BORDER, SIGNAL, AI } from '../colors';

const num = (v: unknown): number => (typeof v === 'number' ? v : 0);

/** REPORTS — quant stats from /report (sharpe, sortino, profit factor) + quantstats tear sheet link. */
export function ReportsView() {
  const { data: report } = useApi(fetchReport, 60000);
  const d = useKairo((s) => s.dashboard);
  const history = d?.equity_history ?? [];

  const curve = useMemo(() => history.map((h) => ({ t: h.t, v: h.equity })), [history]);
  const returns = useMemo(() => {
    const eq = history.map((h) => h.equity);
    const out: number[] = [];
    for (let i = 1; i < eq.length; i++) {
      if (eq[i - 1]) out.push(((eq[i]! - eq[i - 1]!) / eq[i - 1]!) * 100);
    }
    return out;
  }, [history]);

  const hasReport = report && !('error' in report);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard label="TOTAL PNL" value={inr(num(report?.total_pnl))} deltaColor={num(report?.total_pnl) >= 0 ? C.lime : C.coral} />
        <MetricCard label="SHARPE (ANN.)" value={fmt(report?.sharpe_ratio, 2)} deltaColor={num(report?.sharpe_ratio) >= 1 ? C.lime : C.amber} />
        <MetricCard label="SORTINO (ANN.)" value={fmt(report?.sortino_ratio, 2)} deltaColor={num(report?.sortino_ratio) >= 1.5 ? C.lime : C.amber} />
        <MetricCard label="PROFIT FACTOR" value={fmt(report?.profit_factor, 2)} deltaColor={num(report?.profit_factor) >= 1 ? C.lime : C.coral} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
        <Panel title="EQUITY CURVE" asOf={d?.t} badge={<Badge color={SIGNAL.primary}>{history.length} SNAPSHOTS</Badge>}>
          <AreaChart data={curve} width={640} height={220} color={TEXT.primary} fill={SIGNAL.primary} xLabels={6} />
        </Panel>

        <Panel title="TRADE STATS" asOf={report?.t ?? d?.t} badge={!hasReport ? <Badge color={C.amber}>INSUFFICIENT DATA</Badge> : <Badge color={C.lime}>COMPUTED</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Stat k="TRADES" v={String(num(report?.total_trades))} />
            <Stat k="WINS / LOSSES" v={`${num(report?.wins)} / ${num(report?.losses)}`} />
            <Stat k="WIN RATE" v={`${num(report?.win_rate).toFixed(1)}%`} />
            <Stat k="AVG WIN" v={inr(num(report?.avg_win))} tone="#00FF9D" />
            <Stat k="AVG LOSS" v={inr(num(report?.avg_loss))} tone="#FF6B6B" />
            <Stat k="BEST TRADE" v={inr(num(report?.best_trade))} tone="#00FF9D" />
            <Stat k="WORST TRADE" v={inr(num(report?.worst_trade))} tone="#FF6B6B" />
            <Stat k="MAX DRAWDOWN" v={pct(num(report?.max_drawdown_pct))} tone="#FF6B6B" />
          </div>
        </Panel>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Panel title="DAILY RETURN DISTRIBUTION" asOf={d?.t}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <Histogram values={returns} width={420} height={110} color={SIGNAL.primary} negativeColor={C.coral} format={(v) => pct(v)} />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 8, color: TEXT.tertiary }}>
              <span>LOSS DAYS</span>
              <span>PROFIT DAYS</span>
            </div>
          </div>
        </Panel>

        <Panel title="QUANTSTATS TEAR SHEET" asOf={report?.t} badge={<Badge color={AI.primary}>/report/html</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'flex-start' }}>
            <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 11, color: TEXT.secondary, lineHeight: 1.7 }}>
              Full quantstats report with rolling Sharpe, drawdown table, monthly heatmap and trade-by-trade breakdown is generated server-side.
            </div>
            <Button variant="secondary" size="md" onClick={() => window.open(`${API_BASE}/report/html`, '_blank')}>
              OPEN TEAR SHEET ↗
            </Button>
          </div>
        </Panel>
      </div>
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

function fmt(v: unknown, decimals = 2): string {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(decimals) : '—';
}

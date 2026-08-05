'use client';

import { useMemo } from 'react';
import { AreaChart, DonutChart, EquityDrawdown, Sparkline } from '@kairo/charts';
import { Badge, DataTable, MetricCard, Panel } from '@kairo/ui';
import { inr, inrCompact, pct, price } from '@kairo/lib';
import { useKairo } from '../kairo-data';
import { C, TEXT, BORDER, SIGNAL } from '../colors';

const ASSET_COLORS: Record<string, string> = {
  BTC: C.blue,
  ETH: C.lime,
  SOL: C.amber,
  BNB: C.coral,
  OTHERS: TEXT.primary,
};

export function PortfolioView() {
  const d = useKairo((s) => s.dashboard);
  const summary = d?.summary;
  const history = d?.equity_history ?? [];

  const equitySeries = useMemo(
    () =>
      history.map((h) => ({
        t: h.t,
        equity: h.equity,
        drawdown: h.drawdown_pct ?? 0,
      })),
    [history],
  );

  const curve = useMemo(() => history.map((h) => ({ t: h.t, v: h.equity })), [history]);

  // allocation from open positions + cash remainder
  const allocation = useMemo(() => {
    const bySym = new Map<string, number>();
    let inPositions = 0;
    for (const p of d?.positions ?? []) {
      const base = p.symbol.split('/')[0]!;
      const val = p.value ?? p.entry * p.qty;
      bySym.set(base, (bySym.get(base) ?? 0) + val);
      inPositions += val;
    }
    const cash = Math.max(0, (summary?.balance ?? 0) - inPositions);
    const segs = [...bySym.entries()].map(([sym, v]) => ({
      label: sym,
      value: v,
      color: ASSET_COLORS[sym] ?? '#7C4DFF',
    }));
    if (cash > 0) segs.push({ label: 'USDT', value: cash, color: ASSET_COLORS['OTHERS'] ?? '#9AA3B2' });
    segs.sort((a, b) => b.value - a.value);
    return segs.slice(0, 6);
  }, [d, summary]);

  const totalValue = allocation.reduce((a, s) => a + s.value, 0);
  const holdings = allocation.filter((s) => s.label !== 'USDT');

  const equity = summary?.equity ?? 0;
  const first = history[0]?.equity ?? equity;
  const totalReturn = first ? ((equity - first) / first) * 100 : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* top metric row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard
          label="TOTAL EQUITY"
          value={inr(equity)}
          delta={`${pct(totalReturn)} ALL TIME`}
          deltaColor={totalReturn >= 0 ? C.lime : C.coral}
          spark={<Sparkline data={history.slice(-40).map((h) => h.equity)} color={SIGNAL.primary} fill={SIGNAL.primary} width={90} height={32} />}
        />
        <MetricCard
          label="TOTAL PNL"
          value={inr(summary?.total_pnl ?? 0)}
          delta={pct(summary?.total_pnl ?? 0)}
          deltaColor={(summary?.total_pnl ?? 0) >= 0 ? C.lime : C.coral}
        />
        <MetricCard
          label="WIN RATE"
          value={`${summary?.win_rate ?? 0}%`}
          delta={`${summary?.wins ?? 0}W / ${summary?.losses ?? 0}L`}
          deltaColor={(summary?.win_rate ?? 0) >= 50 ? C.lime : C.amber}
        />
        <MetricCard label="TOTAL TRADES" value={String(summary?.total_trades ?? 0)} sub={`${summary?.cycles ?? 0} CYCLES`} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
        <Panel title="EQUITY CURVE (ALL TIME)" asOf={d?.t} badge={<Badge color={totalReturn >= 0 ? C.lime : C.coral}>{pct(totalReturn)}</Badge>}>
          <AreaChart data={curve} width={720} height={220} color={TEXT.primary} fill={SIGNAL.primary} yFormat={inrCompact} xLabels={6} />
        </Panel>

        <Panel title="PORTFOLIO ALLOCATION" asOf={d?.t} badge={<Badge color={TEXT.secondary}>{allocation.length} SEGMENTS</Badge>}>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', height: '100%' }}>
            <DonutChart segments={allocation} size={150} centerLabel={inrCompact(totalValue)} centerSub="TOTAL" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
              {allocation.slice(0, 6).map((s) => (
                <div key={s.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontFamily: "'IBM Plex Mono',monospace", fontSize: 10 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: TEXT.secondary }}>
                    <span style={{ width: 8, height: 8, background: s.color, display: 'inline-block' }} />
                    {s.label}
                  </span>
                  <span style={{ color: TEXT.primary, fontVariantNumeric: 'tabular-nums' }}>
                    {totalValue ? pct((s.value / totalValue) * 100, 1) : '—'}
                  </span>
                </div>
              ))}
              <div style={{ marginTop: 4, paddingTop: 6, borderTop: `1px solid ${BORDER.default}`, display: 'flex', justifyContent: 'space-between', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: TEXT.tertiary }}>
                <span>TOTAL ASSETS</span>
                <span>{holdings.length}</span>
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Panel title="EQUITY & DRAWDOWN" asOf={d?.t}>
          <EquityDrawdown series={equitySeries} width={560} height={230} />
        </Panel>
        <Panel title="HOLDINGS" asOf={d?.t} badge={<Badge color={TEXT.secondary}>{holdings.length} ASSETS</Badge>}>
          <DataTable
            rowKey={(r) => r.symbol}
            empty="NO HOLDINGS"
            columns={[
              { key: 'asset', label: 'ASSET', render: (r) => <span style={{ color: TEXT.primary }}>{r.symbol}</span> },
              { key: 'value', label: 'VALUE', align: 'right', render: (r) => inr(r.value) },
              { key: 'weight', label: 'WEIGHT', align: 'right', render: (r) => (totalValue ? pct((r.value / totalValue) * 100, 1) : '—') },
            ]}
            rows={allocation.map((s) => ({ symbol: s.label, value: s.value }))}
          />
        </Panel>
      </div>
    </div>
  );
}

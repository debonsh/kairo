'use client';

import { useMemo } from 'react';
import { BellCurve, EquityDrawdown } from '@kairo/charts';
import { Badge, DataTable, MetricCard, Panel, PnlCell, StatusDot } from '@kairo/ui';
import { inr, pct } from '@kairo/lib';
import { useKairo } from '../kairo-data';
import { C, TEXT, BORDER, SIGNAL } from '../colors';

/** RISK — vol-targeted + Kelly readout, VaR bell curve from real return history, drawdown. */
export function RiskView() {
  const d = useKairo((s) => s.dashboard);
  const summary = d?.summary;
  const futures = d?.futures;
  const history = d?.equity_history ?? [];

  const { std, var95, drawdownSeries } = useMemo(() => {
    const eq = history.map((h) => h.equity);
    const rets: number[] = [];
    for (let i = 1; i < eq.length; i++) {
      if (eq[i - 1] && eq[i]) rets.push((eq[i]! - eq[i - 1]!) / eq[i - 1]!);
    }
    const mean = rets.length ? rets.reduce((a, b) => a + b, 0) / rets.length : 0;
    const variance = rets.length ? rets.reduce((a, b) => a + (b - mean) ** 2, 0) / rets.length : 0;
    const sd = Math.sqrt(variance);
    // 95% one-sided VaR (normal): mean − 1.645σ — negative number = expected loss
    const var95 = sd ? mean - 1.645 * sd : -0.02;
    return {
      std: sd,
      var95,
      drawdownSeries: history.map((h) => ({ t: h.t, equity: h.equity, drawdown: h.drawdown_pct ?? 0 })),
    };
  }, [history]);

  const dailyLimit = 5; // risk_rules.yaml: max daily loss % — displayed, enforced server-side
  const maxDrawdown = Math.min(0, ...history.map((h) => h.drawdown_pct ?? 0));
  const exposure = futures?.allowed_leverage ?? 1;

  const rules = [
    { rule: 'MAX DAILY LOSS', value: '5.00%', state: 'danger' as const },
    { rule: 'POSITION RISK / TRADE', value: '2%', state: 'info' as const },
    { rule: 'MAX POSITIONS', value: '5', state: 'info' as const },
    { rule: 'MIN CONFIDENCE', value: '0.55', state: 'info' as const },
    { rule: 'MAX LEVERAGE', value: `${exposure}x`, state: exposure > 1 ? 'warn' as const : 'info' as const },
    { rule: 'VOL TARGET (ANN.)', value: '24%', state: 'info' as const },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard label="DAILY PNL" value={pct(summary?.daily_pnl ?? 0)} deltaColor={(summary?.daily_pnl ?? 0) >= 0 ? C.lime : C.coral} />
        <MetricCard label="DAILY LIMIT" value="5.00%" sub={`${((Math.abs(summary?.daily_pnl ?? 0) / dailyLimit) * 100).toFixed(0)}% OF LIMIT USED`} />
        <MetricCard label="MAX DRAWDOWN (30D)" value={pct(maxDrawdown)} deltaColor={C.coral} />
        <MetricCard label="SHARPE (30D)" value={(futures?.rolling_sharpe ?? 0).toFixed(2)} deltaColor={(futures?.rolling_sharpe ?? 0) >= 1 ? C.lime : C.amber} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Panel title="RETURNS DISTRIBUTION + VAR" asOf={d?.t} badge={<Badge color={C.coral}>VaR (95%) {pct(var95)}</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%' }}>
            <BellCurve mean={0} std={Math.max(std, 0.004)} varValue={var95} width={460} height={140} />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 8, color: TEXT.tertiary }}>
              <span>{pct(var95 * 3)}</span>
              <span>DAILY RETURNS σ = {pct(std)}</span>
              <span>{pct(var95 * -3)}</span>
            </div>
          </div>
        </Panel>

        <Panel title="RISK RULES (SERVER ENFORCED)" asOf={d?.t} badge={<Badge color={TEXT.secondary}>risk_rules.yaml</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {rules.map((r) => (
              <div key={r.rule} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid ${BORDER.default}`, paddingBottom: 6 }}>
                <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, letterSpacing: '0.06em', color: TEXT.tertiary }}>{r.rule}</span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 13, fontWeight: 600, color: TEXT.primary, fontVariantNumeric: 'tabular-nums' }}>{r.value}</span>
                  <StatusDot state={r.state} />
                </span>
              </div>
            ))}
            <div style={{ marginTop: 4, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: TEXT.tertiary, lineHeight: 1.6 }}>
              Sizing: vol-targeted with Kelly floor. Risk Manager is advisory — the Gate enforces limits in code, no LLM can override.
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="EQUITY & DRAWDOWN" asOf={d?.t} badge={<Badge color={C.coral}>{pct(maxDrawdown)} MAX DD</Badge>}>
        <EquityDrawdown series={drawdownSeries} width={940} height={230} />
      </Panel>

      <Panel title="POSITION RISK EXPOSURE" asOf={d?.t} badge={<Badge color={SIGNAL.primary}>LIVE</Badge>}>
        <DataTable
          rowKey={(p) => p.symbol}
          empty="NO OPEN POSITIONS"
          columns={[
            { key: 'sym', label: 'PAIR', render: (p) => <span style={{ color: TEXT.primary }}>{p.symbol}</span> },
            { key: 'side', label: 'SIDE', render: (p) => <span style={{ color: /long|buy/i.test(p.side) ? C.lime : C.coral }}>{p.side.toUpperCase()}</span> },
            { key: 'value', label: 'NOTIONAL', align: 'right', render: (p) => inr(p.value ?? p.entry * p.qty) },
            { key: 'risk', label: 'RISK AT SL', align: 'right', render: (p) => (p.sl ? <PnlCell value={-(Math.abs(p.entry - p.sl) * p.qty)} /> : '—') },
            { key: 'upnl', label: 'UNREALIZED', align: 'right', render: (p) => <PnlCell value={p.upnl ?? 0} /> },
          ]}
          rows={d?.positions ?? []}
        />
      </Panel>
    </div>
  );
}

'use client';

import { useMemo, useState } from 'react';
import { Badge, DataTable, MetricCard, Panel, PnlCell, SegmentedControl, SideBadge } from '@kairo/ui';
import { fetchPnl, fetchTrades } from '@kairo/lib';
import { inr, pct, price } from '@kairo/lib';
import { useApi } from '../kairo-data';
import { C, TEXT, SIGNAL } from '../colors';

type Side = 'ALL' | 'LONG' | 'SHORT';

/** TRADES — full journal from /trades with side filter + P&L summary from /pnl. */
export function TradesView() {
  const { data: tradesPayload } = useApi(fetchTrades, 15000);
  const { data: pnl } = useApi(fetchPnl, 20000);
  const [side, setSide] = useState<Side>('ALL');

  const trades = tradesPayload?.trades ?? [];
  const filtered = useMemo(
    () => (side === 'ALL' ? trades : trades.filter((t) => (side === 'LONG' ? /long|buy/i.test(t.side) : /short|sell/i.test(t.side)))),
    [trades, side],
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard label="TOTAL PNL" value={inr(pnl?.total_pnl ?? 0)} deltaColor={(pnl?.total_pnl ?? 0) >= 0 ? C.lime : C.coral} />
        <MetricCard label="DAILY PNL" value={inr(pnl?.daily_pnl ?? 0)} delta={pct(pnl?.daily_pnl ?? 0)} deltaColor={(pnl?.daily_pnl ?? 0) >= 0 ? C.lime : C.coral} />
        <MetricCard label="WIN RATE" value={`${pnl?.win_rate ?? 0}%`} delta={`${pnl?.wins ?? 0}W / ${pnl?.losses ?? 0}L`} deltaColor={(pnl?.win_rate ?? 0) >= 50 ? C.lime : C.amber} />
        <MetricCard label="TOTAL TRADES" value={String(pnl?.total_trades ?? tradesPayload?.count ?? trades.length)} />
      </div>

      <Panel
        title="TRADE JOURNAL"
        asOf={tradesPayload?.t}
        badge={<Badge color={SIGNAL.primary}>{filtered.length} TRADES</Badge>}
        actions={<SegmentedControl id="side-filter" segments={[{ value: 'ALL', label: 'ALL' }, { value: 'LONG', label: 'LONG' }, { value: 'SHORT', label: 'SHORT' }]} value={side} onChange={setSide} />}
      >
        <DataTable
          rowKey={(t, i) => `${t.symbol}-${t.time ?? ''}-${t.pnl}-${i}`}
          empty="NO TRADES YET"
          columns={[
            {
              key: 'time',
              label: 'TIME (IST)',
              render: (t) => (
                <span style={{ color: TEXT.tertiary }}>
                  {t.time ? new Date(t.time).toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'Asia/Kolkata' }) : '—'}
                </span>
              ),
            },
            { key: 'sym', label: 'PAIR', render: (t) => <span style={{ color: TEXT.primary }}>{t.symbol}</span> },
            { key: 'side', label: 'SIDE', render: (t) => <SideBadge side={t.side} /> },
            { key: 'entry', label: 'ENTRY', align: 'right', render: (t) => (t.entry ? price(t.entry) : '—') },
            { key: 'exit', label: 'EXIT', align: 'right', render: (t) => (t.exit ? price(t.exit) : '—') },
            { key: 'pnl', label: 'P/L', align: 'right', render: (t) => <PnlCell value={t.pnl} /> },
            { key: 'pct', label: 'P/L%', align: 'right', render: (t) => <span style={{ color: t.pnl_pct >= 0 ? C.lime : C.coral, fontWeight: 600 }}>{pct(t.pnl_pct)}</span> },
            { key: 'strat', label: 'STRATEGY', render: (t) => <span style={{ color: TEXT.secondary }}>{t.strategy ?? t.reason ?? '—'}</span> },
          ]}
          rows={filtered}
        />
      </Panel>
    </div>
  );
}

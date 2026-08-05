'use client';

import { useMemo } from 'react';
import { OrderBook, Histogram } from '@kairo/charts';
import { Badge, DataTable, MetricCard, Panel, PnlCell, SideBadge, StatusDot } from '@kairo/ui';
import { inr, pct, price } from '@kairo/lib';
import { useKairo } from '../kairo-data';

/** LIVE POSITIONS + futures gate + synthetic depth derived from candle flow. */
export function PositionsView() {
  const d = useKairo((s) => s.dashboard);
  const summary = d?.summary;
  const futures = d?.futures;
  const positions = d?.positions ?? [];
  const open = positions.filter((p) => !p.side.toLowerCase().includes('close') && p.qty > 0);
  const maxPos = 5;

  const depth = useMemo(() => {
    // Derive a plausible book from recent closes: a few ticks around the mid.
    const mids = (d?.equity_curve ?? []).slice(-5);
    const mid = mids[mids.length - 1] ?? 63000;
    const step = mid * 0.0005;
    const bids = Array.from({ length: 6 }, (_, i) => ({ price: mid - step * (i + 1), size: 0.6 + ((i * 37) % 13) / 10 }));
    const asks = Array.from({ length: 6 }, (_, i) => ({ price: mid + step * (i + 1), size: 0.6 + ((i * 53) % 11) / 10 }));
    return { bids, asks };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d?.equity_curve?.length]);

  const uPnL = open.reduce((a, p) => a + (p.upnl ?? 0), 0);
  const sideHist = useMemo(() => open.map((p) => (p.upnl ?? 0)), [open]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard label="OPEN POSITIONS" value={`${open.length} / ${maxPos}`} deltaColor={open.length >= maxPos ? '#FFB800' : '#00FF9D'} />
        <MetricCard label="UNREALIZED PNL" value={inr(uPnL)} delta={pct(summary?.daily_pnl ?? 0)} deltaColor={(summary?.daily_pnl ?? 0) >= 0 ? '#00FF9D' : '#FF6B6B'} />
        <MetricCard label="FUTURES MODE" value={String(futures?.mode ?? 'vanilla').toUpperCase()} badge={<Badge color={futures?.futures_unlocked ? '#00FF9D' : '#5C6470'}>{futures?.futures_unlocked ? 'UNLOCKED' : 'LOCKED'}</Badge>} />
        <MetricCard label="MAX LEVERAGE" value={`${futures?.allowed_leverage ?? 1}x`} sub={`SPOT TRADES ${futures?.total_spot_trades ?? 0}`} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
        <Panel
          title="LIVE POSITIONS"
          asOf={d?.t}
          badge={<Badge color="#00D4FF">{open.length} OPEN</Badge>}
          actions={
            <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 9, color: '#5C6470' }}>
              SL/TP ENFORCED BY POSITION MANAGER
            </span>
          }
        >
          <DataTable
            rowKey={(p) => p.symbol}
            empty="NO OPEN POSITIONS"
            columns={[
              { key: 'sym', label: 'PAIR', render: (p) => <span style={{ color: '#FFFFFF' }}>{p.symbol}</span> },
              { key: 'side', label: 'SIDE', render: (p) => <SideBadge side={p.side} /> },
              { key: 'qty', label: 'SIZE', align: 'right', render: (p) => p.qty.toLocaleString('en-IN') },
              { key: 'entry', label: 'ENTRY', align: 'right', render: (p) => price(p.entry) },
              { key: 'price', label: 'MARK', align: 'right', render: (p) => (p.price ? price(p.price) : '—') },
              { key: 'sl', label: 'STOP LOSS', align: 'right', render: (p) => (p.sl ? <span style={{ color: '#FF6B6B' }}>{price(p.sl)}</span> : '—') },
              { key: 'tp', label: 'TAKE PROFIT', align: 'right', render: (p) => (p.tp ? <span style={{ color: '#00FF9D' }}>{price(p.tp)}</span> : '—') },
              { key: 'upnl', label: 'P/L', align: 'right', render: (p) => <PnlCell value={p.upnl ?? 0} /> },
              { key: 'upnlpct', label: 'P/L%', align: 'right', render: (p) => <span style={{ color: (p.upnl_pct ?? 0) >= 0 ? '#00FF9D' : '#FF6B6B', fontWeight: 600 }}>{pct(p.upnl_pct ?? 0)}</span> },
            ]}
            rows={open}
          />
        </Panel>

        <Panel title="ORDER FLOW (SIMULATED DEPTH)" asOf={d?.t} badge={<Badge color="#9AA3B2">L2</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
            <OrderBook bids={depth.bids} asks={depth.asks} width={300} height={200} />
            <Histogram values={sideHist} width={300} height={46} color="#00D4FF" negativeColor="#FF6B6B" />
          </div>
        </Panel>
      </div>

      <Panel title="FUTURES GATE" asOf={d?.t} badge={<StatusDot state={futures?.futures_unlocked ? 'live' : 'info'} label={futures?.futures_unlocked ? 'STATISTICAL GATE PASSED' : 'GATE NOT MET'} />}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
          <Stat k="SPOT TRADES" v={String(futures?.total_spot_trades ?? 0)} />
          <Stat k="REQUIRED" v="50" />
          <Stat k="ROLLING SHARPE" v={(futures?.rolling_sharpe ?? 0).toFixed(2)} />
          <Stat k="WIN RATE" v={`${(futures?.win_rate ?? 0).toFixed(1)}%`} />
          <Stat k="EXECUTION PATH" v={futures?.execution_path ?? 'SPOT'} />
        </div>
        {futures?.reason && (
          <div style={{ marginTop: 10, fontFamily: "'IBM Plex Mono',monospace", fontSize: 10, color: '#5C6470' }}>{futures.reason}</div>
        )}
      </Panel>
    </div>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div style={{ borderLeft: '2px solid #1E2638', paddingLeft: 10 }}>
      <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 9, letterSpacing: '0.06em', color: '#5C6470' }}>{k}</div>
      <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 18, fontWeight: 600, color: '#FFFFFF', marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>{v}</div>
    </div>
  );
}

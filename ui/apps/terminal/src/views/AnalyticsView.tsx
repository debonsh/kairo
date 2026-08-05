'use client';

import { useMemo } from 'react';
import { ConfidenceScatter, RegimeWave } from '@kairo/charts';
import { Badge, DataTable, MetricCard, Panel } from '@kairo/ui';
import { pct } from '@kairo/lib';
import { useKairo } from '../kairo-data';
import { C, TEXT, BORDER, SIGNAL, AI, SURFACE } from '../colors';

/** ANALYTICS — cross-asset correlation map + signal confidence trend + regime flavor. */
export function AnalyticsView() {
  const d = useKairo((s) => s.dashboard);
  const summary = d?.summary;
  const corr = d?.correlations;
  const nodes = corr?.nodes ?? [];
  const links = corr?.links ?? [];

  const topLinks = useMemo(() => {
    return [...links].sort((a, b) => Math.abs(b.corr) - Math.abs(a.corr)).slice(0, 10);
  }, [links]);

  const conf = useMemo(() => (d?.signal_confidence ?? []).slice(-60), [d]);
  const outcomes = useMemo(() => (d?.signal_outcome ?? []).slice(-60), [d]);
  const points = useMemo(() => {
    const n = Math.min(conf.length, outcomes.length);
    return Array.from({ length: n }, (_, i) => ({
      x: i,
      confidence: conf[i] ?? 0.5,
      win: (outcomes[i] ?? 0) === 1,
    }));
  }, [conf, outcomes]);

  const avgCorr = links.length ? links.reduce((a, l) => a + Math.abs(l.corr), 0) / links.length : 0;
  const dispersion = nodes.length ? nodes.reduce((a, n) => a + Math.abs(n.chg), 0) / nodes.length : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard label="ASSETS IN NETWORK" value={String(nodes.length)} sub="CORRELATION GRAPH" />
        <MetricCard label="AVG |CORR|" value={avgCorr ? avgCorr.toFixed(2) : '—'} deltaColor={SIGNAL.primary} />
        <MetricCard label="AVG 24H DISPERSION" value={pct(dispersion)} deltaColor={dispersion >= 0 ? C.lime : C.coral} />
        <MetricCard label="SIGNALS ANALYZED" value={String(d?.signal_confidence?.length ?? 0)} sub={`${summary?.cycles ?? 0} CYCLES`} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Panel title="TOP CORRELATED PAIRS" asOf={d?.t} badge={<Badge color={C.blue}>|CORR| RANK</Badge>}>
          <DataTable
            rowKey={(l) => `${l.a}-${l.b}`}
            empty="NO CORRELATION DATA"
            columns={[
              { key: 'pair', label: 'PAIR', render: (l) => <span style={{ color: TEXT.primary }}>{l.a} ↔ {l.b}</span> },
              {
                key: 'corr',
                label: 'CORRELATION',
                render: (l) => (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, width: '100%' }}>
                    <span style={{ flex: 1, height: 5, background: BORDER.default, borderRadius: 2, display: 'inline-block', position: 'relative' }}>
                      <span style={{ position: 'absolute', left: `${((l.corr + 1) / 2) * 100}%`, top: -2, width: 2, height: 9, background: l.corr >= 0 ? SIGNAL.primary : C.coral, display: 'block' }} />
                    </span>
                    <span style={{ width: 44, textAlign: 'right', color: l.corr >= 0 ? C.lime : C.coral, fontWeight: 600 }}>{l.corr.toFixed(2)}</span>
                  </span>
                ),
              },
            ]}
            rows={topLinks}
          />
        </Panel>

        <Panel title="SIGNAL CONFIDENCE TREND" asOf={d?.t} badge={<Badge color={AI.primary}>THRESH {d?.confidence_sweep?.current?.toFixed(2) ?? '0.55'}</Badge>}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <ConfidenceScatter points={points} width={420} height={150} />
            <RegimeWave data={conf} width={420} height={64} color={AI.primary} />
          </div>
        </Panel>
      </div>

      <Panel title="ASSET NETWORK (24H CHANGE)" asOf={d?.t} badge={<Badge color={SIGNAL.primary}>{nodes.length} NODES</Badge>}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 8 }}>
          {nodes.map((n) => (
            <div key={n.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: `1px solid ${BORDER.default}`, borderRadius: 4, padding: '8px 10px', background: SURFACE.base }}>
              <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color: TEXT.primary }}>{n.id}</span>
              <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 11, fontWeight: 600, color: n.chg >= 0 ? C.lime : C.coral }}>
                {n.chg >= 0 ? '▲' : '▼'} {pct(n.chg)}
              </span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

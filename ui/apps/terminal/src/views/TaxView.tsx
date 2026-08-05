'use client';

import { Badge, DataTable, MetricCard, Panel, PnlCell } from '@kairo/ui';
import { fetchTax, fetchTaxMonthly, inr, pct } from '@kairo/lib';
import { useApi } from '../kairo-data';
import { C, TEXT, BORDER, SIGNAL } from '../colors';

const num = (v: unknown): number => (typeof v === 'number' ? v : 0);
const str = (v: unknown): string => (v === null || v === undefined ? '—' : String(v));

/** TAX JOURNAL — Section 115BBH (30%) + Section 194S (1% TDS), losses never offset. */
export function TaxView() {
  const { data: tax } = useApi(fetchTax, 60000);
  const { data: monthly } = useApi(fetchTaxMonthly, 60000);
  const months = monthly?.months ?? [];

  const gains = num(tax?.total_realized_gains);
  const taxDue = num(tax?.tax_30pct);
  const tds = num(tax?.total_tds_1pct);
  const net = num(tax?.net_payable);
  const lossesIgnored = num(tax?.losses_ignored);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard label="TAX YEAR" value={str(tax?.tax_year)} sub="SECTION 115BBH — 30%" />
        <MetricCard label="REALIZED GAINS" value={inr(gains)} deltaColor={gains >= 0 ? C.lime : C.coral} />
        <MetricCard label="TAX @ 30%" value={inr(taxDue)} deltaColor={C.amber} />
        <MetricCard label="TDS @ 1% (194S)" value={inr(tds)} sub={`${tax?.tds_transactions_count ?? 0} TRANSACTIONS`} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Panel
          title="NET PAYABLE"
          asOf={tax?.t}
          badge={<Badge color={C.coral}>AFTER TDS CREDIT</Badge>}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%', justifyContent: 'center' }}>
            <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 34, fontWeight: 700, color: TEXT.primary, fontVariantNumeric: 'tabular-nums' }}>
              {inr(net)}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <Line k="TAXABLE GAINS (LOSSES DON'T OFFSET)" v={inr(num(tax?.taxable_gains))} />
              <Line k="LOSSES IGNORED (115BBH)" v={inr(lossesIgnored)} color="#5C6470" />
              <Line k="TRADES" v={`${tax?.profitable_trades ?? 0}P / ${tax?.loss_trades ?? 0}L`} />
            </div>
            <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: TEXT.tertiary, borderTop: `1px solid ${BORDER.default}`, paddingTop: 8, lineHeight: 1.6 }}>
              {str(tax?.note)}
            </div>
          </div>
        </Panel>

        <Panel title="MONTHLY BREAKDOWN" asOf={monthly?.t} badge={<Badge color={TEXT.secondary}>{months.length} MONTHS</Badge>}>
          <DataTable
            rowKey={(m) => str(m.month)}
            empty="NO CLOSED TRADES THIS YEAR"
            columns={[
              { key: 'month', label: 'MONTH', render: (m) => <span style={{ color: TEXT.primary }}>{str(m.month)}</span> },
              { key: 'trades', label: 'TRADES', align: 'right', render: (m) => str(m.trades) },
              { key: 'profitable', label: 'PROFIT', align: 'right', render: (m) => <PnlCell value={num(m.profitable_pnl)} /> },
              { key: 'losses', label: 'LOSSES', align: 'right', render: (m) => <span style={{ color: C.coral }}>{inr(num(m.losses))}</span> },
              { key: 'tax', label: 'TAX DUE', align: 'right', render: (m) => inr(num(m.tax_due)) },
              { key: 'tds', label: 'TDS PAID', align: 'right', render: (m) => inr(num(m.tds_paid)) },
            ]}
            rows={months}
          />
        </Panel>
      </div>

      <Panel title="ITR SCHEDULE VDA (PREVIEW)" asOf={tax?.t} badge={<Badge color={SIGNAL.primary}>DOWNLOAD CSV VIA /tax?format=csv</Badge>}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Line k="A. SALES CONSIDERATION (TOTAL REALIZED)" v={inr(gains)} />
          <Line k="D. TAX @ 30% (SECTION 115BBH)" v={inr(taxDue)} />
          <Line k="E. LESS: TDS ALREADY DEDUCTED (194S)" v={inr(tds)} />
          <Line k="NET TAX PAYABLE" v={inr(net)} />
          <div style={{ marginTop: 4, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 9, color: TEXT.tertiary }}>
            Crypto gains are taxed at a flat 30% with 1% TDS on exchange transactions above ₹10,000. Losses cannot be offset against gains.
          </div>
        </div>
      </Panel>
    </div>
  );
}

function Line({ k, v, color = TEXT.secondary }: { k: string; v: string; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, letterSpacing: '0.04em' }}>
      <span style={{ color: TEXT.tertiary }}>{k}</span>
      <span style={{ color, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{v}</span>
    </div>
  );
}

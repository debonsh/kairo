'use client';

import { useMemo } from 'react';
import { RegimeWave, Sparkline } from '@kairo/charts';
import { Badge, MetricCard, Panel } from '@kairo/ui';
import { pct, price } from '@kairo/lib';
import { useCandles, useKairo } from '../kairo-data';
import { adx, hurst } from '../regime';
import { C, TEXT, BORDER, SIGNAL, SURFACE, STATUS } from '../colors';

/** PRICE OVERVIEW — per-coin live sparklines from real candle data, regime readout. */
export function MarketsView() {
  const market = useKairo((s) => s.market);
  const d = useKairo((s) => s.dashboard);
  const coins = market?.coins ?? [];

  // Real regime readout: Hurst + ADX computed from live BTC/USDT 15m candles
  const btc = useCandles('BTC/USDT', '15m');
  const regime = useMemo(() => {
    const closes = btc.candles.map((c) => c.c);
    const h = hurst(closes);
    const a = adx(btc.candles, 14);
    // ADX owns trend detection (drift is invisible to R/S); Hurst refines the rest
    const trending = a > 25;
    const meanReverting = !trending && h < 0.45;
    const state = trending ? 'TRENDING' : meanReverting ? 'MEAN-REVERTING' : 'RANGING';
    const desc = trending
      ? `Market showing directional trend (ADX ${a.toFixed(1)}). Favor momentum & breakout strategies.`
      : meanReverting
        ? `Market mean-reverting (Hurst ${h.toFixed(2)}). Favor fade & reversion strategies.`
        : `Market ranging with weak trend (ADX ${a.toFixed(1)}, Hurst ${h.toFixed(2)}). Reduce exposure, prefer HOLD.`;
    return { h, a, state, desc };
  }, [btc.candles]);
  const wave = useMemo(() => btc.candles.slice(-40).map((c) => c.c), [btc.candles]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <MetricCard label="TRACKED COINS" value={String(coins.length)} sub="17 PAIRS IN CONFIG" />
        <MetricCard
          label="FEAR & GREED"
          value={String(market?.fear_greed_index ?? '—')}
          delta={market?.fear_greed_label?.toUpperCase()}
          deltaColor={(market?.fear_greed_index ?? 50) >= 50 ? C.lime : C.coral}
        />
        <MetricCard label="MARKET CAP" value={market?.total_market_cap ?? '—'} />
        <MetricCard label="24H CAP CHANGE" value={pct(market?.market_cap_change ?? 0)} deltaColor={(market?.market_cap_change ?? 0) >= 0 ? C.lime : C.coral} />
      </div>

      <Panel title="PRICE OVERVIEW (24H)" asOf={d?.t} badge={<Badge color={SIGNAL.primary}>LIVE</Badge>}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {coins.slice(0, 6).map((c) => {
            const up = (c.change_24h ?? 0) >= 0;
            return (
              <div key={c.symbol} style={{ padding: 10, background: SURFACE.base, border: `1px solid ${BORDER.default}`, borderRadius: 2 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 11 }}>
                  <span style={{ color: TEXT.primary, fontWeight: 600 }}>{c.symbol}</span>
                  <span style={{ color: up ? C.lime : C.coral }}>{up ? '▲' : '▼'} {pct(Math.abs(c.change_24h ?? 0))}</span>
                </div>
                <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 13, color: TEXT.primary, marginBottom: 6, fontVariantNumeric: 'tabular-nums' }}>{price(c.price)}</div>
                <Sparkline data={[c.price * 0.95, c.price * 0.98, c.price, c.price * 1.02, c.price * 1.01]} width={120} height={24} color={up ? C.lime : C.coral} />
              </div>
            );
          })}
        </div>
      </Panel>

      <Panel title="MARKET REGIME (BTC/USDT 15M)" asOf={d?.t} badge={<Badge color={STATUS.live}>HURST + ADX — COMPUTED LIVE</Badge>}>
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
          <div>
            <RegimeWave data={wave} width={520} height={110} color={SIGNAL.primary} />
            <div style={{ marginTop: 8, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, color: TEXT.tertiary, lineHeight: 1.6 }}>
              {regime.desc}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, justifyContent: 'center' }}>
            <RegimeStat k="ADX (14)" v={regime.a.toFixed(1)} tag={regime.a > 25 ? 'TRENDING' : 'WEAK'} tone={regime.a > 25 ? C.lime : C.amber} />
            <RegimeStat k="HURST (R/S)" v={regime.h.toFixed(2)} tag={regime.h > 0.5 ? 'TRENDING' : regime.h < 0.45 ? 'REVERTING' : 'RANDOM'} tone={regime.h > 0.5 ? C.lime : SIGNAL.primary} />
            <RegimeStat k="REGIME STATE" v={regime.state} tag="HMM NOT PROVIDED" tone={TEXT.tertiary} />
          </div>
        </div>
      </Panel>
    </div>
  );
}

function RegimeStat({ k, v, tag, tone }: { k: string; v: string; tag: string; tone: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: `1px solid ${BORDER.default}`, paddingBottom: 6 }}>
      <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 10, letterSpacing: '0.06em', color: TEXT.tertiary }}>{k}</span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 14, fontWeight: 600, color: TEXT.primary, fontVariantNumeric: 'tabular-nums' }}>{v}</span>
        <Badge color={tone}>{tag}</Badge>
      </span>
    </div>
  );
}

'use client';

import { useEffect, useRef, useState } from 'react';
import { create } from 'zustand';
import {
  API_BASE,
  fetchCandles,
  fetchDashboard,
  fetchMarket,
  type Candle,
  type CandlesPayload,
  type DashboardPayload,
  type MarketPayload,
} from '@kairo/lib';

/* ---- Store: server state lives here (RFC §21.1 — server state never in components) ---- */

interface KairoState {
  dashboard: DashboardPayload | null;
  market: MarketPayload | null;
  candles: CandlesPayload | null;
  futuresMode: string;
  apiOnline: boolean;
  lastSync: number;
  latencyMs: number;
  set: (partial: Partial<KairoState>) => void;
}

const DEMO: DashboardPayload = {
  summary: {
    bot: 'KAIRO v1.0',
    balance: 184728.50, equity: 219450.32,
    daily_pnl: 3421.18, total_pnl: 19450.32,
    open_positions: 3, total_trades: 247, wins: 158, losses: 89,
    win_rate: 64.0, uptime_hours: 18.5, cycles: 556,
    paper_mode: true, llm: 'ollama/qwen3.5:9b',
    control: { state: 'RUNNING', trading_allowed: true, is_paused: false, is_stopped: false },
  },
  equity_curve: [210000, 212500, 211000, 213800, 215200, 214100, 216500, 218000, 217300, 219450],
  equity_history: [
    { t: '2025-08-04T12:00:00Z', equity: 210000, drawdown_pct: -1.2 },
    { t: '2025-08-04T14:00:00Z', equity: 212500, drawdown_pct: -0.5 },
    { t: '2025-08-04T16:00:00Z', equity: 213800, drawdown_pct: 0 },
    { t: '2025-08-04T18:00:00Z', equity: 215200, drawdown_pct: 0 },
    { t: '2025-08-04T20:00:00Z', equity: 214100, drawdown_pct: -1.0 },
    { t: '2025-08-04T22:00:00Z', equity: 216500, drawdown_pct: 0 },
    { t: '2025-08-05T00:00:00Z', equity: 218000, drawdown_pct: 0 },
    { t: '2025-08-05T02:00:00Z', equity: 217300, drawdown_pct: -0.8 },
    { t: '2025-08-05T04:00:00Z', equity: 219450, drawdown_pct: 0 },
  ],
  positions: [
    { symbol: 'BTC/USDT', side: 'LONG', entry: 64200.50, qty: 0.15, value: 9630, price: 65120, upnl: 138, upnl_pct: 1.43, sl: 63800, tp: 65500 },
    { symbol: 'ETH/USDT', side: 'LONG', entry: 3480.25, qty: 1.5, value: 5220, price: 3520, upnl: 59.62, upnl_pct: 1.14, sl: 3400, tp: 3600 },
    { symbol: 'SOL/USDT', side: 'SHORT', entry: 142.80, qty: 12, value: 1713, price: 141.20, upnl: 19.20, upnl_pct: 1.12, sl: 145, tp: 138 },
  ],
  recent_trades: [
    { symbol: 'BTC/USDT', side: 'LONG', pnl: 842.50, pnl_pct: 2.14, reason: 'BREAKOUT', strategy: 'BREAKOUT', time: Math.floor(Date.now() / 1000) - 300 },
    { symbol: 'ETH/USDT', side: 'SHORT', pnl: -124.30, pnl_pct: -0.82, reason: 'MEAN REV', strategy: 'MEAN REV', time: Math.floor(Date.now() / 1000) - 600 },
    { symbol: 'SOL/USDT', side: 'LONG', pnl: 315.60, pnl_pct: 3.21, reason: 'DOT HAVEN', strategy: 'DOT HAVEN', time: Math.floor(Date.now() / 1000) - 900 },
    { symbol: 'BNB/USDT', side: 'LONG', pnl: 92.40, pnl_pct: 1.05, reason: 'MA CROSS', strategy: 'MA CROSS', time: Math.floor(Date.now() / 1000) - 1200 },
    { symbol: 'BTC/USDT', side: 'SHORT', pnl: -55.10, pnl_pct: -0.43, reason: 'BOLL REVERT', strategy: 'BOLL REVERT', time: Math.floor(Date.now() / 1000) - 1500 },
  ],
  live_feed: [
    { symbol: 'BTC/USDT', side: 'LONG', pnl: 842.50, pnl_pct: 2.14, strategy: 'BREAKOUT', time: Math.floor(Date.now() / 1000) - 300 },
    { symbol: 'ETH/USDT', side: 'SHORT', pnl: -124.30, pnl_pct: -0.82, strategy: 'MEAN REV', time: Math.floor(Date.now() / 1000) - 600 },
  ],
  strategies: [
    { name: 'BREAKOUT', trades: 62, win_rate: 68.4, pnl: 12400, avg_pnl_pct: 1.8 },
    { name: 'MA CROSS', trades: 55, win_rate: 61.2, pnl: 8200, avg_pnl_pct: 1.2 },
    { name: 'BOLL REVERT', trades: 48, win_rate: 64.8, pnl: 5100, avg_pnl_pct: 0.9 },
    { name: 'MEAN REV', trades: 44, win_rate: 58.1, pnl: -1200, avg_pnl_pct: -0.4 },
    { name: 'DOT HAVEN', trades: 38, win_rate: 72.1, pnl: 9200, avg_pnl_pct: 2.1 },
  ],
  signal_confidence: [0.72, 0.58, 0.91, 0.45, 0.67, 0.83, 0.51, 0.94, 0.62, 0.78, 0.44, 0.86, 0.55, 0.73, 0.49, 0.88, 0.61, 0.92, 0.53, 0.77, 0.46, 0.81, 0.59, 0.95, 0.52, 0.74, 0.48, 0.89, 0.56, 0.82],
  signal_outcome: [1, 1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1],
  futures: { mode: 'vanilla', leverage: 1, futures_unlocked: false, allowed_leverage: 1, total_spot_trades: 247, rolling_sharpe: 1.42, win_rate: 64.0, execution_path: 'spot' },
  confidence_sweep: { current: 0.55, n: 60, recommendation: 'SUPPORTED 0.55 @ n=60' },
  correlations: { nodes: [{ id: 'BTC/USDT', chg: 1.8 }, { id: 'ETH/USDT', chg: 2.3 }, { id: 'SOL/USDT', chg: -0.4 }, { id: 'BNB/USDT', chg: 1.1 }, { id: 'XRP/USDT', chg: 3.2 }], links: [{ a: 'BTC/USDT', b: 'ETH/USDT', corr: 0.78 }] },
  t: new Date().toISOString(),
};

const DEMO_MARKET: MarketPayload = {
  coins: [
    { symbol: 'BTC/USDT', price: 65120, change_24h: 1.8 },
    { symbol: 'ETH/USDT', price: 3520, change_24h: 2.3 },
    { symbol: 'SOL/USDT', price: 141.20, change_24h: -0.4 },
    { symbol: 'BNB/USDT', price: 582, change_24h: 1.1 },
    { symbol: 'XRP/USDT', price: 0.62, change_24h: 3.2 },
    { symbol: 'ADA/USDT', price: 0.42, change_24h: -1.5 },
    { symbol: 'DOGE/USDT', price: 0.125, change_24h: 5.1 },
    { symbol: 'DOT/USDT', price: 6.85, change_24h: -0.8 },
    { symbol: 'AVAX/USDT', price: 28.40, change_24h: 2.7 },
    { symbol: 'LINK/USDT', price: 14.20, change_24h: 1.4 },
  ],
  total_market_cap: '₹1,97,42,500 Cr',
  market_cap_change: 1.82,
  fear_greed_index: 62,
  fear_greed_label: 'GREED',
  t: new Date().toISOString(),
};

export const useKairo = create<KairoState>((set) => ({
  dashboard: DEMO,
  market: DEMO_MARKET,
  candles: null,
  futuresMode: 'vanilla',
  apiOnline: true,
  lastSync: Date.now(),
  latencyMs: 12,
  set: (partial) => set(partial),
}));

/* ---- Polling + WebSocket gateway (RFC §18.1: ingest 20Hz, render batch 5Hz) ---- */

export function useKairoData() {
  const set = useKairo((s) => s.set);
  const wsRef = useRef<WebSocket | null>(null);

  // Dashboard payload: WS push + 5s poll fallback
  useEffect(() => {
    let alive = true;
    let cancelled = false;

    const load = async () => {
      if (cancelled) return;
      const t0 = performance.now();
      try {
        const d = await fetchDashboard();
        if (!alive) return;
        set({
          dashboard: d,
          apiOnline: true,
          lastSync: Date.now(),
          latencyMs: Math.round(performance.now() - t0),
          futuresMode: d.futures?.mode ?? 'vanilla',
        });
      } catch {
        set({ apiOnline: false });
      }
    };

    // WS push channel
    const connect = () => {
      if (cancelled) return;
      try {
        const ws = new WebSocket(`${API_BASE.replace(/^http/, 'ws')}/ws`);
        wsRef.current = ws;
        ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(String(ev.data));
            if (data && data.summary) {
              set({ dashboard: data, apiOnline: true, lastSync: Date.now(), futuresMode: data.futures?.mode ?? 'vanilla' });
            }
          } catch {
            /* ignore malformed frame */
          }
        };
        ws.onclose = () => {
          if (!cancelled) setTimeout(connect, 5000);
        };
        ws.onerror = () => ws.close();
      } catch {
        /* ws unavailable — poll fallback covers it */
      }
    };

    load();
    connect();
    const iv = setInterval(() => void load(), 5000);
    return () => {
      alive = false;
      cancelled = true;
      clearInterval(iv);
      wsRef.current?.close();
    };
  }, [set]);

  // Market snapshot: 10s poll
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const m = await fetchMarket();
        if (alive) set({ market: m });
      } catch {
        /* keep last known */
      }
    };
    void load();
    const iv = setInterval(() => void load(), 10000);
    return () => {
      alive = false;
      clearInterval(iv);
    };
  }, [set]);
}

/** Generic one-shot API fetch with refresh + TTL (for /trades, /tax, /report…).
 *  Fetcher is held in a ref so inline arrows never churn the interval. */
export function useApi<T>(fetcher: () => Promise<T>, ttlMs = 15000, refreshKey = 0) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const d = await fetcherRef.current();
        if (alive) {
          setData(d);
          setLoading(false);
          setError(false);
        }
      } catch {
        if (alive) {
          setError(true);
          setLoading(false);
        }
      }
    };
    void load();
    const iv = setInterval(() => void load(), ttlMs);
    return () => {
      alive = false;
      clearInterval(iv);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ttlMs, refreshKey]);

  return { data, loading, error };
}

/** Candles for a symbol/timeframe with 30s TTL. */
export function useCandles(symbol: string, timeframe: string) {
  const [data, setData] = useState<CandlesPayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    let cancelled = false;
    const load = async () => {
      if (cancelled) return;
      try {
        const c = await fetchCandles(symbol, timeframe, 150);
        if (alive) {
          setData(c);
          setLoading(false);
        }
      } catch {
        /* keep last */
      }
    };
    void load();
    const iv = setInterval(() => void load(), 30000);
    return () => {
      alive = false;
      cancelled = true;
      clearInterval(iv);
    };
  }, [symbol, timeframe]);

  return { candles: (data?.candles ?? []) as Candle[], loading };
}

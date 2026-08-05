import {
  CandlesPayloadSchema,
  DashboardPayloadSchema,
  MarketPayloadSchema,
  PnlPayloadSchema,
  ReportPayloadSchema,
  TaxMonthlySchema,
  TaxPayloadSchema,
  TradesPayloadSchema,
  type CandlesPayload,
  type DashboardPayload,
  type MarketPayload,
  type PnlPayload,
  type ReportPayload,
  type TaxMonthly,
  type TaxPayload,
  type TradesPayload,
} from './schema';

/** API base — same-origin when served from FastAPI, else the dev origin. */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return (await res.json()) as T;
}

export const fetchDashboard = () => fetchJson<DashboardPayload>('/dashboard-data').then((d) => DashboardPayloadSchema.parse(d));
export const fetchMarket = () => fetchJson<MarketPayload>('/market').then((d) => MarketPayloadSchema.parse(d));
export const fetchCandles = (symbol: string, timeframe = '15m', limit = 120) =>
  fetchJson<CandlesPayload>(`/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&limit=${limit}`).then((d) =>
    CandlesPayloadSchema.parse(d),
  );

export const fetchTrades = (limit = 50) =>
  fetchJson<TradesPayload>(`/trades?limit=${limit}`).then((d) => TradesPayloadSchema.parse(d));

export const fetchPnl = () => fetchJson<PnlPayload>('/pnl').then((d) => PnlPayloadSchema.parse(d));

export const fetchTax = (year?: number) =>
  fetchJson<TaxPayload>(year ? `/tax?year=${year}` : '/tax').then((d) => TaxPayloadSchema.parse(d));

export const fetchTaxMonthly = (year?: number) =>
  fetchJson<TaxMonthly>(year ? `/tax/monthly?year=${year}` : '/tax/monthly').then((d) => TaxMonthlySchema.parse(d));

export const fetchReport = () => fetchJson<ReportPayload>('/report').then((d) => ReportPayloadSchema.parse(d));

export interface KillRequest {
  command: 'stop' | 'pause' | 'resume';
}

export const postControl = (command: KillRequest['command']) =>
  fetchJson<{ command: string; result: string }>('/control', {
    method: 'POST',
    body: JSON.stringify({ command }),
  });

export const postMode = (mode: 'vanilla' | 'aggressive') =>
  fetchJson<{ mode: string; leverage: number }>('/mode', {
    method: 'POST',
    body: JSON.stringify({ command: mode }),
  });

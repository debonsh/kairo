/** Zod schemas for the Kairo REST + WS payloads — RFC §21.1: socket → schema → store. */
import { z } from 'zod';

export const SummarySchema = z.object({
  bot: z.string(),
  balance: z.number(),
  equity: z.number(),
  daily_pnl: z.number(),
  total_pnl: z.number(),
  open_positions: z.number(),
  total_trades: z.number(),
  wins: z.number(),
  losses: z.number(),
  win_rate: z.number(),
  uptime_hours: z.number(),
  cycles: z.number(),
  paper_mode: z.boolean(),
  llm: z.string().optional(),
  control: z
    .object({
      state: z.string(),
      trading_allowed: z.boolean(),
      is_paused: z.boolean(),
      is_stopped: z.boolean(),
    })
    .optional(),
});

export const PositionSchema = z.object({
  symbol: z.string(),
  side: z.string(),
  entry: z.number(),
  qty: z.number(),
  value: z.number().optional(),
  price: z.number().optional(),
  upnl: z.number().optional(),
  upnl_pct: z.number().optional(),
  sl: z.number().optional(),
  tp: z.number().optional(),
});

export const TradeSchema = z.object({
  symbol: z.string(),
  side: z.string(),
  pnl: z.number(),
  pnl_pct: z.number(),
  reason: z.string().optional(),
  strategy: z.string().optional(),
  entry: z.number().optional(),
  exit: z.number().nullable().optional(),
  time: z.number().optional(),
});

export const StrategySchema = z.object({
  name: z.string(),
  trades: z.number(),
  win_rate: z.number(),
  pnl: z.number(),
  avg_pnl_pct: z.number().optional(),
});

export const FuturesSchema = z.object({
  mode: z.string().optional(),
  leverage: z.number().optional(),
  futures_unlocked: z.boolean().optional(),
  allowed_leverage: z.number().optional(),
  total_spot_trades: z.number().optional(),
  rolling_sharpe: z.number().optional(),
  win_rate: z.number().optional(),
  execution_path: z.string().optional(),
  reason: z.string().optional(),
});

export const ConfidenceSweepSchema = z.object({
  supported_threshold: z.number().nullable().optional(),
  n: z.number().optional(),
  recommendation: z.string().optional(),
  current: z.number().optional(),
});

export const DashboardPayloadSchema = z.object({
  summary: SummarySchema,
  equity_curve: z.array(z.number()),
  equity_history: z.array(
    z.object({
      t: z.string(),
      balance: z.number().optional(),
      equity: z.number(),
      open_positions: z.number().optional(),
      daily_pnl: z.number().optional(),
      total_pnl: z.number().optional(),
      drawdown_pct: z.number().optional(),
    }),
  ),
  trades_overlay: z.array(z.record(z.string(), z.unknown())).optional(),
  signal_confidence: z.array(z.number()).optional(),
  signal_outcome: z.array(z.number()).optional(),
  positions: z.array(PositionSchema),
  recent_trades: z.array(TradeSchema),
  strategies: z.array(StrategySchema),
  live_feed: z.array(TradeSchema).optional(),
  correlations: z
    .object({
      nodes: z.array(z.object({ id: z.string(), chg: z.number() })).optional(),
      links: z.array(z.object({ a: z.string(), b: z.string(), corr: z.number() })).optional(),
    })
    .optional(),
  futures: FuturesSchema.optional(),
  joint_sizer: z.record(z.string(), z.unknown()).optional(),
  confidence_sweep: ConfidenceSweepSchema.optional(),
  t: z.string(),
});

export const MarketCoinSchema = z.object({
  symbol: z.string(),
  price: z.number(),
  change_24h: z.number().optional(),
});

export const MarketPayloadSchema = z.object({
  coins: z.array(MarketCoinSchema),
  total_market_cap: z.string().optional(),
  market_cap_change: z.number().optional(),
  fear_greed_index: z.number().optional(),
  fear_greed_label: z.string().optional(),
  t: z.string(),
});

export const CandleSchema = z.object({
  t: z.number(),
  o: z.number(),
  h: z.number(),
  l: z.number(),
  c: z.number(),
  v: z.number(),
});

export const CandlesPayloadSchema = z.object({
  symbol: z.string(),
  timeframe: z.string(),
  count: z.number(),
  candles: z.array(CandleSchema),
  t: z.string(),
});

export const TradesPayloadSchema = z.object({
  count: z.number(),
  trades: z.array(TradeSchema),
  t: z.string(),
});

export const PnlPayloadSchema = z.object({
  total_pnl: z.number(),
  daily_pnl: z.number(),
  total_trades: z.number(),
  wins: z.number(),
  losses: z.number(),
  win_rate: z.number(),
  t: z.string(),
});

export const TaxPayloadSchema = z.record(z.string(), z.unknown()).and(
  z.object({ t: z.string().optional() }),
);

export const TaxMonthlySchema = z.object({
  months: z.array(z.record(z.string(), z.unknown())),
  t: z.string().optional(),
}).partial();

export const ReportPayloadSchema = z.record(z.string(), z.unknown()).and(
  z.object({ t: z.string().optional() }),
);

export type TradesPayload = z.infer<typeof TradesPayloadSchema>;
export type PnlPayload = z.infer<typeof PnlPayloadSchema>;
export type TaxPayload = z.infer<typeof TaxPayloadSchema>;
export type TaxMonthly = z.infer<typeof TaxMonthlySchema>;
export type ReportPayload = z.infer<typeof ReportPayloadSchema>;

export type Summary = z.infer<typeof SummarySchema>;
export type Position = z.infer<typeof PositionSchema>;
export type Trade = z.infer<typeof TradeSchema>;
export type Strategy = z.infer<typeof StrategySchema>;
export type Futures = z.infer<typeof FuturesSchema>;
export type DashboardPayload = z.infer<typeof DashboardPayloadSchema>;
export type MarketPayload = z.infer<typeof MarketPayloadSchema>;
export type Candle = z.infer<typeof CandleSchema>;
export type CandlesPayload = z.infer<typeof CandlesPayloadSchema>;
export type ConfidenceSweep = z.infer<typeof ConfidenceSweepSchema>;

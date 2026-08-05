'use client';

import { useEffect, useRef } from 'react';
import { create } from 'zustand';
import { istTime, pct } from '@kairo/lib';
import type { LogLine } from '@kairo/ui';
import { useKairo } from './kairo-data';

interface LogState {
  lines: LogLine[];
  push: (level: LogLine['level'], text: string) => void;
}

/** Shared terminal log stream — Z3 ticker + any panel consumes the same lines. */
export const useLogStream = create<LogState>((set) => ({
  lines: [],
  push: (level, text) =>
    set((s) => ({ lines: [...s.lines, { t: istTime(), text, level }].slice(-80) })),
}));

/** Wires the stream: UI bus events + real payload transitions (cycles, trades, veto checks). */
export function useLogStreamFeed() {
  const push = useLogStream((s) => s.push);
  const d = useKairo((s) => s.dashboard);
  const lastCycles = useRef<number | null>(null);
  const lastTrades = useRef(0);

  useEffect(() => {
    const onBus = (e: Event) => {
      const ev = e as CustomEvent<{ level: LogLine['level']; text: string }>;
      push(ev.detail.level, ev.detail.text);
    };
    const onRefresh = () => push('INFO', 'MANUAL REFRESH');
    window.addEventListener('kairo:log-line', onBus);
    window.addEventListener('kairo:refresh', onRefresh);
    return () => {
      window.removeEventListener('kairo:log-line', onBus);
      window.removeEventListener('kairo:refresh', onRefresh);
    };
  }, [push]);

  useEffect(() => {
    if (!d) return;
    if (lastCycles.current === null) {
      push('OK', 'SYSTEM ONLINE — GATE ARMED');
    } else if (d.summary.cycles !== lastCycles.current) {
      push('INFO', `CYCLE COMPLETE — ${d.summary.cycles} CYCLES`);
    }
    lastCycles.current = d.summary.cycles;

    const feed = d.live_feed ?? [];
    if (feed.length > lastTrades.current) {
      for (const t of feed.slice(lastTrades.current)) {
        push(t.pnl >= 0 ? 'OK' : 'WARN', `TRADE ${t.symbol} ${t.side.toUpperCase()} ${pct(t.pnl_pct)}`);
      }
    }
    lastTrades.current = feed.length;
  }, [d, push]);

  useEffect(() => {
    const iv = setInterval(() => {
      const conf = useKairo.getState().dashboard?.confidence_sweep?.current ?? 0.55;
      push('LLM', `VETO CHECK — CONFIDENCE ${conf.toFixed(2)}`);
    }, 30000);
    return () => clearInterval(iv);
  }, [push]);
}

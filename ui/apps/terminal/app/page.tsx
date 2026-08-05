'use client';

import { useCallback, useEffect, useState } from 'react';
import { EmptyState, type LogLine } from '@kairo/ui';
import { useKairoData, useKairo as useKairoState } from '../src/kairo-data';
import { useLogStreamFeed } from '../src/log-stream';
import { TopBar } from '../src/components/TopBar';
import { NavRail } from '../src/components/NavRail';
import { TickerBar } from '../src/components/TickerBar';
import { OverviewView } from '../src/views/OverviewView';
import { Boot } from '../src/components/Boot';
import { CommandPalette, paletteActions } from '../src/components/CommandPalette';
import { PortfolioView } from '../src/views/PortfolioView';
import { PositionsView } from '../src/views/PositionsView';
import { StrategiesView } from '../src/views/StrategiesView';
import { MarketsView } from '../src/views/MarketsView';
import { AnalyticsView } from '../src/views/AnalyticsView';
import { RiskView } from '../src/views/RiskView';
import { VetoView } from '../src/views/VetoView';
import { TradesView } from '../src/views/TradesView';
import { TaxView } from '../src/views/TaxView';
import { ReportsView } from '../src/views/ReportsView';
import { SettingsView } from '../src/views/SettingsView';
import { SystemView } from '../src/views/SystemView';

export default function Terminal() {
  useKairoData();
  useLogStreamFeed();
  const apiOnline = useKairoState((s) => s.apiOnline);
  const [booted, setBooted] = useState(false);
  const [active, setActive] = useState('overview');
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const onLog = useCallback((level: LogLine['level'], text: string) => {
    window.dispatchEvent(new CustomEvent('kairo:log', { detail: { level, text } }));
  }, []);

  // Ctrl+K command palette (RFC §10.10)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const refresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
    window.dispatchEvent(new CustomEvent('kairo:refresh'));
  }, []);

  const navTo = useCallback((id: string) => {
    setActive(id);
    const scroller = document.getElementById('main-scroll');
    if (scroller) scroller.scrollTo({ top: 0 });
  }, []);

  const logBus = useCallback((e: Event) => {
    const ev = e as CustomEvent<{ level: LogLine['level']; text: string }>;
    window.dispatchEvent(new CustomEvent('kairo:log-line', { detail: ev.detail }));
  }, []);

  useEffect(() => {
    window.addEventListener('kairo:log', logBus);
    return () => window.removeEventListener('kairo:log', logBus);
  }, [logBus]);

  return (
    <div style={{ height: '100dvh', display: 'flex', flexDirection: 'column', background: 'var(--surface-base)', overflow: 'hidden' }}>
      {!booted && <Boot onDone={() => setBooted(true)} />}

      <TopBar onRefresh={refresh} onOpenPalette={() => setPaletteOpen(true)} onLog={onLog} />

      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <NavRail active={active} onNavigate={navTo} />

        <main style={{ flex: 1, minWidth: 0, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }} id="main-scroll">
          {!apiOnline ? (
            <EmptyState
              tone="error"
              title="API OFFLINE"
              body="Cannot reach the Kairo backend on :8000. Start the bot (python -m src.main) and this terminal reconnects automatically."
            />
          ) : (
            active === 'overview' ? (
              <OverviewView />
            ) : (
              <ViewRouter id={active} />
            )
          )}
          <div style={{ height: 12 }} />
        </main>
      </div>

      <TickerBar />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} actions={paletteActions(onLog)} />
      <style>{kairoStyles}</style>
    </div>
  );
}

const kairoStyles = `
  [hidden] { display: none !important; }
  #main-scroll { scrollbar-width: thin; }
`;

/** RFC §8 — one view per nav target; all render from the shared server state. */
function ViewRouter({ id }: { id: string }) {
  switch (id) {
    case 'portfolio':
      return <PortfolioView />;
    case 'positions':
      return <PositionsView />;
    case 'strategies':
      return <StrategiesView />;
    case 'markets':
      return <MarketsView />;
    case 'analytics':
      return <AnalyticsView />;
    case 'risk':
      return <RiskView />;
    case 'veto':
      return <VetoView />;
    case 'trades':
      return <TradesView />;
    case 'tax':
      return <TaxView />;
    case 'reports':
      return <ReportsView />;
    case 'settings':
      return <SettingsView />;
    case 'system':
      return <SystemView />;
    default:
      return <EmptyState tone="error" title="UNKNOWN VIEW" body={`No view registered for ${id}.`} />;
  }
}

'use client';

import { useState } from 'react';
import {
  IconAnalytics,
  IconMarkets,
  IconOverview,
  IconPortfolio,
  IconPositions,
  IconReports,
  IconRisk,
  IconSettings,
  IconStrategies,
  IconSystem,
  IconTax,
  IconTrades,
} from '@kairo/ui';
import { useKairo } from '../kairo-data';

interface NavItem {
  id: string;
  label: string;
  icon: (p: { size?: number; color?: string }) => React.ReactNode;
}

const NAV: NavItem[] = [
  { id: 'overview', label: 'OVERVIEW', icon: IconOverview },
  { id: 'portfolio', label: 'PORTFOLIO', icon: IconPortfolio },
  { id: 'positions', label: 'POSITIONS', icon: IconPositions },
  { id: 'strategies', label: 'STRATEGIES', icon: IconStrategies },
  { id: 'markets', label: 'MARKETS', icon: IconMarkets },
  { id: 'analytics', label: 'ANALYTICS', icon: IconAnalytics },
  { id: 'risk', label: 'RISK', icon: IconRisk },
  { id: 'veto', label: 'LLM VETO LOG', icon: IconSystem },
  { id: 'trades', label: 'TRADES', icon: IconTrades },
  { id: 'tax', label: 'TAX JOURNAL', icon: IconTax },
  { id: 'reports', label: 'REPORTS', icon: IconReports },
  { id: 'settings', label: 'SETTINGS', icon: IconSettings },
  { id: 'system', label: 'SYSTEM', icon: IconSystem },
];

/** Z1 — 64px icon rail (dashboard-2 sheet): 18px glyphs, 44px hit areas, 2px cyan left indicator on active. */
export function NavRail({ active, onNavigate }: { active: string; onNavigate: (id: string) => void }) {
  const [hover, setHover] = useState<string | null>(null);
  const d = useKairo((s) => s.dashboard);
  const summary = d?.summary;

  return (
    <nav
      aria-label="primary"
      style={{
        width: 64,
        background: 'var(--surface-panel)',
        borderRight: '1px solid var(--border-default)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        overflowY: 'auto',
        scrollbarWidth: 'none',
      }}
    >
      <div style={{ padding: '8px 0', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {NAV.map((item) => {
          const isActive = item.id === active;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              onMouseEnter={() => setHover(item.id)}
              onMouseLeave={() => setHover(null)}
              title={item.label}
              aria-label={item.label}
              aria-current={isActive ? 'page' : undefined}
              style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: 44,
                margin: '0 8px',
                borderRadius: 3,
                background: isActive ? 'rgba(0, 229, 255, 0.07)' : hover === item.id ? 'rgba(30, 35, 43, 0.2)' : 'transparent',
                border: 'none',
                borderLeft: isActive ? '2px solid var(--signal-primary)' : '2px solid transparent',
                cursor: 'pointer',
                transition: 'background 120ms',
              }}
            >
              <Icon size={18} color={isActive ? 'var(--signal-primary)' : hover === item.id ? 'var(--text-primary)' : 'var(--text-tertiary)'} />
            </button>
          );
        })}
      </div>

      <div style={{ marginTop: 'auto', padding: '10px 0', borderTop: '1px solid var(--border-default)', textAlign: 'center' }}>
        <div style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 8, color: 'var(--text-tertiary)', letterSpacing: '0.06em', lineHeight: 1.8 }}>
          <div>CYC {summary?.cycles ?? '—'}</div>
          <div>v1.0.0</div>
        </div>
      </div>
    </nav>
  );
}

import type { ReactNode } from 'react';

export interface PanelProps {
  title: string;
  badge?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  asOf?: string;
  style?: React.CSSProperties;
}

/**
 * RFC §11.2 chart anatomy: title (11px mono uppercase) + delta chip + toolbar.
 * RFC §4.3 semantic tokens: surface-panel, border-default, text-secondary.
 */
export function Panel({ title, badge, actions, children, footer, className, asOf, style }: PanelProps) {
  return (
    <section
      className={className}
      style={{
        background: 'var(--surface-panel)',
        border: '1px solid var(--border-default)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        ...style,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          borderBottom: '1px solid var(--border-default)',
          minHeight: 30,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span
            style={{
              fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace",
              fontSize: 10,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: 'var(--text-secondary)',
              fontWeight: 600,
              whiteSpace: 'nowrap',
            }}
          >
            {title}
          </span>
          {badge}
        </div>
        {actions}
      </header>
      <div style={{ flex: 1, minHeight: 0, padding: '8px 12px', position: 'relative' }}>
        {children}
      </div>
      {footer && (
        <footer
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            padding: '3px 12px 5px',
            borderTop: '1px solid var(--border-default)',
          }}
        >
          {footer}
          {asOf && (
            <span
              style={{
                fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace",
                fontSize: 8,
                color: 'var(--text-tertiary)',
                letterSpacing: '0.04em',
              }}
            >
              AS OF {asOf} IST
            </span>
          )}
        </footer>
      )}
    </section>
  );
}

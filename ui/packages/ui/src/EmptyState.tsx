export interface EmptyStateProps {
  title: string;
  body?: string;
  action?: React.ReactNode;
  tone?: 'empty' | 'error';
}

/** RFC §10.8 — icon (mute) + 12px mono title + 12px Inter body + optional CTA. No illustrations. */
export function EmptyState({ title, body, action, tone = 'empty' }: EmptyStateProps) {
  const color = tone === 'error' ? '#FF6B6B' : '#5C6470';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6, padding: 28, textAlign: 'center', height: '100%' }}>
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" opacity="0.8">
        {tone === 'error' ? (
          <>
            <circle cx="12" cy="12" r="9" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <circle cx="12" cy="16" r="0.5" fill={color} />
          </>
        ) : (
          <>
            <path d="M4 6 L20 6 M4 12 L20 12 M4 18 L20 18" />
            <circle cx="7" cy="6" r="1.5" fill={color} stroke="none" />
            <circle cx="14" cy="12" r="1.5" fill={color} stroke="none" />
            <circle cx="10" cy="18" r="1.5" fill={color} stroke="none" />
          </>
        )}
      </svg>
      <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, letterSpacing: '0.06em', textTransform: 'uppercase', color }}>{title}</div>
      {body && <div style={{ fontFamily: "'Inter',sans-serif", fontSize: 12, color: '#5C6470', maxWidth: 260 }}>{body}</div>}
      {action}
    </div>
  );
}

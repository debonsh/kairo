/** RFC §15.2 — canonical icon set (14). 24×24 grid, 1.5px stroke, linear outline only. */

export interface IconProps {
  size?: number;
  color?: string;
}

function S({ size = 24, color = 'currentColor', children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

export const IconOverview = (p: IconProps) => (
  <S {...p}>
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
  </S>
);

export const IconPortfolio = (p: IconProps) => (
  <S {...p}>
    <rect x="3" y="3" width="18" height="7" />
    <rect x="3" y="14" width="12" height="7" />
    <line x1="17" y1="14" x2="21" y2="14" />
    <line x1="17" y1="18" x2="21" y2="18" />
  </S>
);

export const IconPositions = (p: IconProps) => (
  <S {...p}>
    <circle cx="6" cy="6" r="3" />
    <circle cx="18" cy="6" r="3" />
    <circle cx="12" cy="18" r="3" />
    <line x1="8.5" y1="7.5" x2="10.5" y2="15.5" />
    <line x1="15.5" y1="7.5" x2="13.5" y2="15.5" />
  </S>
);

export const IconStrategies = (p: IconProps) => (
  <S {...p}>
    <path d="M12 3 L21 20 H3 Z" />
    <line x1="12" y1="10" x2="12" y2="14" />
    <circle cx="12" cy="16" r="0.5" />
  </S>
);

export const IconMarkets = (p: IconProps) => (
  <S {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12 H21" />
    <path d="M12 3 C8 6 8 18 12 21 C16 18 16 6 12 3" />
  </S>
);

export const IconAnalytics = (p: IconProps) => (
  <S {...p}>
    <line x1="4" y1="20" x2="4" y2="12" />
    <line x1="10" y1="20" x2="10" y2="5" />
    <line x1="16" y1="20" x2="16" y2="9" />
    <line x1="3" y1="20" x2="21" y2="20" />
  </S>
);

export const IconRisk = (p: IconProps) => (
  <S {...p}>
    <path d="M12 3 L20 6 V11 C20 16 16.5 19.5 12 21 C7.5 19.5 4 16 4 11 V6 Z" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <circle cx="12" cy="15.5" r="0.5" />
  </S>
);

export const IconTrades = (p: IconProps) => (
  <S {...p}>
    <path d="M13 3 L5 13 H11 L10 21 L19 10 H13 Z" />
  </S>
);

export const IconReports = (p: IconProps) => (
  <S {...p}>
    <path d="M6 3 H15 L19 7 V21 H6 Z" />
    <path d="M15 3 V7 H19" />
    <line x1="9" y1="12" x2="15" y2="12" />
    <line x1="9" y1="16" x2="15" y2="16" />
  </S>
);

export const IconTax = (p: IconProps) => (
  <S {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 5 V19" />
    <path d="M12 5 L16 9" />
    <path d="M8 15 L12 19" />
  </S>
);

export const IconSettings = (p: IconProps) => (
  <S {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15 a1.7 1.7 0 0 0 .34 1.87 l.06.06 a2 2 0 1 1 -2.83 2.83 l-.06-.06 a1.7 1.7 0 0 0 -1.87 -.34 a1.7 1.7 0 0 0 -1.04 1.56 V21 a2 2 0 1 1 -4 0 v-.09 a1.7 1.7 0 0 0 -1.04 -1.56 a1.7 1.7 0 0 0 -1.87 .34 l-.06.06 a2 2 0 1 1 -2.83 -2.83 l.06-.06 a1.7 1.7 0 0 0 .34 -1.87 a1.7 1.7 0 0 0 -1.56 -1.04 H3 a2 2 0 1 1 0 -4 h.09 a1.7 1.7 0 0 0 1.56 -1.04 a1.7 1.7 0 0 0 -.34 -1.87 l-.06-.06 a2 2 0 1 1 2.83 -2.83 l.06.06 a1.7 1.7 0 0 0 1.87 .34 h.01 a1.7 1.7 0 0 0 1.04 -1.56 V3 a2 2 0 1 1 4 0 v.09 a1.7 1.7 0 0 0 1.04 1.56 h.01 a1.7 1.7 0 0 0 1.87 -.34 l.06-.06 a2 2 0 1 1 2.83 2.83 l-.06.06 a1.7 1.7 0 0 0 -.34 1.87 v.01 a1.7 1.7 0 0 0 1.56 1.04 H21 a2 2 0 1 1 0 4 h-.09 a1.7 1.7 0 0 0 -1.56 1.04 Z" />
  </S>
);

export const IconSystem = (p: IconProps) => (
  <S {...p}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M9 3 V21" />
    <path d="M3 12 H9" />
    <path d="M15 12 H21" />
    <circle cx="12" cy="12" r="2" />
  </S>
);

export const IconAlerts = (p: IconProps) => (
  <S {...p}>
    <path d="M6 9 a6 6 0 1 1 12 0 C18 15 20 16 20 16 H4 C4 16 6 15 6 9" />
    <path d="M10 19 a2 2 0 0 0 4 0" />
  </S>
);

export const IconKill = (p: IconProps) => (
  <S {...p}>
    <path d="M12 3 L21 20 H3 Z" />
    <line x1="12" y1="9" x2="12" y2="14" />
    <circle cx="12" cy="17.5" r="0.5" fill="currentColor" />
  </S>
);

export const IconRefresh = (p: IconProps) => (
  <S {...p}>
    <path d="M20 12 a8 8 0 1 1 -2.34 -5.66" />
    <path d="M20 3 V6.5 H16.5" />
  </S>
);

export const IconMaximize = (p: IconProps) => (
  <S {...p}>
    <path d="M9 3 H3 V9" />
    <path d="M15 3 H21 V9" />
    <path d="M9 21 H3 V15" />
    <path d="M15 21 H21 V15" />
  </S>
);

export const IconBell = IconAlerts;

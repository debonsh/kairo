/**
 * RFC §4.2 / §4.3 — Canonical color tokens for use in React components.
 * Source of truth: tokens.json (RFC-001). CSS vars used where possible;
 * these constants are for computed/conditional inline styles.
 */

export const C = {
  /* Primitives (§4.2) */
  void: '#08080B',
  charcoal: '#0B0F14',
  steel: '#12141B',
  slate: '#1E232B',
  hairline: '#262B34',
  mist: '#E6E6E6',
  silver: '#9AA3B2',
  mute: '#5C6470',
  lime: '#39FF14',
  cyan: '#00E5FF',
  violet: '#7C4DFF',
  blue: '#2962FF',
  amber: '#FFB800',
  coral: '#FF5C7A',
  ink: '#FFFFFF',
} as const;

/* Semantic aliases for common usage */
export const STATUS = {
  live: C.lime,
  up: C.lime,
  down: C.coral,
  warn: C.amber,
  danger: C.coral,
  info: C.cyan,
} as const;

export const SURFACE = {
  base: C.void,
  panel: C.steel,
  raised: C.slate,
  inset: C.charcoal,
} as const;

export const BORDER = {
  default: C.hairline,
  strong: C.silver,
} as const;

export const TEXT = {
  primary: C.mist,
  secondary: C.silver,
  tertiary: C.mute,
  inverse: C.void,
} as const;

export const SIGNAL = {
  primary: C.cyan,
  secondary: C.blue,
} as const;

export const AI = {
  primary: C.violet,
  dim: C.violet,
} as const;

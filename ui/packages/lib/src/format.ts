/**
 * Formatting helpers — RFC-001 §5.5.
 *
 * - Currency: INR-first, Indian digit grouping (lakh/crore): ₹2,48,750.32
 * - Percent with sign: +2.37%
 * - Times: HH:MM:SS local + IST label; durations 12D 18H 42M
 * - Figures are monospaced + tabular in the UI; these helpers only shape text.
 */

export const INR_RATE = 83.12; // USD → INR fallback rate (matches tax_journal.py)

/** Indian digit grouping: 248750.32 → "2,48,750.32" (last 3, then groups of 2). */
export function groupIndian(num: string): string {
  const [int, frac] = num.split('.');
  let out = '';
  if (int && int.length > 3) {
    const head = int.slice(0, -3);
    const tail = int.slice(-3);
    const grouped = head.replace(/\B(?=(\d{2})+(?!\d))/g, ',');
    out = `${grouped},${tail}`;
  } else {
    out = int ?? '0';
  }
  return frac ? `${out}.${frac}` : out;
}

/** ₹ with Indian grouping and a fixed number of decimals. */
export function inr(value: number, decimals = 2): string {
  const sign = value < 0 ? '-' : '';
  const abs = Math.abs(value).toFixed(decimals);
  return `${sign}₹${groupIndian(abs)}`;
}

/** Compact lakh/crore: ₹2.4L, ₹1.7Cr — used on chart axes. */
export function inrCompact(value: number): string {
  const sign = value < 0 ? '-' : '';
  const abs = Math.abs(value);
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(1)}Cr`;
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(0)}K`;
  return `${sign}₹${abs.toFixed(0)}`;
}

/** Signed percent with a fixed number of decimals: +2.37% / −0.45%. */
export function pct(value: number, decimals = 2, glyph = true): string {
  const sign = value > 0 ? (glyph ? '+' : '') : value < 0 ? '−' : '';
  return `${sign}${Math.abs(value).toFixed(decimals)}%`;
}

/** Signed amount with +/− glyph (R4.4: color is never the only encoding). */
export function signed(value: number, decimals = 2, prefix = '₹'): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${prefix}${groupIndian(Math.abs(value).toFixed(decimals))}`;
}

/** Uptime duration: 3.8h → "0D 3H 48M". */
export function duration(totalHours: number): string {
  const h = Math.max(0, Math.floor(totalHours));
  const d = Math.floor(h / 24);
  const rem = h % 24;
  const m = Math.round((totalHours - h) * 60);
  return `${d}D ${rem}H ${m}M`;
}

/** Cycle countdown mm:ss from a cycle period (seconds). */
export function countdown(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const mm = String(Math.floor(s / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

/** IST wall clock HH:MM:SS (+ optional ms). */
export function istTime(date = new Date(), withMs = false): string {
  const fmt = withMs ? 'HH:MM:SS.mmm' : 'HH:MM:SS';
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '00';
  let out = `${get('hour')}:${get('minute')}:${get('second')}`;
  if (withMs) {
    out += `.${String(date.getMilliseconds()).padStart(3, '0')}`;
  }
  void fmt;
  return out;
}

/** Short date label for chart axes: "APR 28" (RFC R11.3 — absolute time). */
export function shortDate(ts: number | string): string {
  const d = typeof ts === 'number' ? new Date(ts) : new Date(ts);
  return `${d.toLocaleString('en-GB', { month: 'short', timeZone: 'Asia/Kolkata' }).toUpperCase()} ${String(
    d.getDate(),
  ).padStart(2, '0')}`;
}

/** Compact number with thousands separators (no currency). */
export function num(value: number, decimals = 2): string {
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Format a price: >=1000 no decimals, >=1 two decimals, else 4. */
export function price(value: number): string {
  const abs = Math.abs(value);
  const decimals = abs >= 1000 ? 0 : abs >= 1 ? 2 : 4;
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

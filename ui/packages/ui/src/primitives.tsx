import type { ButtonHTMLAttributes, ReactNode } from 'react';

/* ---- Button (RFC §10.2: mono 12px uppercase, 0.06em, radius 4, no gradient) ---- */

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'danger-ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

const BTN: Record<ButtonVariant, React.CSSProperties> = {
  primary: { color: 'var(--text-inverse)', background: 'var(--signal-primary)', border: '1px solid var(--signal-primary)' },
  secondary: { color: 'var(--signal-primary)', background: 'transparent', border: '1px solid var(--signal-primary)' },
  ghost: { color: 'var(--signal-primary)', background: 'transparent', border: '1px solid transparent' },
  danger: { color: 'var(--text-primary)', background: 'var(--status-danger)', border: '1px solid var(--status-danger)' },
  'danger-ghost': { color: 'var(--status-danger)', background: 'transparent', border: '1px solid var(--status-danger)' },
};

const BTN_H: Record<ButtonSize, React.CSSProperties> = {
  sm: { height: 28, padding: '0 12px', fontSize: 11 },
  md: { height: 36, padding: '0 16px', fontSize: 12 },
  lg: { height: 44, padding: '0 20px', fontSize: 12 },
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
}

export function Button({ variant = 'secondary', size = 'md', children, style, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      style={{
        ...css(style),
        fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace",
        fontWeight: 600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        borderRadius: 4,
        cursor: 'pointer',
        transition: 'background 120ms, border-color 120ms, color 120ms, transform 120ms',
        ...BTN[variant],
        ...BTN_H[size],
      }}
    >
      {children}
    </button>
  );
}

/* ---- IconButton (RFC §15: inline SVG only, 24px grid, 1.5px stroke) ---- */

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  color?: string;
  children: ReactNode;
}

export function IconButton({ label, color = 'var(--text-secondary)', children, style, ...rest }: IconButtonProps) {
  return (
    <button
      aria-label={label}
      title={label}
      {...rest}
      style={{
        ...css(style),
        width: 36,
        height: 36,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'transparent',
        border: 'none',
        color,
        cursor: 'pointer',
        borderRadius: 4,
        transition: 'background 120ms, color 120ms',
      }}
    >
      {children}
    </button>
  );
}

/* ---- StatusDot (RFC §10.3: 8px circle, 2px ring, + 11px mono label) ---- */

export interface StatusDotProps {
  state: 'live' | 'up' | 'down' | 'warn' | 'danger' | 'info' | 'offline';
  label?: string;
  pulse?: boolean;
}

const DOT_COLOR: Record<StatusDotProps['state'], string> = {
  live: 'var(--status-live)',
  up: 'var(--status-up)',
  down: 'var(--status-down)',
  warn: 'var(--status-warn)',
  danger: 'var(--status-danger)',
  info: 'var(--status-info)',
  offline: 'var(--text-tertiary)',
};

export function StatusDot({ state, label, pulse }: StatusDotProps) {
  const color = DOT_COLOR[state];
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace", fontSize: 11, color: 'var(--text-secondary)', letterSpacing: '0.04em' }}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: color,
          boxShadow: `0 0 0 2px var(--surface-panel), 0 0 0 3px ${color}55`,
          animation: pulse ? 'kairoPulse 1.2s ease-in-out infinite' : undefined,
        }}
      />
      {label && <span style={{ textTransform: 'uppercase', fontWeight: 500 }}>{label}</span>}
    </span>
  );
}

/* ---- Badge (RFC §10.3: 18px min, mono 10px uppercase, radius 2) ---- */

export interface BadgeProps {
  color: string;
  children: ReactNode;
  title?: string;
}

export function Badge({ color, children, title }: BadgeProps) {
  return (
    <span
      title={title}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        minHeight: 18,
        padding: '1px 8px',
        fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace",
        fontSize: 10,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        borderRadius: 2,
        color,
        border: `1px solid ${color}44`,
        background: `${color}11`,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}

/* ---- Toggle (RFC §10.5: 36×20 track, 16px thumb, cyan on, always labeled) ---- */

export interface ToggleProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  disabled?: boolean;
}

export function Toggle({ checked, onChange, label, disabled }: ToggleProps) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        background: 'transparent',
        border: 'none',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace",
        fontSize: 11,
        letterSpacing: '0.04em',
        color: 'var(--text-secondary)',
        textTransform: 'uppercase',
      }}
    >
      <span style={{ width: 36, height: 20, borderRadius: 10, background: checked ? 'var(--signal-primary)' : 'var(--border-default)', border: '1px solid var(--border-default)', position: 'relative', transition: 'background 120ms' }}>
        <span
          style={{
            position: 'absolute',
            top: 2,
            left: checked ? 18 : 2,
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: checked ? 'var(--text-inverse)' : 'var(--text-secondary)',
            transition: 'left 120ms',
          }}
        />
      </span>
      {label}
    </button>
  );
}

/* ---- SegmentedControl (RFC §10.5) ---- */

export interface Segment<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedControlProps<T extends string> {
  segments: Segment<T>[];
  value: T;
  onChange: (v: T) => void;
  id?: string;
}

export function SegmentedControl<T extends string>({ segments, value, onChange, id }: SegmentedControlProps<T>) {
  return (
    <div
      role="tablist"
      aria-label={id}
      style={{ display: 'inline-flex', border: '1px solid var(--border-default)', borderRadius: 4, overflow: 'hidden', background: 'var(--surface-inset)' }}
    >
      {segments.map((s) => (
        <button
          key={s.value}
          role="tab"
          aria-selected={value === s.value}
          onClick={() => onChange(s.value)}
          style={{
            padding: '4px 10px',
            fontFamily: "var(--font-plex-mono), 'IBM Plex Mono',monospace",
            fontSize: 10,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            background: value === s.value ? 'rgba(0, 229, 255, 0.13)' : 'transparent',
            color: value === s.value ? 'var(--signal-primary)' : 'var(--text-tertiary)',
            border: 'none',
            borderRight: '1px solid var(--border-default)',
            cursor: 'pointer',
            transition: 'background 120ms, color 120ms',
          }}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}

function css(s: React.CSSProperties | undefined): React.CSSProperties {
  return s ?? {};
}

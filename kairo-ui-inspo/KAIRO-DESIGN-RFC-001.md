# KAIRO DESIGN RFC-001

**KAIRO — Autonomous AI Trading Operating System: Design Specification**
**Status:** Draft · **Category:** Standards Track · **Stream:** Design Systems
**Version:** v1.0.0 · **Date:** 2025 · **Maintainers:** KAIRO Design Systems Group
**Replaces:** All prior brand guideline PDFs (v0.x). This document is the single source of truth. Where previous assets conflict, this document wins.

---

## Abstract

This RFC defines the complete design architecture for KAIRO, an autonomous AI trading operating system. It is written for engineers and designers who will implement the product end-to-end without further consultation. It is not a brand guide. It contains no motivation, no aspirational copy, no stock imagery, and no decoration.

Every rule in this document is either **measurable** (a number, a token, a budget) or **mechanically checkable** (a lint rule, a test, a DOM assertion). If a rule cannot be enforced by a machine or verified by a measurement, it has been removed.

The visual language is a synthesis of four reference systems:
1. **Bloomberg Terminal** — density, information bandwidth, monospaced data, single-purpose function.
2. **Linear / Stripe** — precise interaction design, crisp borders, restrained color, obsessive state handling.
3. **Swiss editorial design** — grid discipline, typographic hierarchy, asymmetry as structure.
4. **Scientific / computational visualization** — every mark on screen is a data encoding. Nothing is painted for its own sake.

The governing principle is stated once here and repeated nowhere else:

> **Every pixel on screen must be derivable from a data field, a system state, or an explicit user interaction. If a pixel cannot be traced to one of these three sources, it is removed.**

---

## 1. Design Philosophy

### 1.1 Principles

| # | Principle | Meaning | Enforcement |
|---|-----------|---------|-------------|
| P1 | **Data before decoration** | Visual elements exist only to encode information. | Design review gate; no asset may enter the library without a data-source annotation. |
| P2 | **Determinism before drama** | Interaction and motion are mechanical, not theatrical. | Easing curves restricted to the Motion §14 set. |
| P3 | **Density is a feature** | Information bandwidth is the product. Whitespace is not a virtue; legibility is. | Density tiers in §6; content ratio check in QA. |
| P4 | **The machine is visible** | KAIRO shows its own internals: logs, latency, confidence, veto decisions. | Live terminal surfaces in dashboard §8. |
| P5 | **Risk is a first-class citizen** | Capital preservation outranks profit display in visual priority. | Hierarchy in §7; risk zone rules. |
| P6 | **Opacity is failure** | Any state the user cannot inspect is a bug. | Every async operation has a visible log line or status field. |
| P7 | **Autonomy with oversight** | The system acts; the human commands. Veto, not control. | "LLM VETO NOT CONTROL" is a persistent legal/political label on AI surfaces. |
| P8 | **Honesty over persuasion** | Numbers are never styled to flatter. PnL is not enlarged when positive. | Typographic scale for figures is state-invariant (§7.4). |

### 1.2 Rules

1. **R1.1 — The Three-Source Rule.** Every visible element must trace to: (a) a data field, (b) a system state, or (c) a user interaction. The trace must be reproducible by a reviewer. Decorations, filler illustrations, and "ambient" graphics are forbidden.
2. **R1.2 — No decorative gradients.** Gradients are permitted only as a data encoding (density, probability, regime) and only within the approved data-gradient ramp (§4.6).
3. **R1.3 — No glassmorphism, no neumorphism, no 3D bevels.** `backdrop-filter` is forbidden globally. See anti-patterns.
4. **R1.4 — The Terminal Default.** When uncertain between two layouts, choose the denser, more monospaced, more information-complete one.
5. **R1.5 — Zero-stock.** Stock photography, generic SaaS hero illustrations, and "people using laptops" imagery are forbidden in every touchpoint including marketing.

### 1.3 Measurements

- Content-to-chrome ratio on every dashboard view: ≥ 82% of viewport width carries data or controls.
- Decorative (non-informative) pixels per viewport: **0**. Measured via design review; no automated proxy.
- Information density target: ≥ 40 data fields visible on the default dashboard at 1440×900 without scrolling (§8).

### 1.4 Anti-patterns

- ❌ Glass cards, frosted panels, translucent navbars.
- ❌ Neon "cyberpunk" gratuitous glow on non-data elements.
- ❌ Gradient brand buttons.
- ❌ Illustrations of rockets, graphs going up, robots, brains, hands holding coins.
- ❌ "AI assistant" avatars, chat bubbles with sparkles, "thinking…" dot animations.
- ❌ Crypto-culture clichés: lambo, moon, rocket, diamond hands, meme animals.

### 1.5 QA checklist (Section 1)

- [ ] Every component in the library has a `data-source` field in its docs.
- [ ] Zero `backdrop-filter` occurrences in the codebase (grep check).
- [ ] Zero raster stock images in the repo (`*.jpg|png` under `/public/images` must be data-derived).
- [ ] Landing page contains no stock photography.

---

## 2. Brand Identity

### 2.1 Positioning

KAIRO is a **safety-first autonomous AI trading operating system**. It combines deterministic, rule-bound strategies with AI oversight. It trades 24/7; the human audits, configures, and can kill everything at any instant.

Category: AI Crypto Trading System · Founded: 2024 · Founder: Devan · HQ: India · Site: kairo.run.

### 2.2 Brand pillars

| Pillar | Definition | Product manifestation |
|--------|-----------|----------------------|
| **SAFETY-FIRST** | Hardcoded rules. Safety gate always on. No overrides. | Kill switch; risk engine; drawdown limits; veto log. |
| **DATA-DRIVEN** | Every decision backed by data, not emotion. | Regime map; signal DNA; all metrics sourced. |
| **AUTONOMOUS** | Trades 24/7 so the trader doesn't have to. | Live mode; cycle loop; watchdog. |
| **TRANSPARENT** | Everything is logged, explainable, auditable. | Terminal log; LLM veto log; full audit trail. |
| **RELENTLESS** | Always optimizing, learning, improving. | Strategy performance tables; self-tuning loops. |
| **INDIA-AWARE** | Built for Indian traders: taxes, compliance, local context. | ₹ formatting, tax module, INR-first figures, IST timestamps. |

### 2.3 Voice

| Attribute | Meaning | Copy example |
|-----------|---------|--------------|
| PRECISE | Exact numbers, no approximation words | "Drawdown −3.21%" not "slightly down" |
| CONFIDENT | Declarative, no hedging | "Cycle complete" not "cycle seems done" |
| TRANSPARENT | States the mechanism | "LLM veto: confidence 84% < 90% threshold" |
| EMPOWERING | Gives the user agency | "Kill switch armed. All positions liquidated." |

### 2.4 Taglines

- Primary: **TRADE. ANALYZE. OPTIMIZE. REPEAT.**
- Alt (product): **AUTONOMOUS TRADING. HUMAN OVERSIGHT. MAXIMUM EDGE.**
- Safety (product, always shown): **SAFETY GATE ALWAYS ON**

### 2.5 Measurements / constraints

- Tagline casing: always sentence or all-caps as specified; never Title Case.
- The word "KAIRO" in text always appears as `KAIRO` (all caps) in product UI; marketing copy may use `Kairo` in prose.

---

## 3. Logo System

### 3.1 The mark

The KAIRO mark is a **halftone sphere / dot-matrix globe** split down the middle by a vertical gap, constructed from data points forming a wave of probability and market flow. It is rendered in the dot-matrix display face (KAIRO DOT). Construction is on a modular grid of data points; the implied K is formed by the wave/gap ("K + WAVE DATA FLOW").

### 3.2 Construction

- The mark lives on a 48×48 unit grid at 1× (base).
- The gap (the "K") is 4 units wide, centered vertically.
- Dot pitch: 2 units on-center.
- Radius: 24 units; the wave inside follows a sine function with a period of 8 units, amplitude 6 units — it is generated, not drawn by hand (source file is an SVG generated from these parameters).

### 3.3 Clear space & minimum sizes

- Clear space = height of the `0` glyph in the adjacent wordmark.
- Minimum render sizes: 16px (favicon-equivalent contexts), 24px (UI nav), 32px (headers), 96px (marketing lockups).
- Below 16px, replace the full mark with the plain wordmark or the `K` monogram.

### 3.4 Lockups

| Lockup | Use |
|--------|-----|
| Horizontal | Product chrome, docs headers, marketing nav |
| Stacked | App icon, terminal splash, merch |
| Icon (mark only) | Favicon, notifications, OS shortcut |
| Wordmark | Dense UI where the mark is redundant |

Wordmark tagline treatment: `KAIRO` in KAIRO DOT, with `AUTONOMOUS AI TRADING SYSTEM` in IBM Plex Mono, letter-spaced 0.12em, at 40% of the wordmark size.

### 3.5 Usage rules (enforceable)

- ✅ Always use approved files (single source: this repo, `/brand/logo/`).
- ✅ Preserve aspect ratio; never stretch.
- ✅ Use the monochrome white version on dark backgrounds; never place the color version on light.
- ✅ Maintain clear space per §3.3.
- ❌ Never recolor (tokens fixed in §4).
- ❌ Never add effects: glow, gradient fills inside the mark, shadows, outlines.
- ❌ Never rotate or mirror.
- ❌ Never place on photography.

### 3.6 Do / Don't

- **Do** render the mark in `--color-mist` on `--color-void` for terminal contexts.
- **Do** use the cyan variant (`--color-cyan`) only for "live/system active" states (e.g., LIVE badge pairing).
- **Don't** animate the mark except during system boot/splash, and only with the boot sequence in §14.4.

---

## 4. Color System

### 4.1 Canonization note

Prior assets contain conflicting hex values. This RFC canonizes one set. **Use only the values in this table.** All prior values are retired.

### 4.2 Primitives (raw palette)

| Token | Value | Name | Role |
|-------|-------|------|------|
| `--kairo-void` | `#08080B` | VOID | Absolute background. Base of everything. |
| `--kairo-charcoal` | `#0B0F14` | CHARCOAL | Deep inset surfaces, code wells |
| `--kairo-steel` | `#12141B` | STEEL | Panel surfaces, cards, sidebars |
| `--kairo-slate` | `#1E232B` | SLATE | Raised surfaces, hover states |
| `--kairo-hairline` | `#262B34` | HAIRLINE | 1px borders, grid lines (UI) |
| `--kairo-mist` | `#E6E6E6` | MIST | Primary text, chart strokes |
| `--kairo-silver` | `#9AA3B2` | SILVER | Secondary text, axis labels |
| `--kairo-mute` | `#5C6470` | MUTE | Tertiary, disabled, tick marks |
| `--kairo-lime` | `#39FF14` | LIME | System healthy, gains, action confirm |
| `--kairo-cyan` | `#00E5FF` | CYAN | Active data, selection, primary action |
| `--kairo-violet` | `#7C4DFF` | VIOLET | AI/probabilistic output, LLM surfaces |
| `--kairo-blue` | `#2962FF` | BLUE | Deterministic signal, links, info |
| `--kairo-amber` | `#FFB800` | AMBER | Warning, limits approaching |
| `--kairo-coral` | `#FF5C7A` | CORAL | Risk, danger, losses, kill states |
| `--kairo-ink` | `#FFFFFF` | INK | Pure white, emergency emphasis |

### 4.3 Semantic tokens

Primitives are **never referenced directly in components.** Components consume semantic tokens only.

| Token | Value | Meaning |
|-------|-------|---------|
| `--surface-base` | void | App background |
| `--surface-panel` | steel | Cards, panels |
| `--surface-raised` | slate | Menus, popovers, focused panels |
| `--surface-inset` | charcoal | Code wells, terminal logs, chart plot areas |
| `--border-default` | hairline | Default 1px borders |
| `--border-strong` | silver | Emphasized borders, focus rings |
| `--text-primary` | mist | Primary content |
| `--text-secondary` | silver | Secondary content, axis |
| `--text-tertiary` | mute | Captions, disabled, tick labels |
| `--text-inverse` | void | Text on light/neon surfaces |
| `--status-live` | lime | Healthy, online, live |
| `--status-up` | lime | Gains, buy pressure, positive PnL |
| `--status-down` | coral | Losses, sell pressure, negative PnL |
| `--status-warn` | amber | Approaching limits, degraded |
| `--status-danger` | coral | Breach, kill, critical |
| `--status-info` | cyan | Active data, in-progress |
| `--signal-primary` | cyan | Primary deterministic signal |
| `--signal-secondary` | blue | Secondary signal, info |
| `--ai-primary` | violet | AI/probabilistic output |
| `--ai-dim` | violet @ 60% | AI secondary, confidence low |
| `--action-primary` | cyan | Primary buttons, links |
| `--action-hover` | lime | Confirmed/armed actions |
| `--focus-ring` | cyan | Keyboard focus |

### 4.4 Rules

1. **R4.1 — Dark foundation only.** The light theme is a non-goal. KAIRO is terminal software.
2. **R4.2 — Accent budget.** Max **3 accent colors per viewport** (excluding semantic status colors that are inherently present). Counted in design QA.
3. **R4.3 — Accent semantics are fixed.** Cyan is never "loss"; coral is never "gain". A swap is a breaking change.
4. **R4.4 — Up/down is never color-only.** Every up/down encoding must pair color with a glyph (`▲`/`▼` or `+`/`−`). See §17.
5. **R4.5 — Neon on void only.** Neon primaries render on void/steel/charcoal. On mist backgrounds, only use them as small accents with `--text-inverse` pairing; this combination is rare and must be approved.
6. **R4.6 — Opacity for hierarchy, not decoration.** Allowed alpha steps: `100%, 80%, 60%, 40%, 24%, 12%`. No arbitrary alpha.

### 4.5 Data gradient

The KAIRO **data gradient** encodes magnitude/regime and is the only sanctioned multi-stop ramp: `void → lime → cyan → violet → amber`, rendered as discrete stepped bands (not a smooth blend) with dot-pitch indicators. Used for: regime maps, liquidity density, probability fields, heatmaps. Never used for buttons, text, or icons.

### 4.6 Accessibility (color)

- All text-on-surface pairs meet WCAG 2.2 AA (≥4.5:1 body, ≥3:1 large). Verified pairs: mist/void 17.4:1; silver/void 7.9:1; mute/void 4.6:1; lime/void 15.9:1; cyan/void 10.1:1; violet/void 6.8:1; coral/void 5.9:1; amber/void 11.5:1.
- Charts must be legible under deuteranopia and tritanopia simulation (QA step).
- Never rely on lime/coral alone; always pair with shape/glyph (§R4.4).

### 4.7 Do / Don't

- **Do** use violet for anything the LLM generated.
- **Don't** use violet for deterministic metrics.
- **Do** use amber before coral: amber = approaching limit, coral = breached.
- **Don't** add drop shadows to colored elements; use 1px borders and alpha layers instead.

---

## 5. Typography

### 5.1 Typefaces

| Face | Role | Source |
|------|------|--------|
| **KAIRO DOT** | Display, wordmark, hero numerals, splash | Custom pixel/dot-matrix display font (in-repo: `/brand/fonts/kairo-dot.woff2`). Dot-matrix 5×7 grid, designed to match the mark's dot language. |
| **IBM Plex Mono** | All data, figures, terminal, tables, labels, charts | Open source. Primary display + data face per prior guidelines. |
| **Inter** | UI chrome, body, prose, marketing copy | Variable font, Regular 400 / Medium 500 / SemiBold 600 only. |

### 5.2 Type scale (fluid, modular)

Base unit 1rem = 16px. Scale ratio: 1.25 (major third) for UI; 1.0 (mono, integer sizes) for data.

| Token | Size | Line-height | Face | Use |
|-------|------|-------------|------|-----|
| `--text-2xs` | 10px | 14px | Mono | Table meta, timestamps, micro labels |
| `--text-xs` | 11px | 16px | Mono | Dense table cells, axis labels |
| `--text-sm` | 12px | 18px | Mono | Default data, table body |
| `--text-base` | 13px | 20px | Inter | UI body, secondary copy |
| `--text-md` | 14px | 22px | Mono | Key figures, stat values |
| `--text-lg` | 18px | 26px | Mono | Card lead figures, dashboard metrics |
| `--text-xl` | 24px | 32px | Mono | Hero metrics (equity, risk headline) |
| `--text-2xl` | 36px | 44px | Mono | Splash, empty-state headline |
| `--text-display` | 48–72px | 0.95em | KAIRO DOT | Wordmark, landing hero |

**Data-size invariance (R5.1):** The font size of a figure must not change with its sign or magnitude. `+48.62%` and `−3.21%` render at the same size. This is a mechanical check (unit test on figure components).

### 5.3 Rules

1. **R5.2 — Figures are monospaced, always.** Any number that can change (price, PnL, size, time) uses IBM Plex Mono with `font-variant-numeric: tabular-nums`. No proportional digits in data.
2. **R5.3 — Tracking.** Mono labels: `letter-spacing: 0.04em` uppercase micro-labels; KAIRO DOT: `0.08em`; Inter: `-0.01em` at sizes ≥ 14px.
3. **R5.4 — Case.** UI labels are UPPERCASE mono micro-labels (11px, 0.06em tracking) or sentence-case Inter. Never all-caps Inter.
4. **R5.5 — Currency.** INR-first formatting: `₹2,48,750.32` (Indian digit grouping: lakh/crore style `2,48,750`). Percent with sign: `+2.37%`. Times: `HH:MM:SS` local + `IST` label; durations `12D 18H 42M`.
5. **R5.6 — Line length.** Prose (landing): 45–75ch. Data cells: no wrap by default; truncate with `…` or horizontal scroll. Never truncate a PnL or a price with ellipsis.

### 5.4 Engineering notes

- Self-host the three fonts; preload the two webfonts used in first paint (`KAIRO DOT` for splash/wordmark, `IBM Plex Mono` for data). Inter loads async with `font-display: swap` fallback to system UI.
- Total font payload budget: ≤ 180KB woff2 (all weights actually used; do not ship unused weights).

### 5.5 Do / Don't

- **Do** set every figure in Mono with tabular numerals.
- **Don't** use KAIRO DOT for body text or anything ≥ 2 words except the wordmark/tagline.
- **Don't** italicize mono. There is no italic in the data voice.

---

## 6. Grid & Spacing

### 6.1 System

- **Base grid:** 8px. **Micro grid:** 4px (used only inside components and tables). Never 1, 2, 3, 5, 6, 7, 9… px values except hairline borders (1px) and specific chart strokes (§11.4).
- **Layout grid:** 12 columns on ≥1200px viewports (product), 12 columns on marketing, 4 columns < 768px. Column gap 16px; page gutter 24px (product), 48px (marketing).

### 6.2 Spacing scale

| Token | Value | Use |
|-------|-------|-----|
| `--space-1` | 4px | Micro gaps inside cells, icon-to-glyph |
| `--space-2` | 8px | Component internal padding (compact) |
| `--space-3` | 12px | Cell padding, table row padding |
| `--space-4` | 16px | Card padding, gap between widgets |
| `--space-5` | 24px | Section gaps, drawer padding |
| `--space-6` | 32px | Major section separation |
| `--space-7` | 48px | Page-level margins (marketing) |
| `--space-8` | 64px | Terminal footer / hero spacing |

### 6.3 Density tiers

Three system-wide density tiers, switchable (persisted per user):

| Tier | Base unit | Table row | Card padding | Font (data) |
|------|-----------|-----------|--------------|-------------|
| COMFORTABLE | 8px | 40px | 20px | 13px |
| DENSE (default) | 8px | 32px | 16px | 12px |
| COMPACT | 8px | 26px | 12px | 11px |

Default is DENSE. COMPACT is offered in Settings; it must not break the QA checklist.

### 6.4 Rules

- **R6.1** — All spacing values resolve to the scale. Zero exceptions in components (lint-enforced via design tokens in Tailwind).
- **R6.2** — Panel separation uses space + 1px hairline border. Never shadow-based separation.
- **R6.3** — The chart plot area is inset 12px from panel edges; axis labels live in the remaining gutter.
- **R6.4** — The terminal/log surfaces break the spacing grid vertically (line-height driven) but not horizontally.

### 6.5 QA

- [ ] No arbitrary px values in component styles (grep for `p-[3px]`, `mt-[7px]`, etc.).
- [ ] Density switch produces no overflow at 1280×800 in any view.

---

## 7. Information Hierarchy

### 7.1 Priority order (canonical)

1. **System & exchange health** — is the machine alive, is the feed live, is the safety gate armed?
2. **Risk state** — drawdown, VaR, daily limit proximity, kill state.
3. **Open positions & orders** — what is the system doing right now?
4. **PnL & performance** — outcome metrics.

This is the institutional inversion of consumer dashboards: **capital preservation precedes profit display** (P5). PnL is deliberately not the biggest number on the screen.

### 7.2 Hierarchy levels

| Level | Encoding | Examples |
|-------|----------|----------|
| L0 — Global state | Top status bar, always visible, full-opacity neon dot + label | LIVE / SAFE / RISK |
| L1 — Primary metric | Largest mono figure on a card, 24–36px, label above in 11px mono uppercase | Equity, Drawdown, VaR |
| L2 — Secondary data | 14–18px mono figures, silver/mist | Latency, Sharpe, Volatility |
| L3 — Tabular detail | 11–12px mono, dense rows | Positions, trades, logs |
| L4 — Ambient/system | 10–11px, mute, mono | Timestamps, cycle counts, version |

### 7.3 Rules

- **R7.1** — L0 status is always visible; it cannot scroll away, be minimized, or be hidden by a modal.
- **R7.2** — Kill switch affordance is always reachable (≤ 1 interaction) from any screen, including onboarding.
- **R7.3** — Risk values that breach a configured threshold escalate from silver→amber→coral *and* gain a glyph/label (`LIMIT 92%`), never color alone.
- **R7.4** — One L1 metric per card. A card with two 24px figures is a layout bug.

### 7.4 Anti-patterns

- ❌ Animating PnL numbers (count-up) on every tick. Count-up only on page load or manual refresh, ≤ 300ms.
- ❌ Making profit bigger/brighter than loss (R5.1).
- ❌ Burying risk behind a tab or a "more" menu.

---

## 8. Dashboard Architecture

### 8.1 Zone model (desktop, 1440×900 reference)

```
┌──────────────────────────────────────────────────────────────────────┐
│ Z0 TOP STATUS BAR        KAIRO · ●LIVE · 02:14 · 12D 18H 42M · RISK │
├──────┬───────────────────────────────────────────────────────────────┤
│ Z1   │  Z2 WIDGET GRID (12-col, 3 rows)                             │
│ NAV  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                      │
│ 64px │  │ EQUITY   │ │ ALLOC    │ │ SYSTEM   │                      │
│      │  └──────────┘ └──────────┘ └──────────┘                      │
│ icons│  ┌───────────────────┐ ┌──────────────────┐                  │
│ 48px │  │ POSITIONS (3/5)   │ │ RISK METRICS     │                  │
│      │  └───────────────────┘ └──────────────────┘                  │
│      │  ┌──────────┐ ┌──────────┐ ┌──────────┐                      │
│      │  │ RECENT   │ │ LLM VETO │ │ NEWS &   │                      │
│      │  │ TRADES   │ │ LOG      │ │ SENTIMENT│                      │
│      │  └──────────┘ └──────────┘ └──────────┘                      │
├──────┴───────────────────────────────────────────────────────────────┤
│ Z3 TICKER/LOG    12:26:44 [INFO] Cycle complete. Next in 02:14      │
└──────────────────────────────────────────────────────────────────────┘
```

- **Z0:** global state (§7 L0). Height 40px. Contents: wordmark (16px), status cluster, cycle countdown, uptime, mode, risk profile, clock, kill switch slot.
- **Z1:** 64px icon rail. Icons per §15, 24px glyphs, 48px hit areas. Active item gets a 2px left indicator in `--signal-primary`. Tooltips on hover/focus. Collapsible to 48px.
- **Z2:** widget grid. 12 columns, 16px gaps, 3 rows. Widgets are draggable/reorderable in Edit Mode; layout persists server-side per user.
- **Z3:** 28px log ticker. Live `[INFO]`/`[WARN]`/`[ERROR]` lines, mono 11px, `--surface-inset` background. Scrolls horizontally (latest on right) or vertically per user preference; default vertical, newest at bottom, auto-scroll unless user scrolls up (then pause auto-scroll, resume on "live" button).

### 8.2 Widget taxonomy

| Widget | Data source | Ref |
|--------|-------------|-----|
| Equity Curve | Portfolio equity series | §11.5 |
| Portfolio Allocation | Holdings | §11.10 |
| System Health | Exchange/LLM/feed/watchdog states | §8.3 |
| Open Positions | Order manager | table spec §10.6 |
| Strategy Performance | Strategy engine | §11.5 |
| Risk Metrics | Risk engine | §11.7 |
| Recent Trades | Trade journal | table spec |
| LLM Veto Log | LLM oversight | §12.4 |
| News & Sentiment | Sentiment pipeline | §11.9 |
| Market Regime | Regime classifier | §11.8 |
| Order Flow | Exchange depth | §11.11 |
| Signal DNA | Strategy signals | §11.12 |
| Liquidation Map | Liquidity model | §11.13 |
| Strategy Fingerprint | Backtest/equity per strategy | §11.12 |

### 8.3 System health widget spec

Rows: `EXCHANGE BYBIT`, `LLM ENGINE OLLAMA (QWEN 8B)`, `DATA FEED`, `TELEGRAM`, `WATCHDOG`. Each row: name (mono 11px, silver), status dot + `ONLINE`/`DEGRADED`/`OFFLINE` (lime/amber/coral), latency in ms. Update at 5Hz (§18). Any OFFLINE row escalates Z0 status and logs to Z3.

### 8.4 Rules

- **R8.1** — Default dashboard renders ≥ 40 data fields at 1440×900 without scroll (§1.3).
- **R8.2** — Every widget must have a defined empty state, loading state, and error state (§10.8).
- **R8.3** — Edit Mode is explicit (toggle in Z0); no accidental drag. While editing, live data continues but widgets show `--border-strong` dashed outline.
- **R8.4** — A widget showing stale data (>2× its refresh period) gets a `STALE` tag in amber; data older than 10× period turns the tag coral and the panel dims to 60%.

### 8.5 Engineering notes

- Widget grid uses CSS Grid; drag-and-drop via a library with pointer-event throttling; layout state normalized to a JSON schema and persisted.
- Z3 log is a virtualized list (only visible lines mounted).

---

## 9. Landing Page

### 9.1 Principle

The landing page is a **live demo of the terminal**, not a marketing site. It must load fast, show real data where possible (public market data), and never use stock imagery.

### 9.2 Structure

1. **Hero:** KAIRO wordmark in KAIRO DOT (72px), tagline, CTA `LAUNCH TERMINAL`. Behind it: a live-rendered dot-matrix equity/regime canvas (data-derived; falls back to static SVG on slow networks).
2. **Live proof strip:** 3–5 real-time metrics pulled from public feeds (BTC price, funding, fear & greed) rendered in terminal styling — proves "the machine is real".
3. **Product sections (3):** Safety Gate / Autonomy / Transparency — each with a real product screenshot (from the actual app, not mockups) and mono captions.
4. **Terminal embed:** a read-only, reduced demo of the dashboard (equity curve + system health) rendered client-side.
5. **Footer:** wordmark, pillars, `SAFETY GATE ALWAYS ON`, kairo.run, v1.0.0.

### 9.3 Rules

- **R9.1** — No stock photos, no gradients-as-decoration, no glass.
- **R9.2** — Screenshots must be generated from the product at a defined viewport (1440×900), not hand-painted.
- **R9.3** — All marketing claims must reference a product surface: e.g., "LLM Veto Log" links to docs showing the feature.
- **R9.4** — Landing is fully responsive; the hero canvas is dropped below 768px (static wordmark only) to protect mobile LCP.

### 9.4 Performance

- LCP ≤ 800ms on mid-tier mobile (4G); hero canvas lazy-loaded after LCP; fonts per §5.4.

---

## 10. Component Library

### 10.1 Inventory (canonical set — no new components without RFC)

Primitives: `Button`, `IconButton`, `Badge`, `StatusDot`, `Tag`, `Tooltip`, `Popover`, `Input`, `Select`, `SegmentedControl`, `Toggle`, `Checkbox`, `Radio`, `Slider`, `Table`, `DataCell`, `Sparkline`, `Tabs`, `Breadcrumb`, `Modal`, `Drawer`, `Toast`, `CommandPalette`, `EmptyState`, `Skeleton`, `TerminalLog`, `MetricCard`, `KillSwitch`, `Countdown`.

Composite: `MetricCard` (label + figure + delta + sparkline), `StatusRow`, `DataTable` (sortable, virtualized), `ChartPanel` (chart + toolbar + legend), `LogViewer`, `OnboardingStepper`, `RiskGauge`.

### 10.2 Button

| Prop | Spec |
|------|------|
| Variants | `primary` (cyan fill, void text), `secondary` (void fill, cyan border), `ghost` (void, cyan text), `danger` (coral fill, white text), `danger-ghost` |
| Sizes | `sm` 28px / `md` 36px / `lg` 44px; heights on 4px grid |
| States | default, hover (+1 step lighter border/bg), active (translateY(1px)), focus-visible (2px cyan ring, 2px offset), disabled (mute, 40% opacity, `not-allowed`), loading (spinner + label, disable pointer) |
| Radius | 4px (product), 6px (marketing) |
| Typography | Mono 12px uppercase, 0.06em tracking, `md`+ padding 16×12 |

Primary CTA never uses gradient. Confirmations: destructive buttons require a confirmation modal or a two-step hold (kill switch uses hold-to-arm, §10.13).

### 10.3 Badge / StatusDot

- `StatusDot`: 8px circle, 2px ring in `--surface-panel` for contrast, + 11px mono label. States: live/up/down/warn/danger/info/offline.
- `Badge`: 18px min-height, mono 10px uppercase, 0.08em tracking, radius 2px. Variants map 1:1 to semantic status tokens (§4.3). Badges never animate; pulse is reserved for L0 kill/risk escalation only (≤ 3 pulses, then steady).

### 10.4 Tooltip

- Appear ≤ 80ms delay, dismiss ≤ 120ms after pointer leave, follow cursor with 8px offset, max width 260px, mono 11px, `--surface-raised` bg, 1px hairline border, 2px radius. Keyboard-focusable triggers show tooltips on focus too. No tooltip on hover-critical data (§7.3: risk values are never tooltip-only).

### 10.5 Input / Select / Toggle

- Inputs: 36px height, 1px hairline border, 4px radius, focus ring per a11y, mono for numeric fields, error state: coral border + message + icon, `aria-describedby`.
- Select: native-ish custom popover; options list in `--surface-raised`.
- Toggle: 36×20px track, 16px thumb, cyan when on; always labeled (not icon-only).

### 10.6 Table spec (canonical)

- Row height: density tier (§6.3). Cells: mono 11–12px. Headers: 10px mono uppercase, mute, sticky within scroll container.
- Alignment: numbers right-aligned with tabular nums; pairs/symbols left; side `LONG`/`SHORT` as colored badges (lime/coral) + glyph.
- P/L cells: signed, color + `+`/`−` (R4.4).
- Row hover: `--surface-raised` overlay (8% alpha), no full-row border change.
- Selection: 2px left indicator + row bg 12% cyan.
- Sortable columns: header shows `▲/▼` glyph. Virtualized beyond 50 rows (see §18).
- `aria-sort`, `role="grid"` semantics with full keyboard navigation.

### 10.7 Modal / Drawer

- Modal: 480px default, 640px max, centered, 2px radius, 1px border, scrim = void @ 72%. Focus trapped, `Esc` closes, `role="dialog"`, `aria-modal`. No animation > 150ms.
- Drawer: 360px right rail for inspector panes; slides 150ms linear; scrim optional; used for position detail, LLM reasoning view, settings.

### 10.8 Empty / loading / error states (all components)

| State | Spec |
|-------|------|
| Empty | Icon (mute) + 12px mono title + 12px Inter body + optional primary CTA. No illustrations. |
| Loading | Skeleton: void panels with 8% mist shimmer blocks, linear 900ms loop, `prefers-reduced-motion` → static. |
| Error | Coral icon + title + message + `RETRY` ghost button + error code in mono (`E-1024`). Log line in Z3. |

### 10.9 Kill switch (critical component)

- Placement: Z0 slot + reachable from any screen via `Cmd/Ctrl+K` then type "kill" (command palette).
- Interaction: hold-to-arm (1.2s) → confirmation modal with typed risk acknowledgment (`TYPE "CONFIRM"`), then execute; logs every step to Z3.
- Visual: coral, `danger` variant, no decorative glow; armed state = solid coral + `ARMED` label; never animates except the hold progress ring (linear).
- a11y: full keyboard operable; focus order: button → confirm field → execute.
- Engineering: executes a server-side idempotent `POST /v1/system/kill`; UI reflects server state only (no optimistic "killed" state).

### 10.10 Command palette

`Cmd/Ctrl+K` globally. Mono 13px input, results in mono, filter-as-you-type, arrow-key nav, `aria-activedescendant`. Actions: navigate, toggle density, arm risk profiles, kill, search positions/strategies. Latency budget: first keystroke result ≤ 50ms.

### 10.11 Anti-patterns (components)

- ❌ Skeletons that "pop" layout height; use fixed skeleton dimensions per widget.
- ❌ Toast stacking beyond 3; replace oldest.
- ❌ Buttons with icon-only without `aria-label`.
- ❌ Tables that re-render all rows on a 5Hz tick (must virtualize + diff).

---

## 11. Charts & Financial Visualization

### 11.1 Rendering pipeline (canonical)

| Layer | Technology | Budget |
|-------|-----------|--------|
| High-density series (candles, tick, regime map, liquidation map, order flow) | **WebGL** (regl/three minimal) | 500k points @ 60fps, < 100MB heap |
| Interaction & axes (crosshair, gridlines, labels, tooltips) | **SVG** | ≤ 500 nodes per chart |
| Sparklines & tiny static series | **Canvas2D** | ≤ 2k points, drawn once per data change |

Ingest/decouple rule (R11.1): data ingestion at 20Hz (50ms) from WebSocket; rendering batched at 5Hz (200ms). Never re-render on every message. Frame budget: 16.6ms; if a frame exceeds 8ms of JS time, drop non-critical series (sparklines first, then volume, then candles), never the crosshair.

### 11.2 Chart anatomy (canonical)

```
[ Title (11px mono uppercase)          [Δ +2.37%]  [7D|30D|90D|ALL] ]
[ subtitle/period                      [legend chips]               ]
┌─────────────────────────────────────────────────────────────────┐
│ (plot area: inset 12px; bg = surface-inset)                     │
│ grid: horizontal 4 levels, vertical 8 levels, hairline 24%      │
│ axis labels: 10px mono mute, outside plot                       │
│ crosshair: 1px mist 40%, snap-to-data, value readout tooltip    │
└─────────────────────────────────────────────────────────────────┘
[ footer: source, as-of timestamp (mono 10px mute)               ]
```

- Every chart has an **as-of timestamp** (`AS OF 12:26:46.042 IST`) — freshness is a data point.
- Every chart has a footer source line when data is external (exchange, feed).

### 11.3 Rules

- **R11.2** — Y-axis always starts at meaningful zero or at data-min; never truncate to exaggerate. If truncated, show a `//` break glyph.
- **R11.3** — Time axis always absolute: `APR 28`, `04/28 12:00`, or `12:26:46`. No relative time on axes.
- **R11.4** — Line weight: 1.5px for primary series; 1px secondary; 0.5px only for grid. Candle width ≥ 2px at min zoom.
- **R11.5** — Colors on a chart follow the semantic map (§4.3); a chart must come with a legend if it uses >1 accent.
- **R11.6** — Dot-matrix rendering option: series may render as dot grids (data-density encoding) — dots 2px, pitch 4px — as a user-selectable theme in Settings (`RENDER: LINE | DOTS`). Default LINE.

### 11.4 Stroke/geometry constants

- Crosshair: 1px, mist 40%; snap radius 8px.
- Grid: 1px, hairline 24% alpha; show horizontal majors only on zoomed candle charts; suppress grid on dot-matrix themes.
- Chart corner radius: 0. Plot area is square-cornered. No rounded chart panels.

### 11.5 Equity curve

- Primary series: mist 1.5px line; filled area below at cyan 8% alpha (data density, not decoration).
- Baseline: void. Reference markers: drawdown periods marked with coral 12% alpha bands under the curve (drawdown is data, encoded as regions).
- Toggles: 7D / 30D / 90D / ALL; delta chip `+48.62%`.
- Max drawdown label at its local minimum with a `▼` anchor.

### 11.6 Candles / price

- Body 1px stroke, fill: up=lime, down=coral (with glyph convention in legends); wick 1px same color.
- Volume sub-pane: bars 40% alpha, same up/down color.
- Zoom: wheel + pinch; pan: drag; keyboard `←→` steps candle; `+/-` zoom. Crosshair readout shows O/H/L/C + volume + Δ%.

### 11.7 Risk gauges

- **Drawdown / VaR / Daily limit:** presented as mono figures (L1) + a horizontal bar (limit meter). Meter: track hairline, fill violet for VaR, amber→coral as it approaches configured threshold; threshold tick at 100%. Numeric always visible (never meter-only).
- **Risk profile:** `BALANCED` label + tag in Z0.

### 11.8 Regime map

- World map rendered as dot-matrix (grid of dots, 4px pitch, states: trending/volatile/liquid encoded via the data gradient §4.5). Dots carry market-regime color; no geographic fidelity beyond recognizable continents.
- Legend: TRENDING (cyan), VOLATILE (amber), LIQUID (lime), ILLIQUID (mute).

### 11.9 Sentiment

- Bi-directional bar chart: positive bars above zero (cyan), negative below (coral); bar width 8px, gap 4px; score dial `72/100` + `BULLISH` label with `▲` glyph.

### 11.10 Allocation

- Horizontal stacked bar, segments colored by asset (fixed map: BTC=blue, ETH=lime, SOL=amber, BNB=coral, OTHERS=mist) with percent labels inside/outside per width (label if segment ≥ 8% width). Also renderable as treemap for >6 assets.

### 11.11 Order flow

- Depth/heatmap: horizontal dispersion of buy (cyan) vs sell (coral) pressure dots at price levels; imbalance readout `+24% BUY` with glyph. Live shifting at 5Hz.

### 11.12 Signal DNA / strategy fingerprint

- Signal DNA: vertical wave of mono bars (dot-matrix), height = signal strength, colored by type (BREAKOUT=cyan, MA CROSS=lime, BOLL REVERT=violet); footer: `SIGNAL STRENGTH 84% · TYPE BREAKOUT · TF 4H`.
- Strategy fingerprint: per-strategy equity sparkline + win rate + profit factor table; sparkline color = strategy identity (stable map, not semantic).

### 11.13 Liquidation map

- Dot-cluster heat map of predicted liquidation levels; intensity via data gradient (void→amber→coral), clusters labeled with count; `SWEEP LIKELIHOOD 68%` L1 figure + amber badge.

### 11.14 Accessibility (charts)

- Every chart has a screen-reader table equivalent (hidden but real `<table>` or `aria-label` with summary stats).
- Color never sole encoding: add glyphs, patterns (dots/dashes), or direct labels.
- Keyboard: charts are focusable, crosshair navigable with arrows, readout announced via `aria-live="polite"` throttled to 1Hz.

### 11.15 QA (charts)

- [ ] Crosshair readout matches data at cursor (unit test on snapped value).
- [ ] Y-axis never misleadingly truncated (lint/visual check).
- [ ] 500k-point WebGL fixture renders at 60fps (automated perf test).
- [ ] All chart colors from token set; no raw hex in chart code.

---

## 12. AI Visualization

### 12.1 Principles

1. **The LLM is a math engine, not a person.** No avatars, chat bubbles, "thinking" dots, or sparkles.
2. **Show the decision, not the personality.** KAIRO renders LLM outputs as structured, inspectable artifacts: confidence, reasoning trace, veto decision, provenance.
3. **LLM VETO NOT CONTROL.** The model proposes; the safety engine disposes. This is a persistent label on all AI surfaces.

### 12.2 Confidence encoding

- Confidence is displayed as a calibrated figure with uncertainty: `84% ± 1.2%` (mono), never as a vague "HIGH/MEDIUM/LOW" alone.
- Confidence meter: 1px-thin horizontal bar (violet), tick at the decision threshold (e.g., 90%), current value dot. Below-threshold values render the bar amber and the label `BELOW THRESHOLD`.
- Confidence is never rendered as a circular gauge with glow; no "AI brain" visuals.

### 12.3 LLM Insight card

- Header: `LLM INSIGHT` + source (`OLLAMA/QWEN 8B`) + latency.
- Body: the model's structured output rendered as mono text lines (dot-matrix style), one claim per line, each with a confidence chip.
- Footer: `CONFIDENCE 91% · RELEVANCE HIGH · IMPACT SIGNIFICANT` + `VIEW TRACE` link.
- Trace view: expandable panel showing prompt summary, matched parameters, raw reasoning as terminal stdout, and the final boolean decision:

```
[LLM_VETO] CONFIDENCE 84% < 90% :: HOLD
[LLM_APPROVE] CONFIDENCE 91% ≥ 90% :: ENTER LONG BTC/USDT
```

### 12.4 LLM Veto Log (24H)

Table: `TIME | PAIR | REASON | AGENT`. Reason is the machine-readable decision string (mono), agent is the model id. Row color: approved = mist, vetoed = amber border-left, kill = coral border-left. All rows link to trace view.

### 12.5 Rules

- **R12.1** — Every AI claim on screen carries: source model, confidence ± σ, timestamp.
- **R12.2** — No natural-language summary may replace the structured decision; the structured line is primary, prose is secondary.
- **R12.3** — Streaming LLM text renders as terminal lines with a block cursor `▍`; no typewriter easing, no shimmer.
- **R12.4** — Anthropomorphic copy is forbidden: no "I think", "the model believes". Copy uses `CONFIDENCE`, `SIGNAL`, `DECISION`, `VETO`.
- **R12.5** — AI surfaces are violet-tinted only via tokens; never via unlabeled color.

### 12.6 Anti-patterns

- ❌ Chat-bubble UI for the model.
- ❌ "Neural network" decorative graphics (nodes/brains) anywhere.
- ❌ Claiming the model "understands" the market in product copy.
- ❌ Omitting provenance.

---

## 13. Computational Graphic Language

### 13.1 Definition

KAIRO's graphic language is a **family of generative, data-driven texture systems**. They are used as: chart bases, widget backgrounds (at ≤ 8% alpha), marketing surfaces, and print. Every pattern is generated from parameters; none is a static asset.

### 13.2 Canonical patterns

| Pattern | Generation rule | Product use |
|---------|----------------|-------------|
| **DOT MATRIX** | Grid of dots, pitch 4px, dot 2px, alpha ≤ 40% | Chart theme, panel texture, mark construction |
| **HALFTONE** | Circle radius ∝ field value; used for faces/maps only as data viz | Regime maps, liquidation map |
| **WAVEFORM** | Sine/compound wave, stroke 1px, amplitude from a real series | Equity derivative art, boot splash |
| **DATA STREAM** | Vertical bars, height ∝ a live metric (volume/flow) | Landing live strip, widget headers |
| **REGIME MAP** | Scatter of colored dots by regime class | Landing, docs covers |
| **GRADIENT FLOW** | Dense dot cloud with density ∝ the data gradient ramp | Marketing surfaces, docs |
| **GLITCH BLOCKS** | 4px pixel blocks re-slicing a chart strip | Error/terminal aesthetic, boot frames |
| **TOPO GRID** | Contour lines from an actual field (e.g., funding, spread) | Docs, print |
| **POINT CLOUD** | Uniform random dots, seeded per brand asset | Backgrounds at ≤ 6% alpha |
| **NOISE FIELD** | Perlin value noise, mono | Textures |
| **DATA BLOCKS** | Grid of 4px cells, alpha ∝ value | Widget chrome |

### 13.3 Rules

- **R13.1** — All patterns are parameterized (seed, scale, alpha, palette) and generated at runtime or build time from `/patterns` modules. No hand-drawn pattern files.
- **R13.2** — Alpha ceiling 8% in product UI backgrounds; 40% on marketing print only.
- **R13.3** — Patterns must never obscure data (never placed under active chart series at >8%).
- **R13.4** — A pattern used as decoration must still derive from a live or seeded dataset (seed = brand seed `KAIRO-2024`).

---

## 14. Motion System

### 14.1 Principles

Motion communicates state change and nothing else. All motion is **linear or single-easing**, ≤ 300ms, and never loops except the specified pulse/cursor exceptions.

### 14.2 Tokens

| Token | Value | Use |
|-------|-------|-----|
| `--dur-instant` | 0ms | State swaps that must not animate (risk breach, kill) |
| `--dur-fast` | 120ms | Hover, focus, toggles, badges |
| `--dur-base` | 200ms | Panels, tables, modals in |
| `--dur-slow` | 300ms | Drawers, page transitions (rare) |
| Easing | `cubic-bezier(0.25, 0.1, 0.25, 1)` or `linear` | Never spring/bounce |
| `--motion-reduce` | media query | Global kill switch for all motion |

### 14.3 Data-update motion

- Value change: no count-up on tick; new value swaps instantly, with a 1-frame background flash (lime/coral 12% alpha, 150ms fade) — the flash is the only "animation" on live figures.
- Chart series update: 200ms linear morph of the polyline; crosshair moves instantly.
- New table row: 120ms highlight (12% bg flash) then settle. No slide-in rows.

### 14.4 Boot sequence (splash)

Ordered, timed, mono: `KAIRO` wordmark in KAIRO DOT draws via dot-reveal (120ms), then terminal lines appear one per 80ms:

```
> kairo.run --live
[12:26:46] SYSTEM ONLINE
[OK] DATA FEED / RISK ENGINE / LLM ENGINE / SAFETY GATE / TRADING
>
```

Total ≤ 1.6s; skippable; `prefers-reduced-motion` → static splash.

### 14.5 Rules

- **R14.1** — Motion must never delay a critical action's execution (kill switch executes at pointer-up, not after animation).
- **R14.2** — No parallax, no scroll-triggered reveals in product; landing may use scroll reveals ≤ 200ms linear.
- **R14.3** — Pulse only for L0 risk escalation, ≤ 3 pulses.
- **R14.4** — All motion respects `prefers-reduced-motion` (reduce to instant + static flashes).

---

## 15. Iconography

### 15.1 System

- Grid: 24×24. Stroke: 1.5px at 24px (1px at 16px via scaling group), round caps/joins, aligned to the 1px grid.
- Set: linear outline only. No filled, duotone, or gradient icons.
- Rendered as inline SVG components; never font glyphs; never raster.

### 15.2 Canonical set (14)

`OVERVIEW` (grid), `PORTFOLIO` (stack), `POSITIONS` (nodes), `STRATEGIES` (pyramid), `MARKETS` (globe), `ANALYTICS` (bars), `RISK` (shield), `TRADES` (bolt), `REPORTS` (document), `TAX` (percent-coin), `SETTINGS` (gear), `SYSTEM` (circuit), `ALERTS` (bell), `KILL SWITCH` (warning triangle).

### 15.3 Rules

- **R15.1** — Icon color: `--text-secondary` default; `--signal-primary` active; `--status-danger` only for kill switch (always coral, always present in rail).
- **R15.2** — Kill switch icon is the only red icon; never used for anything else.
- **R15.3** — No new icons without adding both 16px and 24px variants and a11y labels.
- **R15.4** — Icons are never animated (no spinning gears); active states use the 2px indicator (§8.1), not icon motion.

### 15.4 Engineering

- Export from a single Figma/SVG source; validate geometry (all paths on 1px grid) via a build check; icons tree-shaken per route.

---

## 16. Copywriting

### 16.1 Voice rules

1. **Numbers before adjectives.** `DRAWDOWN −3.21%` not `healthy drawdown`.
2. **No exclamation marks** in product copy. Zero.
3. **No emoji** in product surfaces (status uses glyphs `▲▼●`, not emoji).
4. **No weasel words:** never "might", "maybe", "could improve". Use confidence ranges: `84% ± 1.2%`.
5. **No anthropomorphism of the model:** "the model" is a system; copy uses `CONFIDENCE/DECISION/VETO`.
6. **India-aware:** ₹ with Indian digit grouping; IST as default local time; tax language matches Indian regime categories (short-term/long-term capital gains).

### 16.2 Copy patterns (canonical strings)

| Context | String |
|---------|--------|
| System online | `SYSTEM ONLINE` |
| Feed ok | `DATA FEED OK` |
| Cycle | `[INFO] Cycle complete. Next cycle in 02:14` |
| Veto | `LLM VETO — CONFIDENCE 84% < 90% :: HOLD` |
| Risk breach | `DAILY LIMIT 98% — AUTO-STOP IN 00:30` |
| Kill confirm | `TYPE "CONFIRM" TO LIQUIDATE ALL POSITIONS` |
| Error | `E-1024 · ORDER REJECTED · INSUFFICIENT MARGIN` |
| Empty | `NO OPEN POSITIONS` + `Run a strategy to begin.` |

### 16.3 Error copy rules

- Format: `CODE · SUMMARY · ACTION`. Never a bare "Something went wrong".
- Every error has a log line and, where possible, a RETRY.

### 16.4 Anti-patterns

- ❌ "Level up your trading", "10x your gains", "squeeze the alpha" — banned.
- ❌ Marketing superlatives in product (L1 figures are data, not slogans).
- ❌ Passive voice in system messages (`Order was rejected` → `ORDER REJECTED`).

---

## 17. Accessibility

### 17.1 Standards

WCAG 2.2 AA is the floor. Keyboard-only usage must be able to: open any view, sort any table, arm/kill, and inspect any AI decision.

### 17.2 Rules

1. **R17.1 — Color never sole channel.** Up/down, status, and risk always pair color with glyph/label (§R4.4). Enforced by component contract.
2. **R17.2 — Focus.** Visible 2px `--focus-ring` (cyan) with 2px offset on all interactive elements; `:focus-visible` only; no focus trap bugs (tested).
3. **R17.3 — Contrast.** Tokens pre-verified (§4.6); any new color needs a contrast fixture test.
4. **R17.4 — Screen readers.** Charts expose data tables or summary + `aria-live` throttled readouts (§11.14). Terminal log has `aria-live="polite"` at 1Hz throttle.
5. **R17.5 — Motion.** `prefers-reduced-motion` honored globally (§14.2 token).
6. **R17.6 — Target size.** ≥ 44×44px hit area for icon buttons in Z1; table rows ≥ 26px min.
7. **R17.7 — Zoom.** Layout must remain functional at 200% browser zoom without horizontal scroll on core paths (density tiers adapt).
8. **R17.8 — Color-blind.** Deuteranopia/tritanopia simulation pass required per release (§4.6).

### 17.3 QA (accessibility)

- [ ] axe-core scan: 0 critical/serious violations on every route (CI gate).
- [ ] Full keyboard walkthrough script passes (nav → table sort → modal → kill flow).
- [ ] SR test: charts announce series summary; veto log announces rows.
- [ ] Reduced-motion: all animations collapse to instant; no functional loss.

---

## 18. Performance Budgets

### 18.1 Core budgets (hard)

| Metric | Budget | Notes |
|--------|--------|-------|
| LCP | ≤ 800ms (mid-tier mobile 4G) | Hero canvas deferred; fonts per §5.4 |
| INP | ≤ 50ms | Kill switch path targeted ≤ 50ms |
| TBT | ≤ 100ms | Heavy chart/WASM deferred after shell interactive |
| Initial JS (gzipped) | ≤ 150KB | Route-split; chart engine and WebGL lazily loaded |
| Font payload | ≤ 180KB woff2 | All fonts, all weights shipped |
| Chart frame | ≤ 8ms JS / 16.6ms total | WebGL 500k pts @ 60fps; SVG ≤ 500 nodes |
| Data ingest | 20Hz (50ms) | WebSocket receive; render batch 5Hz (200ms) |
| Memory | < 100MB/chart heap; < 300MB app | Leak tests per release |

### 18.2 Rules

- **R18.1** — No full-page data re-render on ticks; component-level diffing only.
- **R18.2** — Virtualize anything > 50 rows / > 500 SVG nodes.
- **R18.3** — Off-thread everything possible: WebGL, Web Workers for strategy math, `content-visibility: auto` for below-fold panels.
- **R18.4** — Budgets are CI-gated (Lighthouse assertions + custom perf tests). A PR that regresses a budget fails.

### 18.3 Anti-patterns

- ❌ Rendering 5Hz ticks into a non-virtualized React table.
- ❌ Importing the chart engine on the landing page shell.
- ❌ Unthrottled `requestAnimationFrame` loops when tab is hidden (pause when `document.hidden`).

---

## 19. Responsive Behavior

### 19.1 Strategy

**Desktop-first.** The terminal is the product; tablets/phones are monitoring surfaces, not full trading stations. Adaptive, not just responsive.

| Breakpoint | Layout |
|------------|--------|
| ≥ 1440px | Full terminal, 12-col grid, 3 rows of widgets |
| 1024–1439px | Z1 collapses labels (icons only), Z2 grid → 2 rows, widgets reflow to 6-col each |
| 768–1023px | Tablet: Z1 becomes bottom tab bar (5 primary items), Z2 single column scroll, Z3 log collapsed to notification drawer |
| < 768px | Mobile: metric-first dashboard (L0 bar + equity + risk + positions), full tables → card list, kill switch pinned bottom-right floating action (coral), terminal surfaces read-only |

### 19.2 Mobile-specific rules

- **R19.1** — Trading actions (open/close) require confirmation modal on mobile; kill switch requires hold + typed confirm regardless of platform.
- **R19.2** — Charts: touch crosshair = tap-and-hold with readout chip; pinch zoom supported; candle charts default to 30 min candles on mobile.
- **R19.3** — Density tiers: mobile always COMPACT for tables-turned-cards; user pref overridden with note.
- **R19.4** — Landing: hero canvas dropped < 768px (§9.4).

---

## 20. CSS Variables & Design Tokens

### 20.1 Architecture

Three layers: **Primitives** (`--kairo-*`), **Semantic** (`--surface-*`, `--text-*`, `--status-*`, `--signal-*`, `--ai-*`, `--action-*`), **Component-level** (defined in component files, referencing semantic only).

### 20.2 Distribution

- Tokens are the single source exported from `/tokens` (JSON) and compiled to: CSS custom properties (`:root`), Tailwind theme, TypeScript constants (`tokens.ts`), and design-tool sync. No hex values live in component code or Tailwind config directly.

### 20.3 Complete token list

Primitives (§4.2) + semantic (§4.3) + spacing (§6.2) + type (§5.2) + motion (§14.2) + radii (`--radius-sm 2px`, `--radius-md 4px`, `--radius-lg 6px`) + shadows (none; borders only, except a single `--shadow-popover: 0 8px 24px rgba(0,0,0,0.5)` for floating layers).

### 20.4 Rules

- **R20.1** — No raw values in components. Lint rule: `no-hex-literals`, `no-magic-spacing`.
- **R20.2** — Adding a token requires updating all four exports (CSS/JSON/TS/Tailwind) + contrast fixture if color.
- **R20.3** — Dark theme is the only theme; no `data-theme` variants. Future themes (colorblind mode) map semantic tokens, not primitives.

---

## 21. React / Next.js / Tailwind Architecture

### 21.1 Stack

- **Framework:** Next.js (App Router), RSC-first.
- **Styling:** Tailwind CSS v4 configured from the token JSON; CSS custom properties for runtime theming; no inline styles for layout.
- **Charts:** chart engine as a framework-agnostic WebGL/SVG module (`@kairo/charts`) with React wrappers; rendered client-side only.
- **Data:** WebSocket gateway + TanStack Query for REST; Zustand for ephemeral UI state; server state never in local stores.
- **Tables:** virtualized via TanStack Virtual.

### 21.2 Rendering strategy

- **Server components:** landing page, docs, static marketing — zero client JS where possible.
- **Client components:** dashboard shell, charts, tables, logs, kill switch. Isolate client islands with clear props contracts.
- **Streaming:** splash → terminal shell streams first; data-heavy charts mount after interactive.
- **Code splitting:** `@kairo/charts` and `@kairo/terminal` are dynamic imports; kill switch is statically imported (must be instant).

### 21.3 Rules

- **R21.1** — Every data view is typed end-to-end: socket message → normalized store → component props (zod-validated at the boundary).
- **R21.2** — No component fetches data directly; data flows from route/server loaders or the socket store via hooks (`useEquity`, `usePositions`).
- **R21.3** — Re-render isolation: 5Hz updates hit leaf components only (memoized rows, virtualized).
- **R21.4** — Server actions for mutations (kill, arm, config) with optimistic UI only where idempotent and safe (never for kill).
- **R21.5** — Tailwind config reads tokens; theme changes (density, chart render mode) via CSS variables + a single context, never per-component branching.

---

## 22. Folder Structure & Naming Conventions

### 22.1 Monorepo layout

```
kairo/
├── apps/
│   ├── terminal/          # Next.js product app
│   ├── landing/           # Next.js marketing app
│   └── docs/              # design system docs + token sync
├── packages/
│   ├── tokens/            # source of truth (JSON → css/ts/tailwind)
│   ├── ui/                # component library (@kairo/ui)
│   ├── charts/            # chart engine (@kairo/charts)
│   ├── terminal/          # log/kill/system components (@kairo/terminal)
│   └── lib/               # formatting, validation, math
├── brand/                 # logo, fonts, mark source
└── patterns/              # generative pattern modules
```

### 22.2 Naming conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Components | PascalCase, domain-prefixed | `MetricCard`, `RiskGauge`, `KillSwitch` |
| Hooks | `use` + noun | `usePositions`, `useSystemHealth` |
| Tokens | `--kairo-*` primitives, `--surface-*` semantic | `--kairo-cyan`, `--status-danger` |
| CSS classes | Tailwind utilities only; custom classes only in `@layer components` | `kairo-panel` |
| Chart series | `candles`, `equity`, `volume`, `regime`, `flow` | — |
| Tests | `*.test.tsx` colocated | `KillSwitch.test.tsx` |
| Files | kebab-case | `risk-gauge.tsx` |

### 22.3 Rules

- **R22.1** — One component per file; default export only for pages/route files, named exports for library components.
- **R22.2** — No barrel files that defeat tree-shaking for charts/terminal.
- **R22.3** — Every component ships: types, tests, story, and a `docs.mdx` including its `data-source` annotation (§1.5).

---

## 23. Engineering Guidelines

### 23.1 Standards

- TypeScript strict; no `any` crossing data boundaries.
- ESLint + Prettier + `no-hex-literals` + `no-magic-spacing` + a11y plugin in CI.
- Tests: unit (Vitest), component (Testing Library + axe), E2E (Playwright), perf (Lighthouse CI + custom chart fixture).
- All times stored UTC; displayed local IST with label; durations as ms integers.
- All money: integer minor units (paise) with formatting at the edge; no float math for money (use BigInt/decimal lib).

### 23.2 Data pipeline contract

1. WebSocket message → zod schema → normalized store → selector → leaf component.
2. Every numeric field carries `precision` metadata for formatting.
3. Every message carries `ts` (server UTC) — client never guesses freshness; stale rules per §8.4.

### 23.3 Rules

- **R23.1** — Chart engine is framework-agnostic; React is an adapter. This keeps the WebGL hot path outside React.
- **R23.2** — No `Math.random()` in render paths except seeded brand patterns (§13.3).
- **R23.3** — All mutations idempotent server-side; UI reflects server state.
- **R23.4** — Accessibility checks run in CI on every PR, not just release.

---

## 24. Design QA Checklist (Release Gate)

**Visual / Brand**
- [ ] Zero glassmorphism, neumorphism, decorative gradients, stock images (§1.5).
- [ ] Accent budget ≤ 3 per viewport; semantic color map respected (§4.4).
- [ ] Logo: correct lockup, clear space, no recoloring/effects (§3.5).
- [ ] All figures monospace + tabular; size invariant to sign (§5.2).

**Layout / Hierarchy**
- [ ] L0 status bar always visible; kill switch ≤ 1 interaction from any screen (§7.3, §8.1).
- [ ] ≥ 40 data fields visible on default dashboard at 1440×900 (§1.3).
- [ ] No tooltip-only critical data (§10.4).
- [ ] Density switch: no overflow at 1280×800 (§6.3).

**Charts**
- [ ] Every chart has as-of timestamp + source footer (§11.2).
- [ ] Y-axis no misleading truncation; break glyph if truncated (§R11.2).
- [ ] Crosshair snap verified; SR table exists (§11.14).
- [ ] WebGL 500k fixture @ 60fps; SVG ≤ 500 nodes (§11.1).

**AI surfaces**
- [ ] Every AI output shows source + confidence ± σ + timestamp (§12.5).
- [ ] No anthropomorphic copy or visuals; `LLM VETO NOT CONTROL` label present (§12.1).
- [ ] Veto log rows link to trace view (§12.4).

**Motion / Interaction**
- [ ] Only approved easings/durations; no springs; reduced-motion honored (§14).
- [ ] Kill switch executes at pointer-up, hold-to-arm + typed confirm (§10.9).

**Accessibility**
- [ ] axe 0 critical/serious; keyboard walkthrough passes; SR charts pass (§17.3).
- [ ] Deuteranopia/tritanopia simulation pass (§4.6).

**Performance**
- [ ] LCP/INP/TBT/bundle within §18 budgets (CI-gated).
- [ ] 5Hz tick re-renders only leaf components (§R18.1, §R21.3).
- [ ] No unthrottled rAF when hidden (§18.3).

**Copy**
- [ ] No exclamation marks, emoji, hype, or weasel words in product copy (§16).

---

## 25. Master Implementation Prompt (for coding agents)

> You are implementing the KAIRO Autonomous AI Trading Operating System according to the design specification in RFC-001 (the document you have been given). Build it exactly to spec; do not invent alternatives.
>
> **Stack:** Next.js (App Router, RSC-first), TypeScript strict, Tailwind v4 configured exclusively from the token JSON in `/packages/tokens` (no raw hex, no magic spacing — lint-enforced), WebGL/SVG chart engine in `/packages/charts` (framework-agnostic core with React adapters), WebSocket data gateway + TanStack Query, TanStack Virtual for tables, Zustand for ephemeral UI state.
>
> **Non-negotiable requirements:**
> 1. **Visual language:** dark-only (VOID #08080B base), neon-on-void accents per the semantic token map. Zero glassmorphism, zero decorative gradients, zero stock imagery, zero anthropomorphic AI visuals. Every pixel traces to a data field, system state, or user interaction.
> 2. **Hierarchy:** L0 global status bar (always visible: LIVE/SAFE/RISK, cycle countdown, uptime, kill switch slot); risk metrics outrank PnL in visual weight; figures are monospace/tabular and size-invariant to sign.
> 3. **Kill switch:** reachable from any screen in ≤ 1 interaction; hold-to-arm (1.2s) → typed-confirm modal → idempotent server call; UI reflects server state only; INP ≤ 50ms on this path.
> 4. **Charts:** ingest at 20Hz, render-batch at 5Hz; WebGL for high-density series (500k pts @ 60fps), SVG for axes/crosshair (≤500 nodes); every chart has an as-of timestamp and source footer; up/down never color-only.
> 5. **AI surfaces:** structured decision artifacts (source model, confidence ± σ, timestamp, trace view); veto log renders machine-readable decisions as terminal stdout; `LLM VETO NOT CONTROL` label on all AI surfaces.
> 6. **Density tiers** (COMFORTABLE/DENSE/COMPACT), persisted per user; responsive: desktop terminal, tablet bottom-tab monitor, mobile metric-first with pinned kill switch.
> 7. **Performance:** LCP ≤ 800ms, INP ≤ 50ms, initial JS ≤ 150KB gzipped; chart engine and fonts deferred appropriately; budgets CI-gated.
> 8. **Accessibility:** WCAG 2.2 AA, full keyboard operation, screen-reader chart tables, `prefers-reduced-motion` honored, color-blind simulation pass.
> 9. **Structure:** monorepo layout and naming conventions per §22; components ship types, tests, stories, and docs with `data-source` annotations.
> 10. **Copy:** exact strings from §16.2 where applicable; no exclamation marks, emoji, hype, or weasel words.
>
> Deliver working code for the full dashboard (Z0/Z1/Z2/Z3), all 14 canonical widgets, the component library, the kill-switch flow, the veto-log + trace view, responsive breakpoints, and the landing page. Provide CI checks for the QA checklist in §24. When finished, run the full §24 checklist and report each item pass/fail with evidence.

---

## Appendix A — Token reference (quick map)

`--kairo-void #08080B` · `--kairo-steel #12141B` · `--kairo-slate #1E232B` · `--kairo-hairline #262B34` · `--kairo-mist #E6E6E6` · `--kairo-silver #9AA3B2` · `--kairo-mute #5C6470` · `--kairo-lime #39FF14` · `--kairo-cyan #00E5FF` · `--kairo-violet #7C4DFF` · `--kairo-blue #2962FF` · `--kairo-amber #FFB800` · `--kairo-coral #FF5C7A` · `--kairo-ink #FFFFFF`

**Retired values (do not use):** `#A6FF00`, `#80FF9D`, `#00D4FF`, `#7C5CFF`, `#8D6BFF`, `#FF6A00`, `#F5E36A`, `#080D12`, `#0B0F14`(→charcoal), `#080E12`.

## Appendix B — Rationale notes

1. **Why WebGL + SVG hybrid:** WebGL owns the point budget; SVG owns interaction precision (crosshair snapping, DOM events, a11y hooks). Canvas2D is reserved for static sparklines to avoid WebGL context overhead on trivial series.
2. **Why 20Hz/5Hz split:** 50ms ingest keeps data fresh; 200ms render batching prevents strobing and holds the 8ms JS frame budget (§18).
3. **Why lime over the earlier neon greens:** `#39FF14` holds the highest contrast on VOID and matches the "terminal green" institutional signal (System Online), while `#A6FF00` is retired to marketing-only if ever needed.
4. **Why violet = AI:** it is the only primary never used for deterministic market data, giving users a strict color grammar for provenance.
5. **Why PnL below risk:** capital preservation before profit display is both a brand position and an operational safety pattern; the hierarchy is enforced structurally (sizes §7.2), not by mood.

---

*End of RFC-001. This document is the source of truth. Any conflict with older brand assets resolves in favor of this RFC. Amendments require a new RFC revision (v1.1.0+).*
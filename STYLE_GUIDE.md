# AI Visibility Dashboard — Design System Reference

> **How to use this doc.** This document reverse-engineers the design system from `dashboard.html` (a self-contained ~17 800-line vanilla JS + inline CSS file). Every claim is backed by a file:line reference. Read sections 1–14 to understand what exists; read section 15 for honest gaps; read section 16 for a porting guide to PeekABoo's Next.js + Tailwind stack.

---

## 1. Overall Aesthetic

This dashboard sits squarely in the "modern SaaS, minimal" camp — closer to Linear or Vercel's dashboard than to Bloomberg or Google Analytics. The palette is almost entirely neutral white and gray with a single violet-purple brand accent (`#b352b3`) that appears on active states, CTAs, focus rings, and the brand identity. Surfaces are white on white with ultra-light borders; shadows are barely there. The typographic density is moderate — data tables are compact but not brutalist. There is a playful brand gradient (pink → yellow) that surfaces only in decorative spots (logo icon, avatar background) and never as a primary UI signal. The overall feel is: clean SaaS product built by someone who has used Linear and Notion as references.

---

## 2. Color Palette

All tokens are defined in `:root` at `dashboard.html:23–59`.

### Design Tokens

| Token | Hex / Value | Where used |
|---|---|---|
| `--bg` | `#ffffff` | Page background |
| `--surface` | `#ffffff` | Card, modal, input backgrounds |
| `--surface-alt` | `#fafafa` | Table header bg, hover bg, inactive tab bg |
| `--surface-hover` | `#f4f4f5` | General hover fill (defined but rarely used directly) |
| `--border` | `#EEEEEF` | Card borders, table dividers, input borders |
| `--border-light` | `rgba(0,0,0,0.05)` | Row separators inside cards |
| `--text` | `#1c1917` | Primary text — warm near-black |
| `--text-muted` | `#545D6C` | Secondary labels, descriptions, table headers |
| `--text-faint` | `#9CA3AF` | Timestamps, meta info, empty state text |
| `--accent` | `#b352b3` | Primary CTA bg, active nav indicator, focus rings, pagination active, links |
| `--accent-hover` | `#a043a0` | Hover state for `--accent` buttons |
| `--accent-light` | `rgba(179,82,179,0.08)` | Tinted panel backgrounds (info banners, selected states) |
| `--accent-30` | `rgba(179,82,179,0.3)` | Focus ring shadow, subtle borders |
| `--brand-pink` | `#f8c8ff` | Logo gradient start, range calendar in-range highlight |
| `--brand-yellow` | `#ffcc45` | Logo gradient end |
| `--success` | `#10b981` | Positive change indicators |
| `--success-light` | `#dcfce7` | Positive badge backgrounds |
| `--danger` | `#ef4444` | Error states, delete actions |
| `--danger-light` | `#fee2e2` | Danger badge backgrounds |
| `--warning` | `#f59e0b` | Warning states (token defined; used inline rather than via token) |
| `--sidebar-bg` | `rgba(255,251,235,0.1)` | Sidebar — very faint warm tint over white |

### Semantic Colors (hard-coded, not tokenized)

| Semantic role | Hex | Notes |
|---|---|---|
| Success text | `#16a34a` / `#15803d` | Both appear; no unified token |
| Success bg | `#f0fdf4` / `#dcfce7` | Two shades used interchangeably |
| Success border | `#bbf7d0` | |
| Danger text | `#b91c1c` / `#dc2626` | Two shades; no unified token |
| Danger bg | `#fef2f2` / `#fee2e2` | |
| Neutral badge | `#f3f4f6` bg, `#6b7280` text | |
| Active toggle | `#22c55e` | Toggle on-state (green, not `--success`) |

### Chart / Brand Color Sequence

Defined at `dashboard.html:5344` as `AIM_SOURCE_LINE_COLORS` and `AI_BRANDS[].color`:

| Slot | Hex | Semantic label |
|---|---|---|
| 1 (main brand) | `#b352b3` | Peekaboo purple / accent |
| 2 | `#10b981` | Emerald |
| 3 | `#2563eb` | Blue |
| 4 | `#8b5cf6` | Violet |
| 5 | `#64748b` | Slate |
| 6 | `#06b6d4` | Cyan |
| 7+ | `#f59e0b` | Amber (reused) |
| 8+ | `#f472b6` | Pink (reused) |
| 9+ | `#38bdf8` | Sky |
| 10+ | `#94a3b8` | Cool gray |
| Fallback | `#6b7280` | Neutral gray |

Line chart opacity fill: `color + '18'` (10% alpha hex), consistently applied throughout.

---

## 3. Typography

**Font family** — Inter, loaded from Google Fonts (`dashboard.html:15–17`):

```
'Inter', ui-sans-serif, system-ui, sans-serif
```

Weights loaded: 300, 400, 500, 600, 700, 800.
Token: `--font` (`dashboard.html:59`).

**Base body** — `font-size: 14px`, `line-height: 1.5`, set on `body` at `dashboard.html:65–70`.

### Type Scale (extracted from component CSS)

| Use | Size | Weight | Notes |
|---|---|---|---|
| Body base | 14px | 400 | `body` |
| Body small | 13px | 400 | Most table cell text, inputs |
| Body smaller | 12px | 400–500 | Labels, badge text, secondary content |
| Micro | 11px | 400–600 | Timestamps, meta chips, chart ticks |
| Nano | 10px | 600 | Table `thead` labels (all-caps) |
| Nano micro | 9.5–10px | 600 | Sub-badges |
| Card title | 13px | 600 | `.card-title` |
| Page title | 16px | 700 | `.page-header h1`, `letter-spacing: -0.2px` |
| Ask AI heading | 21px | 700 | `.ask-ai-title`, `letter-spacing: -0.35px` |
| Stat value (SC) | 26px | 700 | Search Console stat cards, `letter-spacing: -0.5px` |
| Logo wordmark | 14px | 700 | `letter-spacing: -0.3px` |
| Logo subline | 11px | 400 | `color: var(--text-muted)` |
| Section label | 10–11px | 600–700 | `text-transform: uppercase`, `letter-spacing: .06–.12em` |
| Modal title | 15px | 700 | `.aim-st-card-title`, `.aim-ap-title` |

**Negative letter-spacing** is used consistently on headings and large numbers (`-0.2px` to `-0.5px`) to create a tighter, more premium feel.

**Line heights:** Body 1.5, answers/responses 1.6–1.65, compact rows 1.3–1.4.

---

## 4. Spacing System

No named spacing scale token exists. Spacing is an 8px-base soft system used pragmatically.

| Pattern | Value | Example |
|---|---|---|
| Base unit | 4px (half-step) | Icon gaps, micro padding |
| Standard unit | 8px | Component gaps, icon margins |
| Card body padding | 16px | `.card-body` |
| Card header padding | `12px 16px` | `.card-header` |
| Page content padding | `24px 28px` | `.page-content` |
| Topbar height | 65px | `.aim-topbar` (and sidebar logo area) |
| Sidebar width | 288px default | `--sidebar-w` |
| Component gap | 16px | `.aim-two-col`, card margin-bottom |
| Inline gap | 6–9px | Nav icon + label, button icon + label |
| Section margin | 16–24px | Between major blocks |

Padding inside buttons follows a pattern: `6–8px` vertical, `10–14px` horizontal for standard; `5px 14px` for small pill buttons.

---

## 5. Layout Primitives

**Structure:** Fixed sidebar + scrollable main column (`display: flex` on body, `dashboard.html:66`).

| Element | Value |
|---|---|
| Sidebar width (default) | `288px` (`--sidebar-w`) |
| Sidebar width (tablet) | `240px` (at ≤1100px) |
| Sidebar width (icon-only) | `64px` (at ≤820px) |
| Sidebar background | `rgba(255,251,235,0.1)` — near-white warm tint |
| Sidebar border-right | `1px solid #e5e3df` |
| Topbar height | `65px` (reduced to `56px` at ≤640px) |
| Topbar backdrop | `rgba(255,255,255,0.97)` + `backdrop-filter: blur(8px)` |
| Page content padding | `24px 28px` (↓ `20px` at ≤1100px, ↓ `14px` at ≤820px, ↓ `10px` at ≤640px) |
| Two-column grid | `grid-template-columns: 1fr 1fr; gap: 16px` — `.aim-two-col` |
| Sources grid | `grid-template-columns: 300px 1fr` — `.aim-sources-grid` |

**Breakpoints:**

| Breakpoint | Width | Key change |
|---|---|---|
| Compact | `≤1100px` | Sidebar narrows to 240px, meta hidden in topbar |
| Tablet | `≤820px` | Sidebar collapses to 64px icon-only, grids go single column |
| Mobile | `≤640px` | Sidebar slides off-canvas (hamburger), topbar 56px, touch-friendly |

No container max-width is defined — the main column fills remaining viewport width.

---

## 6. Buttons

Three primary button variants defined as named classes. Focus states use browser default (no custom `outline` override observed).

### Primary (accent fill)

```css
/* dashboard.html:834 */
.aim-st-btn-primary {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 8px 14px; font-size: 12px; font-weight: 600;
  background: var(--accent); color: #fff; border: none;
  border-radius: 7px; cursor: pointer;
  transition: background .12s;
}
.aim-st-btn-primary:hover { background: var(--accent-hover); }
```

Also appears as `.ask-ai-send-btn` (height: 42px, padding: `0 20px`, `font-size: 13px`, `border-radius: 9px`) and `.aim-st-copy-btn` (pill shape, `border-radius: 20px`).

### Outlined / Secondary

```css
/* dashboard.html:843 */
.aim-st-btn-outlined {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 7px 13px; font-size: 12px; font-weight: 500;
  background: #fff; color: var(--text);
  border: 1px solid var(--border); border-radius: 7px;
  cursor: pointer; transition: border-color .12s;
}
.aim-st-btn-outlined:hover { border-color: var(--accent); color: var(--accent); }
```

### Danger

```css
/* dashboard.html:851 */
.aim-st-btn-danger {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 7px 11px; font-size: 12px;
  background: #fee2e2; color: #dc2626; border: none;
  border-radius: 6px; cursor: pointer;
}
```

### Floating Action Bar Buttons

Three sub-variants — default (gray), primary (accent), danger (red) — defined at `dashboard.html:1064–1071`. All share `height: 30px`, `padding: 0 12px`, `font-size: 12px`, `font-weight: 600`, `border-radius: var(--radius)`.

### Ghost / Icon buttons

`.sidebar-icon-btn` (26×26px, `border-radius: 6px`, `border: 1px solid #d1d5db`), `.aim-mgr-del-btn` (color `#f87171`, `border-radius: 6px`).

### Tab / Pill button groups

`.aim-tab-bar` wraps `.aim-tab` buttons in a pill container (`border-radius: var(--radius-pill)`, `background: var(--surface-alt)`, `padding: 3px`). Active tab: white fill + `box-shadow: 0 1px 2px rgba(0,0,0,0.06)`.

**Disabled state:** `.ask-ai-send-btn:disabled { opacity: .45; cursor: default; }` — opacity-only, no other visual change. No global disabled pattern.

**No size scale** (sm/md/lg) is formally defined. Sizes are set per-component via padding overrides.

---

## 7. Form Elements

### Text Inputs (standard)

```css
/* dashboard.html:808 */
.aim-st-input {
  width: 100%; padding: 9px 12px; font-size: 13px;
  border: 1px solid var(--border); border-radius: 7px;
  background: #fafafa; color: var(--text);
  font-family: var(--font); box-sizing: border-box;
}
```

Focus state (modal inputs): `border-color: var(--accent); box-shadow: 0 0 0 3px rgba(179,82,179,.1)` — `dashboard.html:1270`.

### Search Input

```css
/* dashboard.html:1012 */
.aim-search-input {
  padding: 6px 10px 6px 30px; font-size: 12px;
  border: 1px solid var(--border); border-radius: var(--radius-pill);
  background: var(--surface-alt);
  width: 180px; transition: border-color .15s, box-shadow .15s;
}
.aim-search-input:focus { border-color: var(--accent); background: var(--surface); box-shadow: 0 0 0 3px rgba(179,82,179,0.12); }
```

Icon positioned `left: 9px` with `position: absolute`. Width shrinks responsively (180 → 140 → 130 → 100%).

### Ask AI Input (large)

```css
/* dashboard.html:2579 */
.ask-ai-input {
  flex: 1; height: 42px; border: 1px solid var(--border);
  border-radius: 9px; padding: 0 14px; font-size: 13.5px;
  outline: none; transition: border-color .15s, box-shadow .15s;
}
.ask-ai-input:focus { border-color: var(--accent-30); box-shadow: 0 0 0 3px rgba(179,82,179,0.08); }
```

### Toggles / Switches

Two toggle variants coexist:

**Small inline toggle** (`.aim-toggle` — 32×18px):
Track off: `var(--border)`, track on: `#22c55e`. Thumb 14×14px. `dashboard.html:1079–1087`.

**Standard toggle** (`.aim-rc-toggle` / `.aim-st-toggle` — 42–44×24px):
Same pattern, slightly larger. Off: `var(--border)`, on: `#22c55e`. Thumb 20×20px.
Older toggle form: `input:checked + slider` pattern using `accent-color: var(--accent)` for native checkbox.

**iOS-style toggle** (`.aim-ios-toggle` — 36×20px): Uses `input:checked` + `::before` — off: `#d1d5db`, on: `var(--accent)`. `dashboard.html:1443`.

There are three slightly different toggle implementations with no shared base class.

### Custom Selects

```css
/* dashboard.html:355 */
.ct-custom-trigger {
  padding: 0 12px; height: 36px; font-size: 13px;
  background: #fff; border: 1px solid #e5e5e5; border-radius: 6px;
  transition: background .12s, border-color .12s;
}
.ct-custom-trigger:hover { background: #f5f5f5; }
.ct-custom-dropdown { border-radius: 6px; box-shadow: rgba(0,0,0,.1) 0px 4px 6px -1px, rgba(0,0,0,.1) 0px 2px 4px -2px; padding: 4px; }
.ct-custom-option { padding: 6px 8px; border-radius: 6px; min-height: 32px; }
.ct-custom-option:hover { background: #f5f5f5; }
```

Active filter highlight: `border-color: var(--accent); color: var(--accent); background: rgba(179,82,179,0.07)` — `dashboard.html:1534`.

### Checkboxes

Custom checkbox using `.aim-ai-gen-card-cb` (15×15px square, `border-radius: 4px`). Unchecked: `border: 1.5px solid #d1d5db; background: #fff`. Checked: `background: var(--accent); border-color: var(--accent)`. No native checkbox visible; all replaced with custom renderings.

---

## 8. Cards and Surfaces

### Standard Card

```css
/* dashboard.html:322 */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg); /* 14px */
  box-shadow: var(--shadow);       /* 0 1px 2px rgba(0,0,0,0.05) */
  margin-bottom: 16px;
}
.card-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-light);
}
.card-body { padding: 16px; }
```

`.card-title`: `font-size: 13px; font-weight: 600`.
`.card-desc`: `font-size: 11px; color: var(--text-muted); margin-top: 1px`.

### Settings Card (elevated)

```css
/* dashboard.html:858 */
.aim-st-card {
  background: #fff; border: 1px solid var(--border); border-radius: 10px;
  padding: 24px; margin-bottom: 18px;
}
```

More padding than standard card, no explicit shadow.

### Shadow Scale (from `:root`)

| Token | Value |
|---|---|
| `--shadow` | `0 1px 2px rgba(0,0,0,0.05)` — card default |
| `--shadow-md` | `0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)` |
| `--shadow-lg` | `0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.05)` |
| `--shadow-xl` | `0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.05)` |

Modal shadow (not tokenized): `0 24px 64px rgba(0,0,0,.2)` — `dashboard.html:1122`.

### Modals / Overlays

All modals share: `border-radius: 16px`, `box-shadow: 0 24px 64px rgba(0,0,0,.2)`, `border: 1px solid var(--border)`. Overlay backdrop: `rgba(0,0,0,.4)` + `backdrop-filter: blur(4px)`.

Slide-in panel (Manage Brands): `transform: translateX(100%)` → `translateX(0)`, duration `.28s cubic-bezier(.4,0,.2,1)` — `dashboard.html:1820–1832`.

### Tooltips

CSS-only tooltip via `::after`:
```css
/* dashboard.html:2398 */
.aim-td-tip::after {
  background: #fff; border: 1px solid #e4e4e7; border-radius: 6px;
  padding: 4px 9px; font-size: 11px; font-weight: 400; color: #374151;
  box-shadow: 0 2px 8px rgba(0,0,0,.1); opacity: 0; transition: opacity .12s;
}
```

Chart tooltip (JS-rendered): same visual — white bg, `border: 1px solid var(--border)`, `border-radius: var(--radius-lg)`, `box-shadow: 0 4px 12px rgba(0,0,0,.1)` — `dashboard.html:1510`.

---

## 9. Tables

All tables share collapse behavior and a consistent pattern.

### Primary Table Pattern

```css
/* dashboard.html:330–341 */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th {
  text-align: left; padding: 8px 12px;
  font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .05em;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  background: var(--surface-alt);
  cursor: pointer; /* sortable */
}
thead th:hover { color: var(--text); }
tbody tr { border-bottom: 1px solid var(--border-light); transition: background .1s; }
tbody tr:hover { background: var(--surface-alt); }
tbody td { padding: 9px 12px; }
```

### Compact Table Pattern (`.aim-comp-table`, `.aim-full-table`)

Header: `font-size: 10px; letter-spacing: .06em; color: var(--text-faint); padding: 7–8px 12–18px`.
Row: `padding: 9–10px 12–18px`.

### Main brand row highlight

```css
tr.main-brand td, tr.is-main td {
  background: linear-gradient(90deg, rgba(248,200,255,0.08), transparent);
}
```

Subtle left-edge pink gradient for the user's own brand row — `dashboard.html:543`.

### Sort indicators

No custom CSS sort indicator. Sortable headers use `cursor: pointer` + `:hover` color. Sort direction is communicated by JS-injected content (not styled in CSS).

### Pagination

`.aim-page-btn`: 28×28px, `border-radius: var(--radius)`. Active: `background: var(--accent); color: #fff`. Disabled: `opacity: .4; cursor: not-allowed` — `dashboard.html:1079`.

---

## 10. Charts

All charts use Chart.js. No global `Chart.defaults` override was found — configuration is per-instance.

### Common Options (extracted from JS instances)

| Property | Value | Location |
|---|---|---|
| Responsive | `true` | All instances |
| `maintainAspectRatio` | `false` | All instances |
| Legend | `display: false` | Most charts (custom HTML legend instead) |
| Tooltip | `enabled: false`, custom external | Line charts use `aimMakeChartTooltip()` |
| Y grid color | `rgba(0,0,0,0.03–0.04)` | Very faint |
| X grid | `display: false` | Hidden on most charts |
| Tick font size | `11px` | `ticks: { font: { size: 11 } }` |
| Line tension | `0.4` (visibility), `0.35` (sources) | Slightly curved lines |
| Line border width | `2.5px` (main brand), `1.5–1.8px` (competitors) | |
| Point radius | `3–4px` (main), `2–3px` (others), `5px` on hover | |
| Line fill | `color + '18'` (10% alpha) | Area fill below line |

### Chart Types Used

| View | Chart type | Canvas ID |
|---|---|---|
| Overview — visibility trend | Line (multi-brand) | `aim-ov-chart` |
| Overview — sources | Donut | `aim-ov-donut` |
| Competitors | Horizontal bar (custom HTML) | None (CSS bars) |
| Sentiment | Donut + stacked bar + line trend | Various |
| Sources domain | Line + donut | `srLine`, `srDonut` |
| Search Console | Line (dual Y-axis) | `sc-perf` |

### Donut Chart Center

Custom HTML overlay positioned absolute inside `.aim-donut-wrap`: value at `font-size: 22px; font-weight: 700`, label at `font-size: 10px; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted)` — `dashboard.html:776`.

### Custom Tooltip

JS-rendered div `.aim-chart-tooltip` — white bg, `border-radius: var(--radius-lg)`, `box-shadow: 0 4px 12px rgba(0,0,0,.1)`, `min-width: 140px`. Row items use `.aim-ct-dot` (8px circle) and `.aim-ct-val` (bold).

---

## 11. Icons

**Icon set: Lucide** — all icons are inline SVG with Lucide paths, confirmed by comments (`<!-- lucide-sparkles -->`, `<!-- lucide-layout-dashboard -->` at `dashboard.html:2653–2665`).

**Rendering pattern:**
- `stroke="currentColor"` — inherits text color
- `stroke-width="2"`, `stroke-linecap="round"`, `stroke-linejoin="round"` — consistent across all icons
- `fill="none"` — outline only, never filled

**Nav icon sizing:** `width: 15px; height: 15px` (default), `width: 18px; height: 18px` (collapsed sidebar at ≤820px) — `dashboard.html:129, 1589`.

**Inline icon sizing in components:**
- Chart header export: 12×12px
- Table sort: 10×10px
- Topbar: 14px
- Nav items: 15px (expanded), 18px (collapsed)

**Opacity on nav icons:** Default `.nav-icon { opacity: .6 }`, active/hover `opacity: 1` — `dashboard.html:135`.

**Favicons / brand avatars:** `<img>` tags from `https://www.google.com/s2/favicons?domain=X&sz=32`. Fallback: single letter in a colored rounded rectangle using `var(--accent)` or brand-assigned color.

---

## 12. Effects

### Box Shadows

| Level | Value | Use |
|---|---|---|
| Default card | `0 1px 2px rgba(0,0,0,0.05)` | All `.card` |
| Dropdown | `rgba(0,0,0,.1) 0px 4px 6px -1px, rgba(0,0,0,.1) 0px 2px 4px -2px` | `.ct-custom-dropdown`, brand dropdown |
| Hover button | `0 10px 15px -3px rgba(0,0,0,.1), 0 4px 6px -4px rgba(0,0,0,.1)` | `.aim-topbar .aim-brand-trigger:hover` |
| Modal | `0 24px 64px rgba(0,0,0,.2)` | All overlays |
| User popover | `0 8px 24px rgba(0,0,0,.12), 0 2px 8px rgba(0,0,0,.06)` | `.aim-user-popover` |
| Active tab | `0 1px 2px rgba(0,0,0,.06)` | Tab pills |
| Toggle thumb | `0 1px 3px rgba(0,0,0,.2)` | All toggles |

### Transitions

All transitions are short and uniform:
- Interactive states (hover bg, border color): `.1–.15s` — no easing specified (defaults to `ease`)
- Button background: `.12s`
- Sidebar slide: `.25s cubic-bezier(.4,0,.2,1)` — Material Design standard easing
- Popover show/hide: `.15s ease` (opacity + translateY)
- Toggle thumb: `.15–.2s`
- Accordion panels: no transition (instant show/hide via `display`)

### Hover Effects

- Nav items: background fill (`#f9fafb`), color darkens
- Cards: no lift — shadow does not change on hover
- Topbar brand trigger: border darkens + subtle shadow appears
- Social icon links: border + color change to `--accent`
- Table rows: background `var(--surface-alt)`

### Focus Rings

All inputs: `border-color: var(--accent); box-shadow: 0 0 0 3px rgba(179,82,179,0.08–0.12)`.
No `outline` style set — relies on shadow only. This means the focus ring is not visible in Windows High Contrast mode (accessibility gap — see section 15).

### Animations

| Name | Duration | Use |
|---|---|---|
| `slideUp` | `.2s ease` | Floating action bar entrance |
| `aimIconGlow` | `9s linear infinite` | Ask AI hero icon glow pulse |
| `aimStateChat/Chart/Table` | `9s linear infinite` | Ask AI icon state cycling |
| `aimChartLineDraw` | `9s linear infinite` | Chart line draw in Ask AI |
| `aimPillIn` | — (one-shot) | Agent pill entrance |
| `aimFadeIn` | `.3s 1.75s ease forwards` | Thinking indicator delayed fade |
| `aim-pulse` | `2s infinite` | Active brand status dot |
| `aimDotPulse` | `.9s ease-in-out infinite` | Typing indicator dots |
| `spin` | — | Spinner (defined but usage not observed in CSS scan) |

---

## 13. Component Patterns

### Nav Sidebar Items (`dashboard.html:111–142`)

Vertical list inside `.sidebar`. Each `.nav-item` is `display: flex; align-items: center; gap: 9px; padding: 7px 10px; border-radius: 8px`. Active state uses a `2.5px` left border strip in `var(--accent)` via `::before`, positioned `top: 5px; bottom: 5px` so it doesn't run full height. Hover: `background: #f9fafb`. Section labels (`.section-label`) are all-caps, `font-size: 10px; letter-spacing: .08em`. Nav badges (`.nav-badge-beta`, `.nav-badge-new`) are 10px pill labels.

### Topbar / Brand Selector (`dashboard.html:1551–1545`)

The topbar is `position: sticky; top: 0; z-index: 20; height: 65px`. Its background is achieved via a `::before` pseudo-element (`rgba(255,255,255,0.97)` + blur) so child elements can layer above it without inheriting the backdrop filter. The brand trigger inside the topbar becomes a bordered button: `background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px; height: 36px`. Topbar filter dropdowns: `height: 30px; border-radius: 10px; font-size: 11px`. Brand logo inside topbar: 20×20px (vs 32×32px in sidebar).

### Score Cards / Metric Chips (`.aim-brand-metrics`, `dashboard.html:517–526`)

Inline pill chips: `display: flex; align-items: center; gap: 4px; padding: 4px 10px; background: var(--surface-alt); border: 1px solid var(--border); border-radius: 20px; font-size: 12px`. Label text is `--text-muted`, value is bold `--text`. These are placed in the topbar brand strip, not as separate full cards.

The competitor/overview cards use `.card` + chart canvas or custom bar rows — there is no dedicated "stat card" component for top-line KPIs (visibility %, sentiment %). Numbers appear inside `.aim-sent-stat-card` at `font-size: 24px; font-weight: 700`, with a label at `11px` below.

### Competitor Row Format (`dashboard.html:570–601`)

`.aim-comp-bar-row` is `display: flex; align-items: center; gap: 10px; padding: 7px 12px`. Contains: rank (`10px`, `--text-faint`), brand info area (fixed `172px` width, logo + name), progress bar track (7px tall, `var(--surface-alt)` bg, `border-radius: 4px`), and percentage value (`11px; font-weight: 600`). Sentiment bar is a three-segment flex row (positive/neutral/negative segments in green/gray/red). Main brand rows get the subtle pink gradient background wash.

### Ask AI Panel (`dashboard.html:2411–2632`)

Full-height view (`height: calc(100vh - 65px)`). Welcome state centers content with `align-items: center; justify-content: center; padding: 48px 32px`. Hero icon has a 9-second looping glow animation cycling through chat/chart/table icon states. Quick prompt buttons are `border-radius: 8px; padding: 8px 14px; border: 1px solid var(--border)` with a purple-tinted hover. Message input bar is sticky at bottom: `border-top: 1px solid var(--border); padding: 14px 20px`. User bubbles: gray (`#f3f4f6`) rounded `14px` with asymmetric corner. AI bubbles: surface-alt bg with `border: 1px solid var(--border-light)`. AI agent icon: 28×28px accent-colored square with `border-radius: 8px`.

### To-do / Action Plan Items (`dashboard.html:2285–2408`)

The action plan is implemented as a filterable table view ("To-do's"). Items use a standard table layout (`.aim-full-table`-style). Priority badges use numbered circle indicators (`.aim-td-step-num`): 20×20px colored circles with colorful bg/text combos per step index (indigo, blue, violet, green). Action buttons: `.aim-td-action-btn` (`padding: 6px 14px; border-radius: 7px; border: 1px solid var(--border)`). State variants: `.done` (green), `.added` (blue), `.archived` (orange). Completed rows get `opacity: .45` on `td` elements.

---

## 14. Naming Conventions

**Primary prefix:** `aim-` — stands for "AI Monitoring" (or similar). Applied to virtually every bespoke component class: `aim-brand-card`, `aim-comp-bar-row`, `aim-sent-badge`, `aim-topbar`, etc.

**Sub-namespace pattern:** `aim-{component}-{element}` — e.g. `aim-bd-` (brand dropdown), `aim-rm-` (response modal), `aim-st-` (settings), `aim-ap-` (add prompts modal), `aim-nb-` (new brand), `aim-mgr-` (manage brands panel), `aim-sc-` (search console), `aim-td-` (to-dos).

**Utility classes:** Minimal. `.col-left` for left-align table column. `.main-brand` / `.is-main` for table row state. `.active` / `.open` for toggled state. `.hidden` / `-hidden` suffix for JS-hidden elements.

**BEM-ish structure:** Yes, roughly. Component name → element name, no modifiers with `--`. Modifiers are separate classes (`.active`, `.selected`, `.done`, `.primary`, `.danger`).

**Legacy compat classes:** Some `.aim-brand-opt` entries exist with `display:none !important` — residue from a previous implementation (`dashboard.html:509–510`).

**No utility-class framework** (no Tailwind, no Bootstrap). All CSS is component-specific.

---

## 15. What's Missing or Inconsistent

**Three toggle implementations.** `.aim-toggle` (32×18), `.aim-rc-toggle` / `.aim-st-toggle` (42–44×24), and `.aim-ios-toggle` (36×20) all implement checkbox-style toggles with different markup patterns. There is no shared base. A porting agent should consolidate to one.

**Success/danger tokens are soft.** `--success` and `--danger` are defined at `:root` but large portions of the codebase use hardcoded equivalents (`#16a34a`, `#15803d`, `#b91c1c`, `#dc2626`) rather than the token. The tokens are not reliably used.

**No focus outline.** Focus states use `box-shadow` rings only, with no `outline` fallback. Fails in Windows High Contrast Mode and some accessibility tools. The `focus-visible` pseudo-class is not used anywhere.

**`--warning` token is unused.** Defined in `:root` as `#f59e0b` but warning UI uses `#d97706` or `#f59e0b` as inline values, never `var(--warning)`.

**Mixed border-radius values.** `:root` defines `--radius: 10px` and `--radius-lg: 14px` and `--radius-pill: 9999px`, but component CSS also uses `6px`, `7px`, `8px`, `9px` hardcoded (for inputs, dropdowns, table rows) without a token. At least five distinct radius values appear throughout.

**No loading/skeleton state CSS.** A `spin` keyframe is defined but there are no `.skeleton`, `.loading-shimmer`, or spinner component classes. Loading feedback is handled ad-hoc in JS.

**Font size below 10px.** Several micro-labels drop to `9px` and `9.5px`, which can fail WCAG SC 1.4.4 at non-ideal zoom levels and on low-DPI displays.

**Magic numbers in layout.** The topbar and sidebar logo area are both exactly `65px` tall — this is not tokenized, so if one changes the other must be manually updated.

**Chart JS tooltip vs CSS tooltip.** Two different tooltip systems exist side by side. The CSS-only `.aim-td-tip::after` tooltip and the JS-rendered `.aim-chart-tooltip` div have nearly identical visual specs but are separate implementations.

**Color duplication in AI_BRANDS.** Colors 7, 11 both use `#f59e0b` (amber), and colors 3, 12 both use `#2563eb` (blue). Intentional for representative demo data, but worth noting if the chart ever shows 11+ brands simultaneously.

---

## 16. Porting Notes for PeekABoo (Next.js + Tailwind)

### Colors → `tailwind.config.ts`

PeekABoo already has `peekaboo-pink` and `peekaboo-yellow`. The primary addition needed is the full token set:

```js
// tailwind.config.ts — theme.extend.colors
colors: {
  'peekaboo-pink':   '#f8c8ff',   // --brand-pink ✓ exists
  'peekaboo-yellow': '#ffcc45',   // --brand-yellow ✓ exists
  'peekaboo-purple': '#b352b3',   // --accent (NEW — add this)
  'peekaboo-purple-hover': '#a043a0', // --accent-hover (NEW)
  // Surface/neutral ramp
  surface:         '#ffffff',
  'surface-alt':   '#fafafa',
  'surface-hover': '#f4f4f5',
  border:          '#EEEEEF',
  'border-light':  'rgba(0,0,0,0.05)',
  // Text ramp
  'text-primary':  '#1c1917',
  'text-muted':    '#545D6C',
  'text-faint':    '#9CA3AF',
}
```

Keep Tailwind's built-in `emerald`, `blue`, `violet`, `cyan`, `amber`, `pink`, `sky`, `slate` for chart colors — they map directly to the `AI_BRANDS` sequence.

### Typography → `theme.extend.fontFamily`

```js
fontFamily: {
  sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
}
```

Inter is already widely used. The dashboard loads weights 300–800; Tailwind's default `font-sans` is fine as-is once the family is set. Keep Tailwind's default type scale — the dashboard's sizes (10px, 11px, 12px, 13px, 14px) map roughly to Tailwind's `text-xs` (12px), `text-sm` (14px), `text-base` (16px) but the dashboard skews smaller. Add a custom size if needed:

```js
fontSize: {
  '2xs': ['10px', { lineHeight: '1.5' }],
  '3xs': ['9px',  { lineHeight: '1.5' }],
}
```

### Spacing → Keep Tailwind Defaults

Tailwind's 4px base unit matches the dashboard's spacing rhythm. No custom spacing tokens needed. Use `p-3` (12px), `p-4` (16px), `p-6` (24px), `p-7` (28px) as the page structure cadence.

### Shadows → `theme.extend.boxShadow`

```js
boxShadow: {
  card:   '0 1px 2px rgba(0,0,0,0.05)',
  modal:  '0 24px 64px rgba(0,0,0,0.2)',
  popover:'0 8px 24px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)',
}
```

### Border Radius → `theme.extend.borderRadius`

```js
borderRadius: {
  card: '14px',   // --radius-lg
  comp: '10px',   // --radius
  pill: '9999px', // --radius-pill
}
```

### Components → shadcn/ui Mapping

| Dashboard component | shadcn/ui equivalent | Notes |
|---|---|---|
| `.card` / `.card-header` / `.card-body` | `Card`, `CardHeader`, `CardContent` | Match border + shadow token |
| Custom select (`.ct-custom-select`) | `Select` (Radix) | Replace entirely — shadcn is superior |
| Toggle (3 variants) | `Switch` | Consolidate to one; use `#22c55e` for on-state |
| Modal / overlay | `Dialog` | Match `border-radius: 16px`, blur backdrop |
| Slide panel | `Sheet` | Match `.25s cubic-bezier(.4,0,.2,1)` transition |
| Tabs (`.aim-tab-bar`) | `Tabs` | Set `bg-surface-alt` on trigger container |
| Pagination | `Pagination` | Match 28×28px sizing, accent active |
| Search input | `Input` + icon wrapper | Use `rounded-full` + left icon |
| Badge / pill | `Badge` | Map all badge color variants |
| Tooltip | `Tooltip` (Radix) | Replace both CSS + JS implementations |

### Charts → Recharts vs Chart.js

PeekABoo should evaluate: Recharts integrates better with React state and server components but has a steeper learning curve for custom tooltips. Chart.js (via `react-chartjs-2`) is a direct 1:1 port of the reference — all existing chart configs can be migrated with minimal changes. **Recommendation:** if Recharts is already in PeekABoo, keep it. If starting fresh, use Chart.js for fidelity.

For chart theming, set the following on each chart instance (not via global defaults, matching the reference pattern):
- `grid.color: 'rgba(0,0,0,0.03)'` on Y axis
- `grid.display: false` on X axis
- `ticks.font.size: 11`
- Custom tooltip via `external` callback

### What to Bring Over Verbatim

- The `AI_BRANDS` color sequence (first 6 colors) as a `chartColors` config array
- The `--accent` → `--accent-hover` two-step (already partially in PeekABoo as `peekaboo-purple`)
- The topbar `::before` pseudo-element frosted-glass pattern
- The main brand table row gradient: `linear-gradient(90deg, rgba(248,200,255,0.08), transparent)`
- The active nav item left-border indicator (2.5px, accent color, inset 5px top/bottom)
- Section label style: 10–11px, 600 weight, uppercase, `letter-spacing: .06–.08em`

### What to Adapt

- Consolidate the three toggle variants → single shadcn `Switch`
- Replace custom select dropdowns → shadcn `Select` (Radix-powered, accessible)
- Add `focus-visible` outlines in addition to box-shadow rings (accessibility fix)
- Tokenize success/danger fully — eliminate hardcoded hex variants in component files
- Normalize border-radius: pick `--radius` (10px) and `--radius-lg` (14px) and enforce

### What to Leave Behind

- The `aim-` prefix — PeekABoo should use its own naming or shadcn component names
- The inline JS-rendered tooltips — use Radix `Tooltip` primitive
- The CSS-only toggle implementations — use shadcn `Switch`
- The `3xs` font sizes (9–9.5px) — too small for reliable accessibility; use `text-xs` (12px) minimum
- The multiple bespoke tab implementations — standardize on shadcn `Tabs`

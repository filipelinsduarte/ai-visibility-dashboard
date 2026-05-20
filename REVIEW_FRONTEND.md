# Frontend Review: `dashboard.html`

A performance, accessibility, DOM-write, render-lifecycle, and event-wiring teardown of the same 17,800-line single-HTML file covered structurally in `REVIEW_ARCHITECTURE.md`. This review adds what the architecture review deliberately skipped: the browser-facing costs. Junior dev is the target reader; every section ends with a "Why this matters in general" callout.

**Reading order**: read `REVIEW_ARCHITECTURE.md` first. This document references its findings by section but does not repeat them.

---

## 1. Loading & Runtime Performance

### The numbers

- **File on disk**: 16 MB. After gzip (typical server default, compression ratio ~8:1 for JSON+JS), the wire size is roughly 2 MB. That alone is not fatal.
- **The real problem is what is inside those 2 MB**: the entire `_AIM_SNAPSHOT` JSON blob — real production data including 180 prompt runs, 38 prompt texts, full source URL labels averaging several hundred characters each — is injected inline at `dashboard.html:5214`. This is not a small config object; it is the entire database export for one brand. At render time, the browser parses and garbage-collects a huge JS object graph before drawing pixel one.
- **Chart.js CDN**: `dashboard.html:18-19` loads `chart.js@4.4.0` (≈170 KB minified) and `chartjs-plugin-datalabels@2.2.0` (≈18 KB) from jsDelivr, both as render-blocking `<script>` tags with no `defer` or `async`. This adds two synchronous network round-trips to the critical path. On a fast connection these resolve in under 100 ms. On a flaky 4G connection they can stall First Contentful Paint by 400–800 ms.
- **The main `<script>` block**: `dashboard.html:5215–15674` (~10,460 lines). The browser's HTML parser must complete the full `<style>` block (2,613 lines of CSS), then parse and compile ~10,460 lines of JavaScript before `DOMContentLoaded` fires and any rendering begins. On a mid-range mobile device, V8's parse-and-compile time for a cold 10K-line script is typically 200–600 ms. Combined with snapshot JSON parsing, a realistic Time to Interactive on a budget Android is 3–5 seconds even before accounting for network.

### Three fixes ranked by ROI

**Fix 1 (highest ROI): Add `defer` to the Chart.js CDN tags.**

```html
<!-- dashboard.html:18 — current -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

<!-- proposed -->
<script defer src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
```

`defer` tells the browser to download in parallel with HTML parsing and execute only after the document is parsed, eliminating the render-blocking stall without changing execution order. One attribute change. No refactoring. Estimated FCP improvement: 200–600 ms on real connections.

**Fix 2 (medium ROI): Lazy-load the snapshot JSON.**

The snapshot is injected as `window._AIM_SNAPSHOT = { ... };` at `dashboard.html:5214`. At 16 MB total file size with inline JSON, the parser hits this payload before it ever sees the main `<script>` block. The cleanest alternative without changing the "single HTML file" constraint: move the snapshot to a separate `<script src="snapshot.json.js">` tag loaded at the bottom of `<body>` with `defer`. This lets the parser reach `DOMContentLoaded` without blocking on JSON parse. If a separate file is truly not allowed, at minimum wrap the snapshot injection in a `requestIdleCallback` or `setTimeout(fn, 0)` so the first paint is not blocked. Estimated TTI improvement: 100–400 ms depending on snapshot size.

**Fix 3 (lower ROI but important for reliability): Add a `<link rel="preconnect">` for jsDelivr.**

```html
<!-- add after the existing Google Fonts preconnect at dashboard.html:15-16 -->
<link rel="preconnect" href="https://cdn.jsdelivr.net">
```

jsDelivr is a separate origin. Without a preconnect hint, the browser opens a cold TCP+TLS handshake at the moment it encounters the `<script>` tag. A preconnect instructs it to start that handshake immediately during HTML parse. On CDN: saves ~50–150 ms of connection overhead per CDN origin. Small gain but zero implementation cost.

> **Why this matters in general**: loading performance is not about file size alone — it is about which bytes block which other bytes. The difference between a render-blocking `<script>` and a `defer`-ed one is one attribute, but the user-visible difference can be hundreds of milliseconds. Always ask: "does this resource need to exist before the first pixel paints?"

---

## 2. Accessibility Audit

Three views sampled: Overview, Competitors, Sources. Each scored 0–5 on five axes. 5 = fully compliant, 0 = completely broken.

### Overview view

| Axis | Score | Notes |
|---|---|---|
| Keyboard navigation | 2/5 | Nav items at `dashboard.html:2652-2707` are `<div>` elements with `onclick`, not `<button>` or `<a>`. Keyboard users cannot Tab to them at all. |
| Focus indicators | 2/5 | CSS at `dashboard.html:119-147` shows `nav-item` hover styles but no `:focus-visible` rule. Focus outline is browser default only; may be suppressed by `outline:none` resets elsewhere. |
| ARIA / semantics | 2/5 | `<aside class="sidebar">` at `dashboard.html:2646` is correct; `<main class="main">` at `dashboard.html:2737` is correct. However the nav list inside `<aside>` has no `<nav>` landmark or `aria-label`. Chart `<canvas>` elements at `dashboard.html:2752,2781` have no `aria-label` or `role="img"` — screen readers see nothing. |
| Color contrast | 3/5 | Primary text `#1c1917` on `#ffffff` passes WCAG AA. `var(--text-muted)` (`#6b7280`) on `#ffffff` is approximately 4.6:1 — passes AA for normal text. `var(--text-faint)` used throughout for secondary data is likely below 3:1 on white — needs a contrast meter to confirm but visually it is very light. |
| Screen-reader table friendliness | 3/5 | Competitors table at `dashboard.html:2765` has `<thead>/<tbody>` and text column headers — correct. But the `#` column header is just `#`, which a screen reader announces as "hash" or "number sign." Should be "Rank". |

### Competitors view

| Axis | Score | Notes |
|---|---|---|
| Keyboard navigation | 1/5 | Pagination buttons `#aim-comp-prev` and `#aim-comp-next` at `dashboard.html:2759-2761` are `<button>` elements (correct). However the entire heatmap, sentiment split bars, and the per-competitor row grid are `<div>` soup — zero tab stops for the data itself. |
| Focus indicators | 1/5 | No `:focus-visible` styles found in the CSS audit. Buttons that happen to be real `<button>` elements get the browser default, which Chrome suppresses on click. Tab users see nothing. |
| ARIA / semantics | 1/5 | The sentiment split visual at `dashboard.html:2987-2994` is a `<table>` with no `<caption>` and column headers that just read "Sentiment Split", "Visibility", "Mentions". No units, no context. The "What AI models think" column contains icon-only content with no text alternative. |
| Color contrast | 3/5 | Same as Overview. Sentiment badge colors are defined dynamically — positive/negative hues need contrast verification against both white and the badge background. |
| Screen-reader table friendliness | 2/5 | The heatmap rendered by `aimRenderCompHeatmap` (referenced in `REVIEW_ARCHITECTURE.md:64`) produces a `<div>` grid, not a `<table>`, meaning screen readers cannot navigate it by row/column. The underlying data is genuinely tabular. |

### Sources view

| Axis | Score | Notes |
|---|---|---|
| Keyboard navigation | 2/5 | Tab/topic filter buttons at `dashboard.html:3072-3073` are real `<button>` elements. The domain table rows are just `<tr>` — no way to activate the row actions by keyboard. |
| Focus indicators | 2/5 | Same issue as other views. |
| ARIA / semantics | 2/5 | Sort-able column headers at `dashboard.html:3133-3135` use `onclick` but have no `aria-sort` attribute — screen readers cannot tell users the current sort order or that the column is sortable. |
| Color contrast | 3/5 | Same as Overview. |
| Screen-reader table friendliness | 4/5 | The domains table at `dashboard.html:3132` is a proper `<table>` with `<thead>` and text headers. Best of the three views. Still missing `<caption>`. |

### Worst offenders

**`dashboard.html:2652-2707`** — Every nav item is a `<div>` with `onclick`. This is the single highest-impact a11y bug: keyboard-only users and screen-reader users cannot navigate the app at all. Fix is straightforward: replace `<div class="nav-item" onclick="showView('...')">` with `<button class="nav-item" onclick="showView('...')">` and add `:focus-visible` CSS. The sidebar already has `<aside>` — wrap the nav items in `<nav aria-label="Main navigation">`.

**`dashboard.html:2752,2781,3081,3088,3160,3167,3554`** — Seven `<canvas>` elements have no accessible alternative. Chart.js 4.x supports `aria-label` on the canvas and renders a fallback `<table>` inside the canvas element via its `plugins.accessibility` option or the `aria-label` attribute. Add `aria-label="Visibility trend chart"` (or equivalent) to each. This is a one-attribute fix per chart.

**`dashboard.html:6885`** — The one instance of `role="button" tabindex="0"` (a `<div>` opened as a modal row) has no `onkeydown` handler for `Enter`/`Space`. A keyboard user who Tabs to it and presses `Enter` gets nothing. Fix: add `onkeydown="if(event.key==='Enter'||event.key===' ')aimOpenResponseModal(...)"` alongside the existing `onclick`.

**`dashboard.html:7400-7490`** — `aimOpenResponseModal` sets `modal.style.display = 'flex'` but never moves focus into the modal. `aimCloseResponseModal` hides the modal but never returns focus to the triggering element. Users who open the modal via keyboard are stranded at the top of the document when it closes. Minimum fix: `modal.querySelector('button').focus()` on open; store and restore the opener element's reference on close.

> **Why this matters in general**: accessibility bugs compound. A non-focusable nav means keyboard users cannot reach any view. A chart with no text alternative means screen-reader users get no data at all. Fix the structural problems first (nav, modals) before fixing the cosmetic ones (contrast ratios). The structural ones exclude entire user categories; the cosmetic ones just make things harder.

---

## 3. State & DOM-Write Patterns

The architecture review (`REVIEW_ARCHITECTURE.md:62-68`) documents the global-read / innerHTML-write pattern across all 37 `aimRender*` functions. This section adds the three frontend-specific failure modes.

### Problem 1: Index mutation on a sized array

**`dashboard.html:12580`**:
```js
if (AIM_VIS_BY_MODEL[dKey])  AIM_VIS_BY_MODEL[dKey][0]  = v;
if (AIM_SENT_BY_MODEL[dKey]) AIM_SENT_BY_MODEL[dKey][0] = s;
```

`AIM_VIS_BY_MODEL` is a seeded array (e.g., `AIM_VIS_BY_MODEL.chatgpt = [72, 68, 65, 71, 70, 69, 73]`). Writing to `[0]` mutates index zero of that seed array in place. If `aimApplySnapshot` is called twice — which can happen via `aimApplyInjectedData` at `dashboard.html:13325` plus a user-triggered brand switch — the first value is overwritten but indices 1–6 retain stale seed data. Any chart that reads the full array now mixes real data at `[0]` with fake data at `[1-6]`. The downstream `aimRenderVisibilityChart` at `dashboard.html:6524` reads the entire array; the chart silently plots a hybrid of real and fake history.

**Fix**: do not mutate `[0]` of an array that has semantic meaning at every index. Instead, `aimApplySnapshot` should rebuild the entire per-model arrays from snapshot data: `AIM_VIS_BY_MODEL[dKey] = buildModelSeries(snap, dKey)`. That is one assignment, zero side-effects on the other indices.

### Problem 2: Unguarded getElementById followed by innerHTML

**`dashboard.html:6636`**:
```js
function aimRenderCompetitorsTablePage() {
  const tbody = document.getElementById('aim-comp-tbody');
  const rangeEl = document.getElementById('aim-comp-range');
  if (!tbody) return;
  // ... builds html ...
  tbody.innerHTML = competitorRows + mainBrandRow;
```

`tbody` is guarded; `rangeEl` at line 6637 is not — if `aim-comp-range` is absent (e.g., during a view transition or after a hot-reload of the topbar via `aimRenderTopbar`'s own `el.innerHTML` at `dashboard.html:6184`), the `rangeEl.textContent = ...` at line 6655 throws a `TypeError` and the function exits mid-render, leaving the table in whatever partial state it was in.

**Fix**: a thin helper that fails safely and consistently:

```js
function renderInto(id, html) {
  const el = document.getElementById(id);
  if (!el) { console.warn('[AIM] renderInto: missing element #' + id); return false; }
  el.innerHTML = html;
  return true;
}
function textInto(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}
```

Replace every `el.innerHTML = html` pattern with `renderInto(id, html)` and every optional `el.textContent = x` with `textInto(id, x)`. The helpers are ten lines total. They eliminate the inconsistent guard pattern across 131 `innerHTML` sites, they make missing-element bugs visible in the console rather than silent, and they reduce the cognitive load of every future author who writes a new render function.

### Problem 3: `aimRenderTopbar`'s own innerHTML nukes live event listeners

**`dashboard.html:6184`**:
```js
el.innerHTML = `...`; // replaces entire #aim-topbar content
```

`aimRenderTopbar` is called 20+ times across the codebase (from `initAiOverview`, `initAiCompetitors`, `showView`, filter changes, etc.). Each call sets `el.innerHTML` on `#aim-topbar`, which destroys and recreates all child DOM nodes. Any live event listeners attached to topbar children (not inline `onclick` attributes, but `addEventListener` calls like the brand-dropdown close handler at `dashboard.html:13305`) are silently discarded. The inline `onclick` attributes survive because they are re-serialized into the new HTML string — but this means the topbar cannot ever use `addEventListener`-based wiring for its interactive elements without those listeners dying on the next render call. The codebase works around this by using only inline `onclick` in the topbar, which is why the `onclick` count is 442.

**Fix**: the minimal-disruption pattern is to give topbar sub-regions their own stable IDs and only re-render the parts that actually changed. A brand-name label can update via `textInto('aim-topbar-brand-label', name)` without rebuilding the entire topbar. This is a targeted refactor of `aimRenderTopbar` only, not all 37 render functions.

> **Why this matters in general**: `innerHTML` on a container is a sledgehammer. It is fine for leaf nodes that have no children with event listeners. It is dangerous for any container whose children have been wired with `addEventListener`. The rule of thumb: if a container's children ever receive `addEventListener`, give those children stable IDs and update them individually; do not rebuild the parent.

---

## 4. Render Lifecycle Robustness

### The current boot sequence

**`dashboard.html:13294-13326`**:
```js
document.addEventListener('DOMContentLoaded', () => {
  aimRenderTopbar();           // line 13295 — throws → everything below is skipped
  document.addEventListener(   // line 13297 — brand manager
  document.addEventListener(   // line 13305 — dropdown close
  showView('ai-overview');     // line 13313 — view init
  aimApplyColTips();           // line 13315
  new MutationObserver(...)    // line 13318
  if (window._AIM_SNAPSHOT) {
    aimApplySnapshot(...)      // line 13321 — real data applied
  }
  if (window.AIM_INJECTED_DATA) aimApplyInjectedData(); // line 13325
});
```

If `aimRenderTopbar()` at line 13295 throws — which it did during the repair session this file documents — the entire callback exits. `showView` never fires. `aimApplySnapshot` never fires. The dashboard renders a blank page with no data and no nav. This is the exact failure mode you just recovered from.

Is the ordering defensible? No. `aimApplySnapshot` is the most important step — it populates the data the rest of the views depend on. It is currently last. `aimRenderTopbar` is a cosmetic chrome component. It is currently first. The priority is backwards.

### Three minimal changes to make boot self-healing

**Change 1: Wrap each step in a `try/catch`.**

```js
document.addEventListener('DOMContentLoaded', () => {
  const _boot = (label, fn) => {
    try { fn(); }
    catch(e) { console.error('[AIM] boot step failed:', label, e); }
  };
  _boot('applySnapshot', () => {
    if (window._AIM_SNAPSHOT) aimApplySnapshot(window._AIM_SNAPSHOT);
  });
  _boot('applyInjectedData', () => {
    if (window.AIM_INJECTED_DATA) aimApplyInjectedData();
  });
  _boot('renderTopbar', aimRenderTopbar);
  _boot('showView',     () => showView('ai-overview'));
  _boot('colTips',      aimApplyColTips);
  _boot('mutationObs',  () => { /* MutationObserver setup */ });
});
```

A throw in any one step logs the error and continues. No step can take down the dashboard. This is six lines of wrapper code.

**Change 2: Move `aimApplySnapshot` before `aimRenderTopbar`.**

`aimRenderTopbar` reads `window._AIM_SNAPSHOT.all_brands` at line `dashboard.html:6081`. If the snapshot is applied first, topbar gets real brand data on its first render. Currently topbar renders with seed data, snapshot applies, then something re-calls topbar to update. Swap the order: apply data first, render UI second. One line change in the boot sequence.

**Change 3: Add a no-data fallback state in `aimRenderTopbar`.**

Currently `aimRenderTopbar` at `dashboard.html:6078-6225` silently renders with whatever is in `AIM_WORKSPACES[0]` (fake seed data). If `aimRenderTopbar` were to check `if (!window._AIM_SNAPSHOT && !window.AIM_INJECTED_DATA)` and render a lightweight skeleton or "Loading data..." placeholder instead, the page would show something meaningful even when the snapshot is missing or delayed. This is defensive coding, not a complete fix — but it gives operators a visible signal rather than a broken-looking page.

> **Why this matters in general**: initialization code is the highest-leverage code in any application. A throw anywhere in a top-level `DOMContentLoaded` callback with no error handling kills the entire app. The pattern of wrapping each step with a named `try/catch` is cheap, makes debugging trivial (the console log names which step failed), and keeps every other step alive. Use it any time you have a sequential boot with more than two steps.

---

## 5. Inline Event Handlers

### The count

```
442 onclick= attributes in dashboard.html
```

Confirmed by `grep -c 'onclick=' dashboard.html`. The architecture review (`REVIEW_ARCHITECTURE.md:14`) cites this number. This section explains the specific frontend costs.

### Why 442 inline handlers is a real problem, not just style

**CSP incompatibility**: Content Security Policy `script-src 'self'` — the industry standard for XSS mitigation — blocks all inline event handlers. Every `onclick="fn()"` is an inline script. Any future attempt to add a CSP header to this dashboard requires rewriting all 442 handlers simultaneously. Today there is no CSP at all (confirmed: no `<meta http-equiv="Content-Security-Policy">` tag and no `Content-Security-Policy` header pattern in the file). The 442 handlers are technical debt against that future improvement.

**Escaping failures**: handlers like `dashboard.html:6885` generate `onclick` attributes dynamically:
```js
return `<div ... onclick="aimOpenResponseModal('${escapedModel}','${isoDate}',${promptNumericId},'${storeKey}')">`;
```
`aimEscHtml` escapes for HTML body context (replaces `<`, `>`, `&`, `"`, `'`). But `onclick` attribute values are JS string literals — a model name like `Google's AI` would need JS-string escaping (`\'`), not HTML escaping. A brand or model name containing a single quote will break the JS expression inside the attribute. `aimEscHtml` at `dashboard.html:5807` does escape `'` to `&#39;`, which happens to be safe inside HTML attributes but is not the same as proper JS string escaping. This is a narrow escape (pun intended) that works until someone adds a brand name with a backslash.

**No central listener registry**: with 442 inline handlers, there is no way to audit "which elements respond to clicks" without reading every line of HTML. With delegated listeners, a single `document.addEventListener('click', handler)` can log or intercept all interactions — useful for analytics, debugging, and testing.

**Testability**: you cannot programmatically assert that clicking a nav item calls `showView('ai-overview')` without a full browser environment. With delegated listeners and a central dispatch table, you can test the dispatch table in isolation.

### Two-step migration that does not require rewriting all 442 at once

**Step 1: Add one delegated listener and a data-attribute protocol.**

Add to the boot sequence (after the existing `document.addEventListener('click', ...)` blocks at `dashboard.html:13305`):

```js
document.addEventListener('click', function(e) {
  const btn = e.target.closest('[data-aim-action]');
  if (!btn) return;
  const action = btn.dataset.aimAction;
  const args = btn.dataset.aimArgs ? JSON.parse(btn.dataset.aimArgs) : [];
  const fn = window[action];
  if (typeof fn === 'function') fn(...args);
}, false);
```

**Step 2: Migrate handlers view-by-view, not all at once.**

As you work on each view file (per the `src/views/*.js` plan in `REVIEW_ARCHITECTURE.md:§3`), convert that view's inline handlers to `data-aim-action`. For example:

```html
<!-- before -->
<button onclick="showView('ai-overview')">Dashboard</button>

<!-- after -->
<button data-aim-action="showView" data-aim-args='["ai-overview"]'>Dashboard</button>
```

The old `onclick` and the new `data-aim-action` can coexist during migration — the delegated listener only fires when `data-aim-action` is present. You convert one view, verify it, commit, move to the next. At no point is the dashboard half-broken. When all 442 are migrated, remove the delegated listener and the old inline handlers. This is a view-by-view migration that takes weeks, not a big-bang rewrite that takes days and breaks everything.

The `data-aim-args` JSON pattern handles simple argument passing. For handlers that pass complex computed values (like the `storeKey` in `aimOpenResponseModal` at `dashboard.html:6885`), the element can store a lookup key in `data-aim-args` and the function retrieves the full object from a store — the same pattern already used for `window._aimChatStore`.

> **Why this matters in general**: inline event handlers couple markup to behavior in a way that makes both harder to read and neither testable in isolation. Delegated listeners are the standard DOM pattern for applications that render large lists of interactive elements — they also perform better because they attach one listener instead of N. The migration does not have to be atomic; "replace one view's handlers, verify, ship" is a valid strategy and the only safe one in a codebase this size.

---

## Summary: Priority Order

| Priority | Finding | File:Line | Fix cost |
|---|---|---|---|
| 1 | Nav items are non-focusable `<div>` elements — keyboard users cannot navigate the app | `dashboard.html:2652-2707` | Replace 10 `<div>` with `<button>`, add `<nav>` wrapper, add `:focus-visible` CSS |
| 2 | Boot sequence: one throw kills everything; snapshot applied last, topbar first | `dashboard.html:13294-13326` | Wrap in `_boot()` helpers, swap snapshot/topbar order — ~20 lines |
| 3 | CDN scripts are render-blocking | `dashboard.html:18-19` | Add `defer` — 2 attributes |
| 4 | Modal opens without focus move; closes without focus return | `dashboard.html:7400-7491` | Add `focus()` on open, save/restore opener on close — ~5 lines |
| 5 | Chart `<canvas>` elements have no accessible label | `dashboard.html:2752,2781,3081,3088,3160,3167,3554` | Add `aria-label` — 7 attributes |
| 6 | `AIM_VIS_BY_MODEL[dKey][0] = v` mixes real and seed data | `dashboard.html:12580` | Rebuild full array instead of patching index 0 |
| 7 | No `renderInto` / `textInto` guard helpers — 131 raw `innerHTML` sites | Whole script block | Add 2 helper functions, adopt incrementally |
| 8 | 442 inline `onclick` handlers block CSP adoption | Whole HTML body | Two-step delegated-listener migration, view-by-view |

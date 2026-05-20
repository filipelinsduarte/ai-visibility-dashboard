# Teardown: ai-visibility-dashboard

> One-page synthesis of two deep reviews. Read this first. Branch: `fix/restore-missing-declarations`.

## What we did

After repairing the dashboard (2 syntax errors + 13 missing top-level declarations — see the "Debugging log" section in `README.md`), we ran two reviews to understand *why* it broke so badly and what to do about it:

- **`REVIEW_ARCHITECTURE.md`** — KISS, SOLID, separation of concerns, TDD strategy. Lead-architect's view.
- **`REVIEW_FRONTEND.md`** — Loading perf, a11y, state/DOM patterns, render lifecycle, inline-handler sprawl. Lead-frontend's view.

This doc is the top-level summary. Use it as the index; drill into the two deeper docs for evidence and line numbers.

---

## The one-sentence diagnosis

> **A 17,000-line file with one global namespace, no test runner, no module boundaries, no build step, and 442 inline `onclick` handlers will eventually decay the same way this one did — silently losing declarations during refactors and shipping `SyntaxError`s to production.** The recent repair session is a symptom, not a root cause.

---

## Top 5 takeaways (what a junior dev should remember)

### 1. Single-file + single-global-namespace = fragility multiplier

Everything in `dashboard.html` shares one namespace. `AI_BRANDS`, `AIM_WORKSPACES`, `aimSelectedWorkspaceId` were declared *once*, mutated *many times*, and one bad refactor silently removed all three declarations. A static analyzer that only looks for `X = …` couldn't see them being "used," so it pruned them.

**The lesson**: when variables are populated by **mutation** rather than **reassignment**, static analysis can't see they're load-bearing. Either (a) make them clearly assigned, or (b) move them behind a module boundary that survives refactor passes.

### 2. SRP at the file level matters as much as at the function level

`dashboard.html` does ~10 jobs: HTML structure, CSS, snapshot injection, boot, 7 views, todos engine, modals, event wiring. Any change to any of those means editing the same file. Two collaborators editing simultaneously will conflict.

`aimGenerateTodos` is *1,270 lines long inside one function* (`dashboard.html:14522`). `aimApplySnapshot` is 647 lines and mixes parse + mutate + DOM-write + re-render (`dashboard.html:12556`).

**The lesson**: "one file is simpler" stops being true around 2,000 lines. Past that, you've just hidden the complexity from yourself.

### 3. `SyntaxError` is the hardest bug to debug because every other error disappears

Two missing close-parens (`dashboard.html:6987` and `:16954`) killed the entire script. None of the 17K other lines ran. The user saw a blank dashboard, but the actual cause was 2 characters of source.

**The lesson**: when a page is blank, open DevTools → Console first. Fix `SyntaxError` and `ReferenceError` before reading anything else; everything else is downstream noise.

### 4. Inline `onclick=` handlers are the single worst pattern in this codebase

442 inline handlers (`onclick="aimDoThing()"`). Each one:
- Can't be added/removed without editing the HTML string
- Breaks under any `Content-Security-Policy: script-src 'self'` header (silently — all 442 die together)
- Can't be tested without a real DOM
- Re-fires on every `el.innerHTML = ...`, leaking subtle bugs
- Has its own escaping rules (HTML-attr context vs JS-string context) that the codebase mixes inconsistently — see `dashboard.html:6885`

**The lesson**: event delegation (one listener at `document`, dispatch via `data-action` attributes) gives you the same ergonomics with zero of the downsides. It's a 10-line helper.

### 5. Untestable code rots — and you don't notice until it breaks in production

There's no Vitest, no Jest, no Playwright. There can't be — `dashboard.html` exports nothing. The functions live inside `<script>` and reference each other through shared globals.

This is the *direct cause* of the bug we fixed: an automated refactor pruned 13 declarations, and there was no test to scream when boot started failing. Manual QA caught it eventually, but only because someone opened the dashboard and saw it was blank.

**The lesson**: untested code isn't a luxury problem — it's the reason silent regressions ship. The cost of *one* failing test (any test) is far lower than the cost of one production "the dashboard is blank" incident.

---

## What to do, ranked by ROI

The two deeper reviews agree on roughly the same priority order. Consolidated:

### Do this week (≤1 day each)

1. **Add `defer` to both Chart.js script tags** at `dashboard.html:18-19`. Two characters, 200–600 ms FCP improvement on real connections.
2. **Set up Vitest** (lighter than Jest, native ESM, no Babel). Write the first 5 tests around the pure functions identified in `REVIEW_ARCHITECTURE.md` section 4 — start with `aimEscHtml`, `_normBN`, `aimEvenlySample`.
3. **Wrap the boot sequence in a `_boot()` function with named try/catch per step**, so one throw in `aimRenderTopbar` doesn't kill `aimApplySnapshot`. See `REVIEW_FRONTEND.md` section 4.
4. **Dedup the 11 redeclarations of the provider-key map** (`AIM_PROVIDER_KEYS`). Pick one, use it everywhere.

### Do this quarter

5. Extract 4–6 modules into `src/` and add a 30-line `scripts/build.sh` that concatenates them back into one HTML deliverable. The single-file constraint stays; the developer experience improves. See `REVIEW_ARCHITECTURE.md` section 3.
6. Add `tabindex="0"` + keyboard handlers to nav items at `dashboard.html:2652-2707`. The app is currently keyboard-unusable.
7. Build a `data-aim-action` event-delegation listener at `document` and migrate inline `onclick=` view-by-view. Both reviews agree on this. Do NOT try to convert all 442 in one PR — that's how you break everything at once.
8. Add `aria-label` to every `<canvas>` chart.
9. Split `aimApplySnapshot` into parse → store → render. 647-line functions are not maintainable.

### Never

- **Don't rewrite this in React/Next.js/TypeScript.** The deliverable constraint is "one HTML file works without a server." That constraint is more important than any framework win.
- **Don't sweep all 442 inline handlers in one pass.** Recipe for another repair session.
- **Don't restructure for hypothetical multi-brand-tenancy or theming.** YAGNI. The existing workspace system already handles it.

---

## TDD: where to start tomorrow

From `REVIEW_ARCHITECTURE.md` section 4:

1. **Install Vitest + happy-dom**: `npm init -y && npm i -D vitest happy-dom`
2. **Extract 6 pure functions** to `src/lib/` (no DOM, no globals): `aimEscHtml`, `_normBN`, `aimEvenlySample`, `aimFmtDate`, `aimSentimentLabel`, `aimGetBrandMetrics`.
3. **Write these 5 tests first**:
   - `aimEscHtml escapes `<`, `>`, `&`, `"`, `'` correctly`
   - `_normBN treats "Otterly.AI" === "OtterlyAI" === "otterly ai"`
   - `aimEvenlySample picks endpoints + spaced interior` (the dashboard's date-axis logic depends on this)
   - `aimGetBrandMetrics returns 0 visibility for a brand with no mentions` (the bug-magnet edge case)
   - `_AIM_SNAPSHOT shape matches expected schema` (a smoke test that fails fast if `generate_snapshot.py` regresses)

Why these five? They're the functions where a bug would silently corrupt every chart on the page. Catching them at unit-test speed (ms) beats finding them at "user opens dashboard" speed (days).

---

## How to read the rest of this material

- Start: **this file** (you're here).
- First: **`SETUP.md`** if you haven't actually got the dashboard running locally yet.
- Then: **`README.md` → "Debugging log"** for the worked example of the recent fix.
- Then: **`STYLE_GUIDE.md`** for the complete extracted design system (colors, type, spacing, components, chart palette, porting notes to React/Tailwind).
- Then: **`COMPONENT_STRUCTURE.md`** for the rules behind when to extract anything (the *why*, not the *what*).
- Then: **`TDD_PHILOSOPHY.md`** for testing strategy aimed at non-technical maintainers using AI tools.
- Then: **`REVIEW_ARCHITECTURE.md`** for KISS/SOLID/TDD with line refs (applies those rules to this repo).
- Then: **`REVIEW_FRONTEND.md`** for perf/a11y/render with line refs.

Total reading: ~45 minutes if you skim, ~2 hours if you check every line ref.

---

## Meta-takeaway: the cheap fix vs the right fix

We spent ~30 minutes restoring 13 declarations and 2 missing parens. The dashboard now boots. **That was the cheap fix.** It does not prevent the next refactor from doing the same thing.

The *right* fix is the rest of this document: modules, tests, build step, event delegation. None of it is glamorous, none of it changes what users see — but it's the only thing that prevents the next person from spending their afternoon writing another "Debugging log" entry.

When you find yourself doing the cheap fix in a hurry, write down the right fix so it doesn't get forgotten. That's what `TEARDOWN.md` is.

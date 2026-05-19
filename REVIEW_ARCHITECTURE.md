# Architectural Review: `dashboard.html`

A KISS / SOLID / TDD teardown of a 17,800-line self-contained HTML file. Written as a learning artefact after the `fix/restore-missing-declarations` repair session. Junior dev is the target reader; every section ends with a "Why this matters in general" callout.

The repair session ([README.md:403-619](README.md)) treated symptoms — a syntax error and 13 missing globals. This review names the disease.

**Stats that frame the rest of this document** (all from a `grep` of the current file):

- `dashboard.html`: 17,800 lines, 16 MB on disk
- Main `<script>` block: lines 5215–15674 (~10,460 lines, ~59% of the file)
- Top-level declarations: **533** (390 functions + 143 vars). The original `fa46607` had 72; current HEAD has 133.
- 442 inline `onclick=` handlers in HTML
- 86 top-level mutable `let`/`var` globals
- One function (`aimGenerateTodos` at line 14522) is **1,270 lines** by itself. Five functions exceed 200 lines.
- 131 `.innerHTML =` assignments
- The provider-key map `{chatgpt, gemini, perplexity, googleaio, googleaimode}` is re-declared inline at lines 5614, 5615, 7205, 7407, 8347, 11781, 12563, 12650, 12673, 12893, 13072 — **at least 11 copies**.

---

## 1. KISS violations — the five worst

### 1.1 `aimGenerateTodos` is 1,270 lines long

`dashboard.html:14522` — single function ending at line ~15672. It builds the Action Plan view by walking every snapshot field (`competitor_entities`, `prompt_metrics`, `top_sources`, `prompt_response_history`, `aim_se`, etc.), branching on a dozen heuristics ("does this brand have <10% visibility?", "is reddit.com a top source?", "did this prompt get zero ChatGPT mentions?"), and pushing up to 17 different todo shapes into a single array. Each branch carries its own copy-flow, example-domain lookup, and template. There is no way to add a 13th todo type without reading the other 12 to make sure the new code doesn't conflict with them.

**Simpler form**: invert it. Define each todo type as a small descriptor — a pure `(snap) => Todo | null` function plus metadata — and put them in a registry array. `aimGenerateTodos` becomes `TODO_GENERATORS.map(g => g(snap)).filter(Boolean)`, maybe 8 lines. Each individual generator is 30–80 lines, can be tested in isolation, and you can add a new todo type without touching the existing ones. This is the Open/Closed lesson, applied as a KISS lesson: a long if-else chain almost always wants to be a table of small functions.

*Why this matters in general*: when one function is more than ~100 lines, the cost of understanding it before you can safely change it is enormous. The function isn't doing one job — it's doing N jobs glued together. Splitting is rarely premature.

### 1.2 The provider-key map is redeclared 11 times

`dashboard.html:5614-5615` declares `AIM_PROVIDER_KEYS` and `AIM_PROVIDER_DISPLAY` — a clean canonical map of the five AI providers. Then nine other functions (lines 7205, 7407, 8347, 11781, 12563, 12650, 12673, 12893, 13072) redeclare a local copy of the *same* map, sometimes flipping the key direction (`{'ChatGPT':'chatgpt'}` vs `{'chatgpt':'ChatGPT'}`). Adding a sixth provider (say, Anthropic) is now 11 separate edits.

**Simpler form**: keep the two maps at the top of the script, add helper functions next to them — `aimProvDashboardToSnapshot(k)`, `aimProvDisplayLabel(k)`, `aimProvOrder()` — and *forbid* inline redeclaration via grep-able naming. One source of truth, accessed through a tiny interface.

*Why this matters in general*: the same constant declared in N places is N places to update when it changes. Duplication doesn't just risk drift — it actively encourages drift, because each copy slowly bends to fit its caller. The first time you find yourself typing the same literal twice, name it.

### 1.3 `AI_BRANDS` is mock seed data that gets mutated in place

`dashboard.html:5410-5431` declares 20 fictional brands with fake visibility scores ("AI Peekaboo: 52%, Profound: 67%"). Then `aimApplySnapshot` (lines 12587 onwards) overwrites every field of every entry with real data: `AI_BRANDS[0].visibility = avgVis; AI_BRANDS[0].sentiment = avgSent`. The same pattern repeats for `AIM_WORKSPACES[0].brands`, `AIM_VIS_BY_MODEL`, `AIM_SENT_BY_MODEL`, `AIM_PROMPTS`, `AIM_SOURCE_DOMAINS`. The seed data isn't documentation — it's a fake skeleton that has to exist so the file parses, and is then immediately discarded.

This is precisely what made the "remove unused vars" static-analyser bug happen (README.md:579) — the variables looked unused because they were mutated, not reassigned. The fix wasn't "delete the seed data"; it was "fight harder to keep it." That's a smell.

**Simpler form**: separate the *shape* from the *seed*. Make `AI_BRANDS = []` and `AIM_VIS_BY_MODEL = { all: [], chatgpt: [], ... }` at the top — empty containers. Make `aimRenderTopbar` and friends tolerate empty arrays gracefully (return early, show a "no data" state). Then `aimApplySnapshot` is the *only* code that populates them. Fake mock data is a separate concern: keep one optional `mockSnapshot.js` for screenshots / design work, never inline in production. The current scheme conflates "default state" with "demo state" and gets the worst of both.

*Why this matters in general*: code where the default value is a lie is code where every reader has to ask "is this real or placeholder?" every time they encounter it. Empty containers + a clearly-named seed function ("loadDemoData()") tells the truth.

### 1.4 The `_AIM_SNAPSHOT` parse expression that caused the crash

`dashboard.html:6987` (and identical copy at line 16954) was originally:

```js
const snap = window._AIM_SNAPSHOT || (window._AIM_SNAPSHOT = null;
```

This is *trying* to express "use the snapshot, or initialise it to null if missing" — but for `null`, that's identical to just `window._AIM_SNAPSHOT || null`. The parenthesised assignment was both syntactically broken (missing `)`) and semantically pointless. Two characters of cleverness cost the entire dashboard.

**Simpler form**: when an expression's purpose isn't obvious in 1 second, simplify it. `const snap = window._AIM_SNAPSHOT || null` is one line, zero cleverness, zero parsing risk. If you ever need the assignment side-effect ("if missing, set to null so future checks see it"), do it on its own line. The combined `||=` style here is a clever-trap.

*Why this matters in general*: every operator you add to an expression is one more way to mistype it. The cleverest one-liner is whichever one your tired-Friday-self would still write correctly. Aim for "boring code that works" over "tight code that almost works."

### 1.5 Every render function reads from globals AND writes to the DOM

`aimRenderTopbar` (`dashboard.html:6077-6225`) reads from `AIM_WORKSPACES`, `window._AIM_SNAPSHOT`, `window._aimMgrDeleted`, `window._aimMgrToggles`, `window._aimSelectedApiBrandId`, `AIM_BRAND_LIMIT`, `AIM_MODEL_CONFIGS`, `AIM_TOPIC_COLORS` — at least 8 globals — and ends with `el.innerHTML = …`. No arguments in, no return value out, no purity. `aimRenderCompHeatmap` (`dashboard.html:8399-8531`) is the same shape, reading `aimFilterModel`, `aimFilterDate`, `_aimAllResponses`, `aimCpHeatmapPageIdx`, `aimHmSortCol`, `aimHmSortDir`, and several more. There are 37 functions named `aimRender*` (`grep -c "^function aimRender"`); every single one follows this pattern.

**Simpler form**: render functions should take their inputs explicitly. `aimRenderTopbar(state)` where `state` is `{ workspace, snapshot, selectedBrandId, atLimit }` — gathered once at the call site. The body becomes a string-returning function (`function topbarHtml(state): string`) and a thin `el.innerHTML = topbarHtml(state)` shell. The HTML-building part is now testable without a DOM.

*Why this matters in general*: a function with implicit dependencies is a function nobody can refactor with confidence — "did I break it?" requires running the whole app. A function with explicit inputs and a return value can be tested in 5 lines. The cost of converting one is small; the cost of not converting any is what created this file.

> **Why this matters in general (whole section)**: KISS isn't aesthetic. It's economic. Every piece of needless complexity is a tax on every future change. The 13-declarations bug only happened because the codebase was complex enough that a static analyser misread it. Simpler code resists that class of failure.

---

## 2. SOLID violations — focus on SRP and OCP

### 2.1 SRP: the file does ~10 jobs

`dashboard.html` is, simultaneously: a CSS stylesheet (lines 20–2633, 2,613 lines), the HTML body of 7 dashboard views (lines 2645–5212, ~2,560 lines), 20 separate seed-data tables and config objects (lines 5217–5715), all rendering logic for 7 views (37 `aimRender*` functions), the snapshot ingestion pipeline (`aimApplySnapshot`, lines 12556–13203, 647 lines), the boot sequence (lines 13294–13326), the todo-generation engine (1,270 lines, line 14522), a popover/modal subsystem (lines 15790–17797), and inline analytics tags (lines 6–12). Each of these is a distinct *reason to change*: a designer touches CSS, a backend dev touches the snapshot fields, a PM asks for a new todo type, an analyst wants different GA4 events. All of them edit the same file.

The mechanical evidence is the merge-conflict surface area: any two parallel feature branches will both write to `dashboard.html`. There is no per-concern blast radius.

### 2.2 OCP: adding anything = editing the whole file

The Open/Closed principle says "open for extension, closed for modification." Right now, adding a new dashboard view means: (a) adding a `<div id="view-new">` to the HTML body, (b) adding a sidebar nav item with `onclick="showView('new')"`, (c) adding `if (v === 'new') initAiNew()` inside `showView` at `dashboard.html:6344`, (d) writing `initAiNew()` somewhere in the 10K-line JS block, (e) probably patching `aimRefreshCurrentView` too. Five edits to five locations in one file — and any of them can break the others.

Same shape for adding a new AI provider (11 inline `{chatgpt:'…', gemini:'…'}` literals to update — see §1.2). Same for adding a new todo type (`aimGenerateTodos`, see §1.1). The file is "open for extension" only if you're willing to edit half a dozen places that already exist.

**Fix**: a tiny registry pattern. `const AIM_VIEWS = [{ id: 'overview', init: initAiOverview, html: '…' }, …]`; `showView` becomes a loop over the registry. Adding a view is one push to the array.

### 2.3 SRP within `aimApplySnapshot`: ingestion is interleaved with rendering

`aimApplySnapshot` at `dashboard.html:12556` is named like a pure data-transformer ("apply snapshot data to runtime state"), but in practice it (a) parses snapshot fields, (b) mutates `AI_BRANDS`, `AIM_VIS_BY_MODEL`, `AIM_SENT_BY_MODEL`, `AIM_PROMPTS`, `AIM_SOURCE_DOMAINS`, `AIM_DATE_CONFIGS`, `AIM_TOPIC_COLORS`, `AIM_DONUT_DATA`, plus 6+ `window.*` properties, (c) writes DOM at line 13190 (`_urlDomDrop.innerHTML = …`), and (d) re-invokes `initAiOverview()` / `aimRefreshCurrentView()` / `aimRenderTopbar()`. Four jobs, one function, 647 lines. If a snapshot field changes shape, you can't tell from the function signature whether the bug is in parsing, in state-mutation, in DOM-writing, or in the re-render call.

**Fix**: three functions in a pipeline. `parseSnapshot(raw): RuntimeState` (pure), `applyRuntimeState(state): void` (mutates the globals), and the caller does `applyRuntimeState(parseSnapshot(snap)); refreshCurrentView();`. Now the parse step is testable without a DOM.

### 2.4 OCP: snapshot field handling is open-coded at every call site

The snapshot has ~20 fields (`daily_trend`, `prompt_response_history`, `competitor_entities`, etc.). Each one is read in multiple places (`window._AIM_SNAPSHOT.competitor_entities` appears in `aimApplySnapshot`, `aimGenerateTodos`, `aimRenderCompetitorsTablePage`, `aimRenderTopbar`, and others). If the API ever renames a field — say `competitor_entities` → `competitors` — that's a grep-and-edit across the whole file, with no compiler help. There is no accessor layer; every reader directly couples to the JSON shape.

**Fix**: a thin accessor module at the top — `aimSnap.competitors()`, `aimSnap.dailyTrend()`, `aimSnap.promptHistory(id)`. One place to handle missing fields, renames, defaults. Cheap to add, immediate win for a single field rename.

> **Why this matters in general (whole section)**: SRP and OCP aren't ceremony — they're "can I change one thing without reading everything?" When the answer is no, every edit is high-risk. The 2 SyntaxErrors and 13 missing declarations in the repair session were possible because the file is so big nobody had a mental model of all of it. Smaller modules with single responsibilities make wholesale-deletion bugs nearly impossible.

---

## 3. Separation-of-concerns plan — pragmatic, ships one HTML

**Constraint**: the deliverable is a single self-contained `dashboard.html` you can email or drop on S3. You can't introduce a bundler, a build step (Vite/webpack), or external `<script src="…">` files served separately. Anything you propose has to inline back into one file.

**The good news**: you can still split *source* into multiple files and concatenate at build time. The deliverable stays single-file; the workshop doesn't have to be. A 30-line `build.sh` (or `scripts/build_dashboard.py`) that catting source files into `<style>` and `<script>` blocks is enough. This is the **only** new infrastructure required.

**Six modules to extract first (in this order):**

1. **`src/data/constants.js`** (~200 lines). Move `AIM_PROVIDER_KEYS`, `AIM_PROVIDER_DISPLAY`, `AIM_MODEL_CONFIGS`, `AIM_TOPIC_COLORS`, `AIM_PROVIDER_KEYS` etc. — every config map. **Delete the 11 inline copies** of the provider map (§1.2). Zero behavior change, immediate readability win, makes "add a provider" a one-file edit.

2. **`src/data/seed.js`** (~400 lines). Move `AI_BRANDS`, `AIM_WORKSPACES`, `AIM_PROMPTS`, `AIM_SOURCE_DOMAINS`, `AIM_COMP_INSIGHTS`, `AIM_VIS_BY_MODEL`, `AIM_SENT_BY_MODEL`, `AIM_DATE_CONFIGS`, `AIM_PROMPT_VIS_BY_MODEL`, `AIM_SOURCE_BOOST`, `AIM_RECENT_CHATS`, `AIM_PROMPT_COMP_RANKINGS`, `AIM_DONUT_DATA`, `AIM_URL_DONUT_DATA`, `AIM_AP_SUGGESTED`, `AIM_VIS_DATA`. Better still: replace most with empty containers per §1.3, and put the fake demo data behind an opt-in `loadDemoSnapshot()`. This file is where seed-data lives or where the empty defaults live — your call, but isolated.

3. **`src/lib/format.js`** (~150 lines). The pure utility functions: `aimFmtDate`, `aimEscHtml`, `aimSentimentLabel`, `aimTrendArrow`, `aimRelTime`, `aimFormatAnswer`, `aimEvenlySample`, `aimBrandIcon`. These are the easiest functions to extract and the highest-ROI for testing (§4). No DOM, no globals, no side effects — perfect candidates.

4. **`src/lib/metrics.js`** (~300 lines). `aimGetBrandMetrics` (currently `dashboard.html:5727-5805`), `aimHeatmapVal`, `aimHeatmapAllVal`, the brand-name normalizer (`_normBN`), the filtered-dates helpers. These are the "math" of the dashboard — they take data, return numbers, no DOM. Extract them and the dashboard becomes meaningfully testable.

5. **`src/snapshot/apply.js`** (~700 lines). The current `aimApplySnapshot` and `aimApplyInjectedData`. Split internally into `parseSnapshot()` (pure) + `applyRuntimeState()` (mutates globals) per §2.3. This is the highest-value extraction because *every* bug in the data pipeline lives here today.

6. **`src/views/<viewname>.js`** (~5 files, ~1,500 lines each). One file per view: `overview.js`, `competitors.js`, `prompts.js`, `sources.js`, `sentiment.js`, `todos.js`, `integrations.js`. Each contains its `initAi<View>` function and its `aimRender*` helpers. The 1,270-line `aimGenerateTodos` becomes `src/views/todos.js` and gets the §1.1 registry refactor inside that file.

**What stays in `dashboard.html`:**
- All the CSS (lines 20–2633) — concatenation order doesn't matter, no win from extracting yet
- All the HTML body / view divs (lines 2645–5212) — the structure is fine where it is
- The snapshot injection markers (line 5214) — these are part of the deliverable contract
- The `<script>` tag boundaries — the build script just inserts concatenated JS between them

**Build step (literally one new file, ~30 lines):**

```bash
# scripts/build.sh
cat src/template-head.html \
    src/data/constants.js src/data/seed.js \
    src/lib/format.js src/lib/metrics.js \
    src/snapshot/apply.js \
    src/views/*.js src/boot.js \
    src/template-foot.html > dashboard.html
```

You wrap each `.js` file or pre/post-pend `<script>` tags as needed. The deliverable hashes identically (modulo file order) to the hand-edited version on day one.

**What you do NOT do in the first pass:**
- Don't try to remove `window.*` globals — they're load-bearing for inline `onclick=` handlers. That's a §5 "this quarter" task.
- Don't add TypeScript, JSX, modules, or any other compile step.
- Don't move CSS into per-component files yet. Stylesheets are easier to leave alone until you have view-extraction working.

> **Why this matters in general**: separation of concerns is not about purity. It's about "can I edit one thing without reading the whole?" Six files where each fits in your head beat one file that doesn't. The "still ship one HTML file" constraint is fine; concatenation is cheap.

---

## 4. TDD strategy — making this testable in a week

**Current state**: zero tests, no test runner, no module exports. Every function is a global. Most functions read from other globals and write to the DOM. This is the worst-case starting point for TDD.

**The trap to avoid**: do not try to test `aimRenderTopbar` or any render function on day one. The setup cost (jsdom + Chart.js stubs + global priming) will burn your TDD enthusiasm to ash. Start with the easy wins.

### Step (a) — Pure functions to extract first

These functions in `dashboard.html` are *already* pure, or 95% pure. Each takes inputs and returns a value. Extract them to `src/lib/*.js` (per §3.3 and §3.4) with `module.exports` (or ESM `export`), test them, then the build script inlines them back into the HTML. Order by ROI:

1. `aimEscHtml` — line 5807. Two-liner, 100% pure. Test escapes for `<`, `>`, `&`, `'`, `"`, `null`, `undefined`. Six tests, ten minutes.
2. `aimSentimentLabel` — line 5830. Maps a 0–100 score to `{label, color}`. Test boundary values.
3. `aimEvenlySample` — sampled inside `aimApplySnapshot` for date labels. Test with N inputs, K outputs.
4. `aimFmtDate` — line 5719. ISO → display. Test format, invalid inputs, edge dates.
5. `_normBN` (brand-name normalizer) — declared inline at `dashboard.html:12566`. Extract to `lib/brandName.js`. Test `"OtterlyAI"` === `"Otterly AI"` === `"Otterly.AI"`.
6. `aimGetBrandMetrics` — line 5727. Takes a `brand`, reads filter globals, returns `{vis, sent, pos}`. Pass the filters as arguments instead of reading globals — then it's pure. This is the single most-valuable function to make testable: it's the scoring math the README documents (line 214–220).

### Step (b) — Test runner: Vitest

Pick **Vitest**, not Jest. Three reasons:

1. **Zero-config for plain JS**: no Babel, no `transform`, no `jest.config.js`. Add `"test": "vitest"` to a fresh `package.json` and it works.
2. **Fast cold start** (~200ms vs Jest's ~2s). On a one-file repo, that's the difference between TDD feeling free and feeling expensive.
3. **Same API as Jest**: `describe`, `it`, `expect`, `beforeEach`. If you ever migrate, the tests don't change.

```bash
# Setup (one-time)
npm init -y
npm install --save-dev vitest
mkdir -p src/lib tests
```

```jsonc
// package.json — only the relevant parts
{
  "type": "module",
  "scripts": {
    "test": "vitest",
    "test:run": "vitest run",
    "build": "bash scripts/build.sh"
  }
}
```

```js
// vitest.config.js — optional; sane defaults are fine
import { defineConfig } from 'vitest/config'
export default defineConfig({
  test: {
    include: ['tests/**/*.test.js'],
    globals: false,    // explicit imports, easier to read
  },
})
```

Total setup: one `npm install`, one `package.json` line, two minutes.

### Step (c) — The first 5 tests worth writing

In order of writing. Each is a deliberate teaching moment, not just "any old test."

**1. `aimEscHtml escapes all five dangerous HTML characters`** (`tests/escHtml.test.js`).
Asserts that `<`, `>`, `&`, `"`, `'` all become entities, and that `null`/`undefined` become `''`. Good first test because: (a) it's almost impossible to get wrong, (b) it teaches the `describe`/`it`/`expect` shape, (c) the function is used in 100+ places — every test reader can see why it matters.

**2. `_normBN treats Otterly.AI, OtterlyAI, and Otterly AI as the same brand`**.
Asserts the normalizer collapses non-alphanumerics and lowercases. Good test because: (a) it's the exact bug the README's "Competitors view missing brands" section (line 73-79) needs `refresh_brand_vis.py` to work around, (b) it pins down a piece of business logic that's currently implicit, (c) you'll catch any future "OtterlyAI" doesn't match "Otterly.AI" regression instantly.

**3. `aimGetBrandMetrics returns 0 visibility when no timeline data exists`**.
Construct a brand with no `brand_timeline` entry, pass `aimFilterDate='7d'`, expect `{vis: 0, sent: 50, pos: null}`. Good test because: (a) it's the explicit fallback path at `dashboard.html:5803`, (b) it forces you to make the function take `filterDate` as an argument instead of reading globals — the conversion is the test's value, (c) zero-data is the easiest edge case to reason about and the most common in real demos.

**4. `aimGetBrandMetrics averages the visibility across a 7-day window correctly`**.
Construct a timeline with 7 daily entries `[10, 20, 30, 40, 50, 60, 70]`, call with `aimFilterDate='7d'`, expect `vis: 40.0`. Good test because: (a) it pins down the **canonical scoring formula** the README documents at line 214, (b) the README's TIME_RANGE env var (line 90) is supposed to map directly to this filter, so the test doubles as documentation, (c) it's a single arithmetic assertion — no DOM, no globals.

**5. `aimEvenlySample picks 7 evenly-spaced labels from a 30-element array`**.
Asserts sample length is 7, first element equals input[0], last equals input[N-1], and the indices are roughly evenly spaced. Good test because: (a) the date axis is one of the most visually obvious things on the dashboard and a regression is immediately user-visible, (b) it locks down a piece of helper logic that's currently invisible — embedded as a single inline call inside `aimApplySnapshot`, (c) it forces you to actually *extract* the helper as a named function, which is half the point.

After these 5 land, you have: a working test runner, three lib files, ~100 lines of test code, and the muscle memory to extract function 6, 7, 8… on demand. That's how TDD takes root in a legacy codebase — five tests, not fifty.

> **Why this matters in general**: TDD in greenfield code is well-documented. TDD in a 17K-line legacy file is not — the textbooks skip this case. The recipe is: find the most-pure function, extract it as if for testing, write the test, ship it. Repeat. Don't try to test the rendering — test the math first. The math is where regressions hurt customers.

---

## 5. Risk-ranked verdict

### This week (1-3 days each, do all three)

1. **Kill the 11 duplicate provider-key maps** (§1.2). One canonical declaration at the top, search-and-delete the inline copies. Pure cleanup, zero behavior change, makes future provider additions trivial. ~1 hour.

2. **Set up Vitest + extract the first three pure helpers** (§4.a items 1-3: `aimEscHtml`, `_normBN`, `aimEvenlySample`) and write the first three tests (§4.c). Establishes the testing muscle and proves the build-time-concat pattern works. Half a day.

3. **Write the 30-line build script** (`scripts/build.sh` or `scripts/build_dashboard.py`) that concatenates `src/*.js` files into `dashboard.html`. Even with no extractions yet, this unblocks every future modularization. Half a day.

### This quarter (1-2 weeks each, in priority order)

4. **Extract per-view files** (§3.6). `src/views/{overview,competitors,prompts,sources,sentiment,todos,integrations}.js`. The build script concatenates them between the existing `<script>` tags. Big mental-load reduction; merge conflicts on parallel feature work drop to near-zero.

5. **Refactor `aimGenerateTodos` into a registry** (§1.1). 1,270 lines → ~80-line dispatcher + 15 small generators. Adding a new todo type stops being a high-risk edit.

6. **Split `aimApplySnapshot` into `parseSnapshot` + `applyRuntimeState`** (§2.3). The pure parse step gets tests covering every snapshot field; the impure apply step shrinks to obvious mutation.

7. **Introduce the snapshot accessor module** (`aimSnap.competitors()`, etc., §2.4). Decouple every reader from the raw JSON shape. Cheap to add, immediate win when the API renames a field.

8. **Replace inline `onclick=` handlers with delegated listeners** (442 of them currently). Big win for testability and security posture; takes a while because every interaction has to be retested. Probably best done view-by-view as part of §4.

### Never (the cure is worse than the disease)

9. **Don't migrate to React/Next/TypeScript** — out of scope per the brief, and you'd lose the "single HTML file, no build" superpower this repo's customers rely on (README.md:228-280 documents three integration patterns that all depend on it).

10. **Don't try to delete the 442 inline `onclick=` handlers in one pass.** They're load-bearing; each one is wired to a global function name. The right plan is to convert view-by-view (§5.8), not to attempt a single-day sweep that leaves the file half-broken. The repair session you just survived is a tax on big-bang changes; pay it by avoiding the next one.

> **Why this matters in general**: not every cleanup is worth doing. The discipline of saying "we won't do that" is as important as the discipline of saying "we will." A 17K-line file is salvageable if you separate the parts that hurt (math, snapshot parsing, todo generation) from the parts that don't (CSS, HTML structure, declarative seed data). A full rewrite makes a worse codebase fail at production while a better one is half-built — almost always the wrong trade.

---

## Closing

The repair session (README.md:403-619) is the right first step: stop the bleeding, document the diagnosis, share the lesson. The next step is to make a recurrence impossible, not to keep your reflexes sharp. The recurrence-prevention plan in `5.1`, `5.2`, `5.3` is three days of work and removes the entire class of bugs that produced the repair session.

The juniors reading this should walk away with three rules:

1. **Find the duplication and name it once.** (§1.2, §2.4)
2. **Find the long function and split it by responsibility.** (§1.1, §2.3)
3. **Find the pure function buried in the impure one, and write a test for it.** (§4.a, §4.c)

Three rules, applied a hundred times each, would turn this file into something that doesn't need an emergency-repair session next quarter.

# TDD — Architecture & Philosophy

This section is the "why" behind tests in this repo. It is written for the cofounder who maintains `dashboard.html` with AI tools, and for the junior dev who has to keep the lights on. Frontend visual testing and backend API contracts are covered in separate sections — stay focused here on what TDD *is*, why it matters for *this* situation, and when it's worth the cost.

---

## 1. What TDD actually is

TDD — Test-Driven Development — is a three-step loop: **Red → Green → Refactor**.

1. **Red**: write a test for the behavior you want, *before* the code exists. The test fails (red) because there's nothing to call yet.
2. **Green**: write the smallest, ugliest code that makes the test pass. Don't optimize. Don't generalize. Just get to green.
3. **Refactor**: now that the test is green, clean the code up. The test is your seatbelt — if you break the behavior, it goes red again instantly.

Concrete example: say you want to add a new "share of voice" metric to the competitor chart. The TDD version:

```js
// Step 1 — Red. tests/shareOfVoice.test.js
it('returns 25% when brand has 1 of 4 mentions', () => {
  expect(shareOfVoice(1, 4)).toBe(25)
})
// run: npm test  →  ReferenceError: shareOfVoice is not defined

// Step 2 — Green. src/shareOfVoice.js
export const shareOfVoice = (mine, total) => (mine / total) * 100
// run: npm test  →  ✓ passes

// Step 3 — Refactor. Add edge cases, guard against divide-by-zero, etc.
// Tests stay green the whole time.
```

That's the whole loop. The point isn't that you wrote a test — it's that the test came **first**, so the code is shaped around being testable from the moment it exists.

> **Why this matters in general**: the test-first habit forces you to define the behavior before you write the code. You can't write code "that probably does the right thing" if you've already committed to what "right" looks like.

---

## 2. What TDD is NOT

Three myths to clear up before they cause arguments:

- **TDD is not "100% test coverage."** Coverage is a vanity metric. A test that exercises a line without asserting anything meaningful is worse than no test, because it gives false confidence. We aim for *every important behavior* to have a test, not every line.
- **TDD is not "write tests after the code."** Writing tests after the fact is fine — it's better than nothing — but it's not TDD, and it routinely misses edge cases because the test author already knows what the code does and unconsciously writes tests that match. Test-first catches bugs test-after never sees.
- **TDD is not "a test for every function."** Trivial getters, one-line wrappers, and pure rendering helpers usually don't need tests. The math, the parsers, the scoring formulas, the brand-name normalizers — those need tests. The function that returns `el.innerHTML = html` does not.
- **TDD is not slow.** A well-written unit test runs in milliseconds. The 5 tests proposed in `REVIEW_ARCHITECTURE.md` §4 all together run in under a second. The "slow" part is learning the rhythm, and that fades after the first dozen tests.

> **Why this matters in general**: most people who hate TDD got burned by one of these myths. Don't carry someone else's bad experience into this repo.

---

## 3. Why TDD matters HERE specifically

This repo is the perfect storm for regression risk:

- **The maintainer doesn't read JavaScript fluently.** You can spot a visual bug ("the chart is empty"). You cannot spot a logic bug ("the average is computed over the wrong window"). That second class of bug ships silently.
- **The codebase is a 17,800-line single file.** No module boundaries, 86 mutable globals, 533 top-level declarations. Manual inspection cannot cover the surface area.
- **The primary editing tool is AI.** Claude, Cursor, Copilot — they write *plausible* code. Plausible is not the same as correct. AI tools will confidently rename a variable on line 9,000 and break a function on line 14,000 that depended on the old name. They will refactor a "redundant" loop and silently change the iteration order. They will suggest "cleaner" math that swaps `rank` and `total` in the visibility formula.

Without tests, the cofounder's only defense against an AI-introduced bug is: open the dashboard, click around, and hope. That works for layout regressions. It does not work for math regressions — the chart still renders, but the numbers are wrong, and nobody notices until a customer asks "why does my visibility say 12% when I'm clearly #1 on ChatGPT?"

Tests are **the cofounder's autonomous QA**. They are the thing that lets you accept an AI-suggested diff without reading every line of it. They are the difference between "I trust this change" and "I hope this change is fine."

Put another way: this repo without tests is a loaded gun. You don't pull the trigger most days, but the day you do, you can't put the bullet back.

> **Why this matters in general**: the value of a test scales with the cost of a silent failure. Here, silent failures ship to customers and damage trust in the product. Tests are cheaper than that, every time.

---

## 4. The cost-benefit framing — where TDD is worth it, where it isn't

Be honest: TDD has an up-front cost. Writing the test first feels slower than just typing the code. For a tiny team, you cannot afford dogma. Here is the rule we use:

### Non-negotiable — TDD these, always:

1. **The scoring math** (`aimGetBrandMetrics`, visibility average, share-of-voice, sentiment normalization). The whole product is "we tell you the number." If the number is wrong, the product is broken. The bug is invisible visually. Test these test-first, every time.
2. **Brand-name normalization** (`_normBN` and friends). The README documents that "Otterly.AI", "OtterlyAI", and "Otterly AI" must collapse to one brand. A regression here makes competitors silently disappear from charts. Visually invisible. Test it.
3. **Snapshot parsing** — the code that pulls fields out of the JSON the Python scripts produce (`aimApplySnapshot` and downstream). If the API changes a field name, this is where it breaks. A test that loads a real snapshot fixture and asserts shape is one of the highest-leverage tests in the file.
4. **HTML escaping** (`aimEscHtml`). A bug here is a security hole. Test all five dangerous characters, plus `null`/`undefined`. Five-minute test, prevents an XSS.

### Smoke tests are enough — don't bother test-first:

- Pure rendering (`aimRenderTopbar`, the `el.innerHTML = …` shells). A visual smoke test ("does the page load? do the charts appear?") is fine. The expensive part of these functions is the math they call, and that math should already be tested in isolation.
- CSS, copy changes, color tweaks. A test cannot tell you the new shade of purple is correct. Use your eyes.
- One-off scripts in `scripts/`. The Python data-pull scripts are run by hand and inspected by hand. A test pinning them down would slow you down more than it helps.

### Decision rule

Before adding a test, ask: **if this code breaks silently, does a customer see wrong data?** If yes, write the test. If no — if a break would be visually obvious within 5 seconds of opening the dashboard — skip it.

> **Why this matters in general**: the goal isn't to write tests. The goal is to make silent regressions impossible. Tests are how you get there, but only for the code where silent regressions are possible.

---

## 5. The AI-assisted change workflow

This is the workflow that justifies all the test-writing effort. Once tests exist, the daily loop changes:

**Before tests (today)**:
1. Cofounder asks Claude to "add a new metric to the chart."
2. Claude proposes a diff — touches 4 places in `dashboard.html`.
3. Cofounder pastes it in, opens the dashboard, eyeballs the chart.
4. Looks fine.
5. Commit.
6. Three weeks later, a customer notices the average is off by a factor of two.

**After tests (the goal)**:
1. Cofounder asks Claude to "add a new metric to the chart."
2. Cofounder *also* asks: "write the test first. What should the metric return for `[10, 20, 30]`? Add that test, then the code."
3. Claude proposes a diff: one new test file, one new lib function, one wiring change.
4. Cofounder runs `npm test`.
5. **Green** → commit. **Red** → paste the failure back into Claude: "this test is failing, fix it." Claude iterates. Re-run. Repeat until green.
6. Push. The customer never sees the bug.

The key shift: the cofounder doesn't have to *read* the code to trust it. The test reads it for them. As long as the test asserts the right behavior, the implementation is allowed to be ugly, weird, or written by an AI that just hallucinated three function names. If it's green, it works.

Two rules to make this real:

- **When asking AI for any logic change, ask for the test in the same prompt.** "Add a share-of-voice metric. Write the test first, in `tests/shareOfVoice.test.js`. Then the implementation." This is the single highest-leverage habit you can build.
- **Never commit on red.** If `npm test` is failing, stop. Don't push. Don't "fix it later." A green test suite is the line between "we ship safely" and "we ship and pray." Treat it like a seatbelt — clicked or not, no in-between.

> **Why this matters in general**: AI tools are force multipliers. Tests are what keeps them from multiplying mistakes too. The cofounder's superpower in this repo is being able to ship a change without reading the diff — but only because the test read it first.

---

## Closing

TDD here is not about being a "real engineer" or following best practices for their own sake. It's a survival tool for a specific situation: a non-coder maintaining a 17K-line file with AI assistance. Without tests, every AI-suggested change is a coin flip on customer-visible correctness. With tests, the coin is rigged in your favor.

Start small. Five tests, not fifty. Cover the four non-negotiables in §4 first. Build the habit from §5 into every AI prompt. The rest takes care of itself.

---

## Testing UI and design changes

This section is specifically for the cofounder who maintains the visual design of `dashboard.html` using Claude Code or Cursor. You are changing colors, fonts, layout, and copy — not business logic. The tests in §4 cover the math; this section covers everything you can *see*.

---

### The three test types that catch design regressions

**Unit tests for pure render logic**

These test small functions that format text or compute display values — things like `formatPct(0.623)` returning `"62%"`, or a function that decides whether to show a trend arrow up or down. They run in Node.js in milliseconds and need no browser.

What they catch: wrong number formatting, wrong labels, broken string interpolation. What they don't catch: anything visual. A unit test has no idea that `display: none` got added to the trend chart.

**Snapshot tests for HTML output**

These call a pure render function and assert that the HTML string it returns hasn't changed. If a function that builds a card's inner HTML changes — even one attribute — the test fails and shows you a diff.

Honest opinion: for this repo, snapshot tests are mostly noise. The rendering functions in `dashboard.html` are deeply entangled with global state and DOM side effects — they aren't pure enough to snapshot cleanly without a lot of setup. Don't spend time on these. The two test types on either side of them (unit tests for logic, visual regression for layout) cover the real risk.

**Visual regression tests (screenshot diffs)**

These open the actual dashboard in a real browser, take a screenshot, and compare it pixel-by-pixel to a stored baseline screenshot. If any pixel changed — a button moved, a chart disappeared, a color shifted — the test fails and shows you exactly where.

This is the one that matters most for design work. A unit test would never catch "the CSS change to `.chart-wrap` accidentally set `overflow: hidden` and cropped the top of `#aim-ov-chart`." A visual regression test catches it immediately, because the screenshot looks wrong.

Concrete example from this repo: say you ask Claude to change all primary button backgrounds to `#b352b3`. Claude touches a `.btn-primary` rule correctly, but also adds `visibility: hidden` to `.chart-wrap` two edits later. Unit tests: all green (no logic changed). Visual regression: red — the Overview view screenshot shows the trend chart area is blank. You catch it before it ships.

> **Why this matters in general:** in a modular app, a CSS change to one component can only affect that component. In a 17,800-line single file with global CSS, a change to one selector can accidentally affect any element on any view. Visual diffs are how you find out which one.

---

### Playwright setup for this repo

No framework, no build step — Playwright spins up Python's `http.server`, opens `dashboard.html`, and screenshots each view. That's it.

**Install (one time):**

```json
// package.json — add these to devDependencies
"@playwright/test": "^1.44.0",
"npm-run-all": "^4.1.5"
```

Then:

```bash
npm install
npx playwright install chromium   # only chromium needed, saves ~400 MB vs all browsers
```

**Config:**

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/visual',
  snapshotDir: './tests/visual/snapshots',
  use: {
    baseURL: 'http://localhost:8080',
    viewport: { width: 1280, height: 900 },
  },
  webServer: {
    command: 'python3 -m http.server 8080',
    url: 'http://localhost:8080/dashboard.html',
    reuseExistingServer: !process.env.CI,
  },
})
```

**Example test — Overview view:**

```ts
// tests/visual/overview.spec.ts
import { test, expect } from '@playwright/test'

test('Overview view matches baseline', async ({ page }) => {
  await page.goto('/dashboard.html')
  // The Overview view is active by default (id="view-ai-overview", class="view active")
  // Wait for Chart.js to finish drawing the canvas — it animates on load
  await page.waitForTimeout(800)
  await expect(page).toHaveScreenshot('overview.png', { maxDiffPixels: 50 })
})
```

Add one more test block per view — `ai-prompts`, `ai-competitors`, `ai-sources`, `ai-sentiment` — each clicking the nav item first:

```ts
test('Competitors view matches baseline', async ({ page }) => {
  await page.goto('/dashboard.html')
  await page.click('[onclick="showView(\'ai-competitors\')"]')
  await page.waitForTimeout(600)
  await expect(page).toHaveScreenshot('competitors.png', { maxDiffPixels: 50 })
})
```

**Add a script to `package.json`:**

```json
"scripts": {
  "test:visual": "playwright test",
  "test:visual:update": "playwright test --update-snapshots"
}
```

**CI cost estimate:** 4 views × 1 viewport × ~7s per screenshot = roughly 30 seconds per run on GitHub Actions. Free tier handles this easily. The Python server startup adds ~3s. Total run: under 45 seconds.

> **Why this matters in general:** if the test suite takes longer than a minute, people stop running it. 30 seconds means you run it before every commit without thinking about it.

---

### The cofounder workflow for design changes

Here is the exact sequence to follow every time you make a visual change, whether Claude Code suggested it or you typed it yourself.

**1. Make the change.** Example: you ask Claude to "make all primary buttons background color `#b352b3`."

**2. Claude proposes a diff.** It touches some CSS rule in `dashboard.html`. You accept the diff.

**3. Run the visual tests:**

```bash
npm run test:visual
```

**What a passing test looks like:** The terminal prints something like:

```
  ✓  overview.spec.ts › Overview view matches baseline  (1.2s)
  ✓  overview.spec.ts › Competitors view matches baseline  (0.9s)
  4 passed (38s)
```

No news is good news. Ship it.

**What a failing test looks like:**

```
  ✗  overview.spec.ts › Overview view matches baseline
     Error: Screenshot comparison failed: 1,240 pixels differ.
     See diff: tests/visual/snapshots/overview-diff.png
```

Open `tests/visual/snapshots/overview-diff.png`. Playwright shows three panels side by side: expected (left), actual (right), and a pink-highlighted diff (center). The pink pixels are exactly what changed. If the pink is on a button — expected. If the pink is on the trend chart (`#aim-ov-chart`, `dashboard.html:2752`) or the donut (`#aim-ov-donut`, `dashboard.html:2781`) — something unexpected broke, and you should not commit.

**4a. Test failed because of an unintended side effect:** paste the diff screenshot description back into Claude: "The visual test failed — the trend chart area went blank. Here is the diff. What did the CSS change break?" Fix, rerun, green, commit.

**4b. Test failed because the change was intentional** (you meant to update the button color, of course the screenshots differ): update the baseline:

```bash
npm run test:visual:update
```

This overwrites the stored screenshots with the new ones. Then immediately run `npm run test:visual` again (without `--update-snapshots`) to confirm the new baseline passes cleanly. Commit both the updated code and the updated snapshot files together. The snapshots live in `tests/visual/snapshots/` and should be checked into git — they are the "what the dashboard is supposed to look like" record.

> **Why this matters in general:** updating baselines is not cheating. It is the correct thing to do when a change is intentional. The danger is updating them without looking at what changed — always open the diff first.

---

### What cannot be tested cheaply — and what to do instead

Be honest about the limits:

- **Animations.** Chart.js animates on load (`dashboard.html:2752`, `dashboard.html:3081`). Playwright screenshots taken mid-animation are flaky. The `waitForTimeout(800)` in the example above is a workaround, not a guarantee. If you add a CSS transition, test it with your eyes.
- **Hover states.** The info-tip tooltips triggered by `onmouseenter` (e.g. `dashboard.html:3085`) are invisible in screenshots unless you explicitly simulate a hover in Playwright. Worth adding for critical tooltips; not worth it for decorative ones.
- **Real cross-browser bugs.** Playwright with Chromium only catches Chromium bugs. Safari and Firefox can render the same CSS differently. If a customer ever reports "it looks broken in Safari," run it in Safari manually. For a single-HTML static file, Safari bugs are rare but real.
- **Accessibility.** Playwright can check basic ARIA attributes, but it cannot tell you whether the color contrast ratio between `var(--text-muted)` and the card background meets WCAG AA. Use the browser's built-in accessibility inspector (DevTools → Accessibility) for that.

**5-minute smoke test checklist — run this before every commit:**

Open `http://localhost:8080/dashboard.html` in Chrome. Check each item:

- [ ] Page loads with data (not blank, not "–" in every metric)
- [ ] Click each nav item: Overview, Prompts, Competitors, Sources, Sentiment — each view renders
- [ ] The trend chart on Overview shows a line (Canvas `#aim-ov-chart` is not empty)
- [ ] The donut on Overview shows colored segments (not a gray circle)
- [ ] At least one competitor row appears in the Competitors view
- [ ] No red errors in the browser console (DevTools → Console)
- [ ] On mobile width (DevTools → 375px): sidebar collapses, content is readable

This takes under 5 minutes and catches the "blank screen" class of bug documented in `README.md` → "Debugging log." The visual regression tests catch subtler layout shifts; this checklist catches catastrophic failures.

> **Why this matters in general:** automated tests and manual smoke tests are complements, not substitutes. The automated test runs in 30 seconds but cannot see what you see. The smoke test takes 5 minutes but catches things no script can.

---

### Why visual regression helps more in a single-file app than in a normal codebase

In a normal React or Vue app, components are isolated. A CSS change inside `<Button>` cannot accidentally affect `<Chart>` — they are separate files, separate style scopes, separate DOM subtrees.

`dashboard.html` has none of that. Every CSS rule is global. A rule like `.card { overflow: hidden }` applies to every card on every view. A change to the `.chart-wrap` class (used at `dashboard.html:2752` for the Overview trend chart, `dashboard.html:3081` for the Sources line chart, `dashboard.html:3554` for the Search Console chart, and more) affects all of them simultaneously. You can't see all four views at once when you're editing.

Visual regression tests see all four views — one screenshot per view, every run. If a global CSS change breaks the Sources chart while you were only looking at Overview, the `sources.png` diff lights up. You catch the collateral damage before it reaches anyone else.

That is the single strongest argument for visual testing in this specific codebase. The lack of component boundaries is not just a code quality concern — it is a direct multiplier on how many places a single CSS edit can break. Screenshots are the only automated tool that covers the whole surface area in one pass.

---

## Testing the API contract

The previous two sections are about testing code you own. This section is about testing code you don't own — specifically, the PeekABoo API that `scripts/generate_snapshot.py` calls on your behalf.

Here is the problem in plain terms. The PeekABoo team can deploy a change tomorrow. Maybe a field gets renamed — `visibility.score` becomes `visibility.value`. Maybe `competitor_entities[].sentiment` changes from a 0-100 integer to a string label. Maybe a new required field disappears from the snapshot response entirely. Your script will still run to completion, still inject something into `dashboard.html`, and still exit 0. You will open the dashboard that evening and see blank competitor cards or a broken trend chart, with no obvious explanation. The break happened hours ago in a system you don't control.

Contract tests are what catch this before you open the dashboard.

---

### Layer 1: Schema validation inside generate_snapshot.py (highest ROI)

> **Why this matters:** The script currently accepts whatever the API returns and passes it through to the HTML. One field rename breaks the dashboard silently. Validation inside the script makes it loud — the script refuses to write a malformed snapshot.

Add `jsonschema` as a dev dependency (one pip install, no framework, very stable):

```bash
pip install jsonschema
```

Add it to `scripts/requirements.txt`:

```
jsonschema>=4.0
```

Then add a validation call right after fetching the snapshot endpoint — before any of the downstream aggregation logic runs. Insert this near the top of `generate_snapshot.py`, after the imports:

```python
# scripts/generate_snapshot.py  (add near top, after imports)

SNAPSHOT_SCHEMA = {
    "type": "object",
    "required": ["visibility", "competitors"],
    "properties": {
        "visibility": {
            "type": "object",
            "required": ["score", "totalChatsAnalyzed"],
            "properties": {
                "score":              {"type": "number"},
                "totalChatsAnalyzed": {"type": "integer"},
            }
        },
        "competitors": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "score"],
                "properties": {
                    "name":  {"type": "string"},
                    "score": {"type": "number"},
                }
            }
        },
        "aiSuggestions": {"type": "array"},
    }
}

def validate_snapshot_response(data: dict) -> None:
    """Raise ValueError with a human-readable message if the API shape is wrong."""
    try:
        import jsonschema
        jsonschema.validate(instance=data, schema=SNAPSHOT_SCHEMA)
    except jsonschema.ValidationError as e:
        raise ValueError(
            f"PeekABoo /snapshot API response failed schema check.\n"
            f"  Field: {' -> '.join(str(p) for p in e.absolute_path) or '(root)'}\n"
            f"  Problem: {e.message}\n"
            f"  This usually means the API changed shape. Do NOT inject a broken snapshot.\n"
            f"  Contact the PeekABoo team or check aipeekaboo.com/changelog."
        )
```

Then in `main()`, right after the existing `snap = api_get(f"brands/{BRAND_ID}/snapshot")` line:

```python
    snap = api_get(f"brands/{BRAND_ID}/snapshot")
    validate_snapshot_response(snap)   # <-- add this line
    overall_visibility = float(snap.get('visibility', {}).get('score', 0) or 0)
```

If validation fails, the script raises `ValueError`, prints the human-readable message, and exits non-zero. It never writes to `dashboard.html`. A malformed snapshot cannot reach the dashboard.

Keep the schema narrow — only assert fields the dashboard actually depends on. Don't try to exhaustively schema-check every nested object. The goal is catching field renames and structural breaks, not documenting the entire API surface.

---

### Layer 2: A smoke target that asserts field presence (second highest ROI)

> **Why this matters:** The schema check catches shape problems in the data. A smoke run catches a different failure mode: "the API is down, rate-limiting us, or returning 401." A cron job that silently exits 0 with an empty snapshot is just as bad as one that corrupts data.

Add a `Makefile` at the repo root (or extend an existing one):

```makefile
# Makefile

.PHONY: smoke test

smoke:
	@echo "Running smoke check against live PeekABoo API..."
	@python3 scripts/generate_snapshot.py --save /tmp/aim_smoke_out.json
	@python3 - <<'EOF'
import json, sys
with open('/tmp/aim_smoke_out.json') as f:
    snap = json.load(f)
errors = []
if snap.get('overall_visibility') is None:
    errors.append("MISSING: overall_visibility")
if not isinstance(snap.get('daily_trend'), list) or len(snap['daily_trend']) == 0:
    errors.append("EMPTY or MISSING: daily_trend")
if not isinstance(snap.get('competitor_entities'), list):
    errors.append("MISSING: competitor_entities")
if errors:
    print("SMOKE FAILED:")
    for e in errors: print(f"  - {e}")
    sys.exit(1)
print(f"Smoke OK — visibility={snap['overall_visibility']}%, "
      f"trend_days={len(snap['daily_trend'])}, "
      f"competitors={len(snap['competitor_entities'])}")
EOF
```

One important note about `--dry-run`: looking at the actual script, `--dry-run` prints a human-readable summary and returns early — it does NOT produce the assembled snapshot JSON. For the smoke target to assert field shapes, you need `--save` to write the full assembled snapshot to a temp file first. The target above does this.

Run it manually before any scheduled refresh where you suspect something changed:

```bash
PEEKABOO_BRAND_ID=xxx PEEKABOO_API_KEY=xxx make smoke
```

In CI, gate this behind a `workflow_dispatch` trigger — do not run it on every push. You have 18 requests per minute against a production API. One smoke run burns roughly 2 + (number of prompts) requests. That is fine once per day or on demand; it is not fine on every commit.

```yaml
# .github/workflows/smoke.yml
name: API smoke test
on:
  workflow_dispatch:   # manual trigger only — never on push

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install jsonschema
      - run: make smoke
        env:
          PEEKABOO_BRAND_ID: ${{ secrets.PEEKABOO_BRAND_ID }}
          PEEKABOO_API_KEY:  ${{ secrets.PEEKABOO_API_KEY }}
```

---

### Layer 3: Recorded fixture tests — no network, runs in milliseconds

> **Why this matters:** The smoke run is slow and burns API quota. You cannot run it on every commit. Fixture tests let you catch parsing regressions in the Python aggregation logic without spending any API calls.

The workflow: run the script once with `--save` to capture a real assembled snapshot, commit it, and write tests that load it. When the fixture diverges from what the live API produces, the smoke run will fail first — that is your signal to refresh the fixture deliberately.

```bash
# Capture a fresh fixture
PEEKABOO_BRAND_ID=xxx PEEKABOO_API_KEY=xxx \
  python3 scripts/generate_snapshot.py --save tests/fixtures/snapshot.json
```

```python
# tests/test_snapshot_contract.py
import json, os, sys

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'snapshot.json')

def _load():
    with open(FIXTURE) as f:
        return json.load(f)

def test_fixture_loads():
    snap = _load()
    assert isinstance(snap, dict), "Snapshot must be a JSON object"

def test_overall_visibility_present():
    snap = _load()
    assert 'overall_visibility' in snap, "Missing 'overall_visibility'"
    assert isinstance(snap['overall_visibility'], (int, float))

def test_daily_trend_shape():
    snap = _load()
    trend = snap.get('daily_trend', [])
    assert isinstance(trend, list) and len(trend) > 0, "daily_trend is empty"
    first = trend[0]
    assert 'iso_date' in first,   "daily_trend entry missing 'iso_date'"
    assert 'visibility' in first, "daily_trend entry missing 'visibility'"

def test_competitor_entities_shape():
    snap = _load()
    comps = snap.get('competitor_entities', [])
    assert isinstance(comps, list), "'competitor_entities' must be a list"
    if comps:
        first = comps[0]
        assert 'name' in first,       "competitor missing 'name'"
        assert 'visibility' in first, "competitor missing 'visibility'"
        assert 'sentiment' in first,  "competitor missing 'sentiment'"

def test_prompt_metrics_shape():
    snap = _load()
    pm = snap.get('prompt_metrics', [])
    assert isinstance(pm, list) and len(pm) > 0, "prompt_metrics is empty"
    first = pm[0]
    assert 'prompt_id' in first,      "prompt_metrics entry missing 'prompt_id'"
    assert 'visibility_all' in first, "prompt_metrics entry missing 'visibility_all'"
    assert 'by_provider' in first,    "prompt_metrics entry missing 'by_provider'"

if __name__ == '__main__':
    tests = [test_fixture_loads, test_overall_visibility_present,
             test_daily_trend_shape, test_competitor_entities_shape,
             test_prompt_metrics_shape]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    if failed:
        sys.exit(1)
    print(f"\nAll {len(tests)} contract tests passed.")
```

Add it to the Makefile:

```makefile
test:
	python3 tests/test_snapshot_contract.py
```

Run with `make test`. No pip installs, no network, done in under a second.

---

### What to do when the contract breaks

Symptom: after running `generate_snapshot.py`, the dashboard renders blank competitor cards, a missing trend chart, or "–" in every metric that used to show a number.

**First: did schema validation fire?** If the script exited non-zero and printed "PeekABoo /snapshot API response failed schema check", the API changed shape. Do not attempt to fix the dashboard — fix the contract first. The snapshot was not written, so the live dashboard is still on the previous (good) data.

**If the script exited 0 but the dashboard looks broken:** The API changed something the schema did not cover. Run:

```bash
python3 scripts/generate_snapshot.py --save /tmp/fresh.json
# Compare top-level keys against your fixture
python3 -c "
import json
a = json.load(open('tests/fixtures/snapshot.json'))
b = json.load(open('/tmp/fresh.json'))
print('removed:', set(a) - set(b))
print('added:',   set(b) - set(a))
"
```

**Decide: regression or evolution?**

- If a field was renamed or removed without warning — do not update the fixture to paper over it. File an issue with the PeekABoo team. Until they fix it or you have clarity, do not run a fresh snapshot injection; the previous dashboard snapshot is still intact and still correct.
- If it is a deliberate API change — update the schema in the script, capture a fresh fixture, update the test assertions, update the `aimApplySnapshot` parsing logic in `dashboard.html`, run the visual tests from the UI section to confirm charts still render, then commit everything together.

---

### The rate-limit constraint on testing

The PeekABoo API allows 18 requests per minute. A full snapshot run for 40 prompts costs roughly 44 API calls. The rule is:

- **Fixture tests (`make test`)**: no network, no rate-limit concern. Run on every commit.
- **Smoke run (`make smoke`)**: hits the real API. Run manually before a scheduled refresh, or via `workflow_dispatch` in CI. Never on push triggers. Never both scripts concurrently against the same API key — `generate_snapshot.py` and `refresh_brand_vis.py` share the same rate-limit budget, and running them in parallel will leave both in a half-finished state.

---

### What contract tests cannot tell you

Contract tests only check shape — whether the fields exist and have the right type. They cannot check correctness — whether the visibility score the API returned is actually right.

If the PeekABoo scoring formula changes in a way that produces different numbers but identical JSON structure, every contract test passes, every chart renders, and the numbers are wrong. That is semantic drift, and no automated test in this repo can catch it without a known-correct ground truth.

The mitigation is manual and takes five minutes: once a month, open `aipeekaboo.com/dashboard`, note what overall visibility score it shows for your brand, then open `dashboard.html` after a fresh snapshot run and confirm the number is in the same ballpark. You are not looking for exact matches — the two products may use slightly different time windows. You are looking for "both say roughly 20–25%" versus "one says 3% and the other says 67%." A gap that large signals a semantic regression worth investigating.

Write the number down — a note in Notion, a comment in the fixture file, anywhere — so next month you have a baseline to compare against. That is the closest thing to a semantic contract that is practical without building a second analysis pipeline just to cross-check the first one.

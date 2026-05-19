# AI Monitoring Dashboard

A self-contained, single-file HTML dashboard for monitoring AI visibility across ChatGPT, Gemini, Perplexity, Google AIO, and Google AI Mode. Connects to the [AI Peekaboo API](https://aipeekaboo.com) to generate a static snapshot that can be served anywhere.

---

## Overview

The dashboard is a single HTML file (`dashboard.html`) with no external dependencies except Chart.js (loaded from CDN). All data lives in a JSON blob injected into the file at build time — there is no runtime API connection from the browser.

```
┌─────────────────────────────────────────────────┐
│              Build pipeline                      │
│                                                  │
│  AI Peekaboo API                                 │
│       │                                          │
│       ▼                                          │
│  generate_snapshot.py   ──►  dashboard.html      │
│       │                       (self-contained,   │
│       │                        ~1-10 MB)         │
│       ▼                                          │
│  refresh_brand_vis.py   ──►  dashboard.html      │
│  (run after generate    (patches brand_global_   │
│   if Competitors view    vis for full competitor │
│   looks incomplete)      coverage)              │
└─────────────────────────────────────────────────┘
         │
         ▼
  Serve or embed anywhere:
    - Static file (GitHub Pages, S3, Nginx)
    - Next.js: return file contents from a route handler
    - Iframe embed in existing app
```

---

## Quick start

**1. Set environment variables**

```bash
export PEEKABOO_BRAND_ID="your-brand-uuid"
export PEEKABOO_API_KEY="your-api-key"
```

Get both from **aipeekaboo.com/settings/integrations**.

**2. Generate the snapshot**

```bash
cd scripts
python3 generate_snapshot.py
```

Runtime: 10–20 minutes for ~40 prompts (API rate-limited to 18 req/min).

**3. Open the dashboard**

```bash
open ../dashboard.html
```

Or serve it:

```bash
cd ..
python3 -m http.server 8080
# open http://localhost:8080/dashboard.html
```

**4. (Optional) Refresh competitor visibility**

If the Competitors view is missing brands that appear in aipeekaboo.com/dashboard, run:

```bash
python3 refresh_brand_vis.py
```

This does a deeper pass over all brand mentions and patches `brand_global_vis` in the HTML.

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PEEKABOO_BRAND_ID` | Yes | — | Brand UUID. Found in the URL at aipeekaboo.com/settings or /brands endpoint |
| `PEEKABOO_API_KEY` | Yes | — | API key from aipeekaboo.com/settings/integrations |
| `DASHBOARD_PATH` | No | `../dashboard.html` | Absolute or relative path to inject the snapshot into |
| `TIME_RANGE` | No | `30d` | History window. Options: `7d`, `30d`, `90d` |
| `MAX_HIST_DATES` | No | `7` | Max dates of response history per prompt (controls file size) |

Use a `.env` file for local development (see `.env.example`).

---

## Dashboard views

| View | What it shows |
|---|---|
| **Overview** | Visibility score card, daily trend chart, sentiment/position breakdown, recent AI chat responses |
| **Competitors** | All brands by visibility score, sentiment, avg. position — paginated, sortable |
| **Prompts** | Per-prompt visibility, sentiment, position across all 5 AI models |
| **Sources** | All cited domains (1,000+) and URLs (3,000+) sourced from full response history — domain table, heatmap (domain x model), bar chart, URL table with page-type classification |
| **Sentiment** | Feature Mentions table (prompt categories grouped by topic, mention rate + sentiment bar), Sentiment Overview donut (distribution of positive/neutral/negative across responses where brand is mentioned), Sentiment by Competitor (10 per page, pos/neu/neg split + strength/weakness) |
| **Action Plan** | Dynamically generated action items (up to 17) derived from the snapshot data — competitor gaps, zero-visibility prompts, top citation domains, model gaps, Reddit strategy, schema opportunities, press coverage, original research, and more |
| **Integrations** | API key generator (read/read+write permissions), API docs with sticky sidebar (AI agent guide, quickstart, REST reference, rate limits, error codes), MCP server config |

---

## Snapshot data schema

The snapshot is injected as `window._AIM_SNAPSHOT` between the HTML comments:

```html
<!-- AIM_SNAPSHOT_INJECT_START -->
<script>window._AIM_SNAPSHOT={...}</script>
<!-- AIM_SNAPSHOT_INJECT_END -->
```

### Top-level fields

```jsonc
{
  "generated_at": "2026-05-16T11:59:34",  // ISO timestamp
  "brand": "Your Brand Name",
  "brand_id": "uuid",
  "all_brands": [...],                      // All brands in the Peekaboo account (for dropdown)
  "total_runs": 3800,
  "overall_visibility": 2.1,               // % averaged across all prompts + providers
  "overall_avg_position": 4.2,
  "daily_trend": [...],                    // [{date, iso_date, visibility, chatgpt, gemini, ...}]
  "latest_by_provider": {...},             // {chatgpt: {visibility, sentiment, position}, ...}
  "competitor_entities": [...],            // Explicitly tracked competitors (from /competitors API)
  "prompt_metrics": [...],                 // Per-prompt aggregated scores
  "prompt_responses": {...},              // Latest response per prompt per provider
  "prompt_response_history": {...},       // Last N days of responses per prompt
  "recent_responses": [...],              // 20 most recent responses across all prompts
  "mentioned_responses": [...],           // 10 most recent responses where brand was mentioned
  "prompt_analysis": {...},              // Top brand/citation per prompt
  "brand_timeline": {...},               // {brandName: [{date, visibility}]}
  "brand_timeline_by_provider": {...},   // {brandName: {chatgpt: [{date, visibility}]}}
  "top_sources": [...],                   // [{domain, citation_count, run_count}] top 20 domains (runtime IIFE extends to all)
  "top_source_urls": [...],              // [{url, domain, citation_count, share, by_provider}] top 300 URLs
  "sources_by_date": {...},             // {isoDate: [{domain, citation_count}]}
  "sources_by_provider": {...},         // {chatgpt: [{domain, citation_count}]}
  "brand_global_vis": {...},            // {brandName: visibilityScore} — all brands seen across all responses
  "ai_suggestions": [...],
  "aim_real_hm_data": {...},            // {brandName: {chatgpt: score, gemini: score, ...}} for heatmap
  "aim_real_matrix_data": {...}         // {promptId: [{n: brandName, d: domain, count}]}
}
```

### Key field details

**`competitor_entities`** — Only the brands explicitly configured in aipeekaboo.com/settings/competitors. These always appear first in the Competitors view.

```jsonc
{
  "name": "Profound",
  "visibility": 29.0,    // % — from /snapshot API
  "rank": 1,
  "sentiment": 62,       // 0-100 (75=positive, 50=neutral, 25=negative)
  "avg_position": 2.3,
  "mention_count": 847
}
```

**`brand_global_vis`** — Every brand mentioned across all AI responses, with visibility computed as `sum(mention_scores) / total_entries`. This is what populates the rest of the Competitors view beyond the 8 explicitly tracked competitors. High-cardinality — typically 2,000+ brands.

**`prompt_metrics`** — One entry per prompt:

```jsonc
{
  "prompt_id": "ap1",
  "prompt_text": "best aeo platforms for improving brand presence",
  "topic": "General",
  "intent": "Commercial",
  "visibility_all": 2.1,
  "sentiment_all": 52.0,
  "position_all": 4.2,
  "by_provider": {
    "chatgpt":      {"visibility": 3.1, "sentiment": 55.0, "position": 3.0},
    "gemini":       {"visibility": 1.8, "sentiment": 50.0, "position": null},
    "perplexity":   {"visibility": 0.5, "sentiment": 50.0, "position": null},
    "googleaio":    {"visibility": 4.2, "sentiment": 48.0, "position": 5.1},
    "googleaimode": {"visibility": 1.0, "sentiment": 50.0, "position": null}
  },
  "last_run": "2026-05-16"
}
```

**`prompt_response_history`** — Keyed by `ap1..apN` (prompt index), then ISO date, then provider key:

```jsonc
{
  "ap1": {
    "2026-05-16": {
      "chatgpt": {
        "model": "ChatGPT",
        "date": "2026-05-16",
        "text": "Full AI response text (up to 4000 chars)...",
        "brands": ["Profound", "Otterly AI"],
        "sources": ["reddit.com", "tryprofound.com"],
        "sentiment_label": "neutral",
        "visibility_score": 3.1,
        "is_mentioned": 1
      }
    }
  }
}
```

**Visibility scoring formula** — Matches the Peekaboo API exactly:

```
visibility = sum(brand_mention_scores_across_all_runs) / total_runs
```

Where `total_runs = total (prompt × provider × date) entries processed`.

---

## Integrating into aipeekaboo.com

The dashboard is a self-contained HTML file. Three integration patterns are available depending on how you want to serve it.

### Option A: Static file (simplest)

Generate `dashboard.html`, upload to S3/GCS/CDN, serve at a path like `app.aipeekaboo.com/report/{brandId}`. Works well for a per-brand report you regenerate on demand or on a schedule.

```
S3 bucket → CloudFront → /report/{brandId}/dashboard.html
```

Regenerate on a schedule (cron or Lambda):

```bash
# cron: daily at 2am UTC
0 2 * * * PEEKABOO_BRAND_ID=xxx PEEKABOO_API_KEY=xxx \
  DASHBOARD_PATH=/var/www/reports/dashboard.html \
  python3 /opt/peekaboo/scripts/generate_snapshot.py >> /var/log/snapshot.log 2>&1
```

### Option B: Next.js route handler (recommended for aipeekaboo.com)

Read the generated HTML from disk and return it from a route handler. The browser receives a full HTML page — no React hydration, no API calls from the client.

```typescript
// app/report/[brandId]/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { readFile } from 'fs/promises'
import path from 'path'

export async function GET(req: NextRequest, { params }: { params: { brandId: string } }) {
  const filePath = path.join(process.cwd(), 'reports', params.brandId, 'dashboard.html')
  try {
    const html = await readFile(filePath, 'utf8')
    return new NextResponse(html, {
      headers: { 'Content-Type': 'text/html; charset=utf-8' }
    })
  } catch {
    return new NextResponse('Report not found', { status: 404 })
  }
}
```

Pair this with a background job (Trigger.dev, BullMQ, cron) that runs `generate_snapshot.py` for each brand and writes the HTML to `reports/{brandId}/dashboard.html`.

### Option C: Iframe embed

If you want to embed the dashboard inside the existing aipeekaboo.com UI rather than serving it as a full page:

```html
<iframe
  src="/report/brandId/dashboard.html"
  style="width:100%; height:100vh; border:none;"
  title="AI Monitoring Dashboard"
/>
```

Note: the dashboard has its own sidebar navigation. For embed use, you may want to hide it via the iframe URL hash or a query param.

### Snapshot regeneration strategy

The dashboard data is only as fresh as the last time `generate_snapshot.py` was run. Recommended cadence:

| Use case | Frequency |
|---|---|
| Demo / prospect | On demand (manual) |
| Active client | Daily (cron, 2–4am UTC) |
| Real-time monitoring | Hourly (note: 10–20 min runtime per brand) |

For parallel multi-brand generation, run one process per brand (each has its own rate-limit budget).

---

## Architecture: how the dashboard works

All rendering logic lives in the HTML file — no framework, no build step. The JS is structured around three layers:

```
window._AIM_SNAPSHOT       ← static data blob injected at build time
       │
       ▼
aimApplySnapshot(snap)     ← parses snapshot into runtime JS globals:
                              AI_BRANDS, AIM_WORKSPACES, AIM_VIS_BY_MODEL,
                              AIM_SENT_BY_MODEL, AIM_PROMPTS, etc.
       │
       ▼
showView(viewName)         ← renders one of 5 views:
                              'overview' | 'ai-competitors' | 'ai-prompts'
                              'ai-sources' | 'ai-todos'
```

**Key globals set by `aimApplySnapshot`:**

| Global | Type | Purpose |
|---|---|---|
| `AI_BRANDS` | Array | All brands with name, visibility, sentiment, color |
| `AIM_WORKSPACES` | Array | Brand workspace config (links AI_BRANDS to UI) |
| `AIM_VIS_BY_MODEL` | Object | `{all: [], chatgpt: [], ...}` — index-aligned with AI_BRANDS |
| `AIM_SENT_BY_MODEL` | Object | Same structure, sentiment scores |
| `AIM_PROMPTS` | Array | All prompts with text, topic, last response |
| `AIM_RECENT_CHATS` | Array | Recent AI responses for the Overview card |

**Competitor display logic:**

1. `competitor_entities` (8 explicitly tracked) are assigned positions 1–8 in `AI_BRANDS`
2. Additional brands from `brand_global_vis` with visibility >= 1% are appended (up to 20)
3. Brand names are normalized (`/[^a-z0-9]/g` strip) before dedup — handles "OtterlyAI" = "Otterly AI" = "Otterly.AI"

---

## Development notes

**Editing the dashboard JS/CSS:** Edit `dashboard.html` directly. The file is a standard HTML document — open in browser, edit in editor, refresh. No build step.

**Adding a new view:** Each view follows this pattern:
1. Add a `<div id="view-{name}" class="view">` in the HTML body
2. Add a sidebar nav item that calls `showView('{name}')`
3. Add a case in `showView()` that renders the view content

**Chart library:** Chart.js 4.4.0 (loaded from CDN). All charts use the `AimChart` wrapper pattern defined at the bottom of the JS section.

**Data refresh without a full regeneration:** To update only `brand_global_vis` (fastest path for fixing the Competitors view), run `refresh_brand_vis.py` alone. The rest of the snapshot remains unchanged.

**File size:** A fresh snapshot with 40 prompts and 30d of history is typically 8–12 MB. The dashboard loads entirely in memory — avoid very large `MAX_HIST_DATES` values (>14) if file size is a concern.

---

## Scripts reference

### `scripts/generate_snapshot.py`

Fetches all data from the Peekaboo API and injects it into `dashboard.html`.

```bash
# Standard run
PEEKABOO_BRAND_ID=xxx PEEKABOO_API_KEY=xxx python3 scripts/generate_snapshot.py

# Dry run (print summary, don't write to file)
PEEKABOO_BRAND_ID=xxx PEEKABOO_API_KEY=xxx python3 scripts/generate_snapshot.py --dry-run

# Save raw JSON snapshot (for debugging or archiving)
PEEKABOO_BRAND_ID=xxx PEEKABOO_API_KEY=xxx python3 scripts/generate_snapshot.py --save snapshot.json

# Custom dashboard path
PEEKABOO_BRAND_ID=xxx PEEKABOO_API_KEY=xxx DASHBOARD_PATH=/path/to/output.html \
  python3 scripts/generate_snapshot.py
```

API endpoints called, in order:
1. `GET /brands` — brand list
2. `GET /brands/{id}` — per-brand detail (one call per brand in account)
3. `GET /brands/{brandId}/snapshot` — overall metrics + AI suggestions
4. `GET /brands/{brandId}/prompts` — prompt list
5. `GET /brands/{brandId}/prompts/{pid}?include_full_response=true&time_range=30d` — full history (one call per prompt)
6. `GET /brands/{brandId}/competitors` — competitor list

### `scripts/refresh_brand_vis.py`

Recomputes `brand_global_vis` from ALL brand mentions and patches it into `dashboard.html`. Run when the Competitors view is missing brands.

```bash
PEEKABOO_BRAND_ID=xxx PEEKABOO_API_KEY=xxx python3 scripts/refresh_brand_vis.py
```

### API rate limits

The Peekaboo API allows 18 requests/minute. Both scripts include a built-in throttle that pauses automatically when approaching the limit. Do not run both scripts concurrently against the same API key.

---

## Security

- No API keys are stored in `dashboard.html`. The snapshot contains only brand visibility data.
- `dashboard.html` contains your brand's visibility metrics and competitor scores. Treat it as internal data — do not publish to a public URL unless you intend for competitors to see it.
- All user-visible content in the dashboard uses `aimEscHtml()` before rendering to innerHTML. No CSP issues with inline scripts (the snapshot injection is server-side, not user input).

---

## Debugging log: "the dashboard is blank"

> A real session of taking this repo from "renders nothing" to "renders snapshot data." Written for a junior dev as a worked example of how to diagnose a broken self-contained HTML app. Branch: `fix/restore-missing-declarations`.

### The symptom

Cloned the repo, ran `python3 -m http.server 8080`, opened `http://localhost:8080/dashboard.html`. The page loaded — sidebar visible — but every panel was empty. No charts, no numbers, no errors visible to the user.

### Step 1 — Verify the data is actually there

When a "data dashboard" renders blank, there are only two possibilities:

1. **No data** — the snapshot was never injected.
2. **Data is present but rendering is broken** — usually a JS error halted the script.

Cheapest check first: `wc -c dashboard.html` showed 16 MB. An empty template is closer to 1 MB. So the data is there. Confirmed by grepping for the injection markers:

```bash
grep -n "window._AIM_SNAPSHOT" dashboard.html | head
```

Found `window._AIM_SNAPSHOT={"generated_at":"2026-05-19T19:59:33","brand":"AI Peekaboo", ...}` injected on line 5214. **The data is present.** That immediately narrows the problem to "something is preventing JS from running it through to render."

**Takeaway**: before debugging rendering logic, prove whether the data exists. Most "blank screen" issues are one of those two halves of the problem, and they need totally different fixes.

### Step 2 — Read the browser console

The user pasted these errors from DevTools:

```
dashboard.html:6987 Uncaught SyntaxError: Unexpected token ';' (at dashboard.html:6987:68)
dashboard.html:16954 Uncaught SyntaxError: Unexpected token ';' (at dashboard.html:16954:66)
```

A `SyntaxError` is fatal: it stops the browser from parsing the **entire** `<script>` block. Not just that function — the whole script. Nothing after the syntax error runs. So `aimApplySnapshot(window._AIM_SNAPSHOT)` (the function that actually fills the dashboard with data) never executed. That fully explains "data is there, but UI is empty."

Opened those lines. Both had the identical typo:

```js
// broken — missing closing paren on the parenthesized assignment
const snap = window._AIM_SNAPSHOT || (window._AIM_SNAPSHOT = null;
```

Fixed to:

```js
const snap = window._AIM_SNAPSHOT || null;
```

**Takeaway**: when you see `Uncaught SyntaxError`, fix it before reading any other errors. Until the script parses cleanly, every other error message is either misleading or won't even show up. One syntax error can mask a hundred real bugs.

### Step 3 — A new error appears (and that is good)

After fixing the syntax errors, the console showed:

```
Uncaught ReferenceError: AIM_WORKSPACES is not defined
    at aimRenderTopbar (dashboard.html:5876:15)
    at HTMLDocument.<anonymous> (dashboard.html:13091:3)
```

This is **progress**. The script now parses, runs `DOMContentLoaded`, calls `aimRenderTopbar()` — and only then crashes because `AIM_WORKSPACES` doesn't exist. We've moved from "nothing runs" to "things run until they don't."

Where is `AIM_WORKSPACES` supposed to come from? Search:

```bash
grep -nE "^(const|let|var) +AIM_WORKSPACES" dashboard.html
# (no output)
```

It's referenced 12 times across the file but **never declared**. Same story for `AI_BRANDS` and `aimSelectedWorkspaceId`. The codebase is using these as globals that don't exist.

**Takeaway**: when one error is fixed and a different one appears, you're making progress, not going backwards. Track the *frontier of the error* — each new error is a more specific clue than the previous one.

### Step 4 — Use git history to find the missing pieces

When something is referenced but never declared, it was almost certainly declared once and got removed. `git log` is your friend:

```bash
# Find every commit that ever touched a string
git log --all --oneline -S "const AIM_WORKSPACES" -- dashboard.html

# Output included:
# fa46607 Initial release: AI Monitoring Dashboard
```

So it existed in the very first commit. Extract it directly without checking out the branch:

```bash
git show fa46607:dashboard.html | grep -nE "^(const|let|var) +AIM_WORKSPACES"
# 2905:const AIM_WORKSPACES = [
```

`git show <sha>:<path>` reads a file as it existed at any commit — no need to `git checkout` and risk losing your in-progress work.

**Takeaway**: `git log -S "string"` (the "pickaxe") finds every commit that changed how often a string appears. It's the right tool when you want to ask "when did this code disappear?" Don't use `git log --grep` for that — `--grep` searches commit messages, not the diff content.

### Step 5 — Find every missing declaration in one pass

Rather than play whack-a-mole one `ReferenceError` at a time, list every top-level declaration in the original vs current, and diff:

```bash
git show fa46607:dashboard.html | grep -oE "^(const|let|var) +[A-Za-z_][A-Za-z0-9_]+" | awk '{print $2}' | sort -u > /tmp/orig.txt
grep -oE "^(const|let|var) +[A-Za-z_][A-Za-z0-9_]+" dashboard.html | awk '{print $2}' | sort -u > /tmp/head.txt
comm -23 /tmp/orig.txt /tmp/head.txt
```

Output: 13 missing declarations. Far better to know all 13 up front than to discover them one tab-click at a time.

**Takeaway**: when you find one instance of a class of bug, search for the whole class. One missing declaration usually means there are others — fixing them in a batch is much faster than waiting for users to find each one.

### Step 6 — Restore minimally, in the right place

The 13 missing declarations were re-inserted just before `const AIM_PROVIDER_KEYS = …` in the same neighborhood as the other seed-data globals (`AIM_VIS_BY_MODEL`, `AIM_SENT_BY_MODEL`, `AIM_DATE_CONFIGS`). Why there? Two reasons:

1. **Execution order**: they must exist before `DOMContentLoaded` fires `aimRenderTopbar()` on line ~13091. Anywhere in the script body before that works.
2. **Locality**: putting them next to similar globals makes the code easier to read for the next person.

I did NOT re-inject two declarations that the original had — `AIM_PROMPT_COMP_RANKINGS` and `AIM_TOPIC_COLORS`. Both are already declared elsewhere in HEAD. Adding them again would just produce a new `SyntaxError: Identifier 'AIM_PROMPT_COMP_RANKINGS' has already been declared`.

**Takeaway**: a "copy from the old version" fix is only safe if you've checked that you're not creating duplicates. JS doesn't let you redeclare a `const` or `let` at the same scope.

### Step 7 — Sanity-check the fix works

```bash
# All 13 declarations exist exactly once each
for v in AI_BRANDS AIM_WORKSPACES aimSelectedWorkspaceId aimCompMentionsPage \
         aimCompSentPage aimCpHeatmapPageIdx aimHmSortCol aimHmSortDir \
         AIM_HM_PAGE_SIZE AIM_HM_MODELS AIM_HM_ALL AIM_COMP_INSIGHTS AIM_VIS_DATA; do
  echo "$v: $(grep -cE "^(const|let|var) +$v " dashboard.html)"
done

# No remaining instances of the broken paren pattern
grep -c 'window._AIM_SNAPSHOT = null;' dashboard.html  # expect 0
```

Then a **hard refresh** in the browser (`Cmd+Shift+R`) — important because Python's `http.server` happily returns `304 Not Modified` and the browser will keep showing the broken file from cache.

**Takeaway**: a static-file dev server has no idea your file changed. If your fix doesn't seem to land, your browser is probably serving you a stale cached copy. Open DevTools → Network → check "Disable cache" and leave it on while you work.

---

## What was wrong, and why it matters

### The two classes of bug

**Class A — `SyntaxError` (2 instances, blocks everything)**

```js
// dashboard.html:6987 and :16954
const snap = window._AIM_SNAPSHOT || (window._AIM_SNAPSHOT = null;
//                                                              ^ missing )
```

A single `SyntaxError` anywhere in the `<script>` block means the **entire** block is skipped. Not the line, not the function — the whole tag. Browsers do not "try to keep going past a syntax error" inside a script.

**Class B — `ReferenceError` (13 instances, blocks code paths that touch them)**

13 globals were referenced across the file but never declared:

| Variable | What it does |
|---|---|
| `AI_BRANDS` | List of brands shown in sidebar/topbar |
| `AIM_WORKSPACES` | Multi-brand workspace config |
| `aimSelectedWorkspaceId` | Which workspace is currently active |
| `aimCompMentionsPage` / `aimCompSentPage` / `aimCpHeatmapPageIdx` | Pagination state for Competitors tab |
| `aimHmSortCol` / `aimHmSortDir` | Sort state for the heatmap |
| `AIM_HM_PAGE_SIZE` / `AIM_HM_MODELS` / `AIM_HM_ALL` | Heatmap config |
| `AIM_COMP_INSIGHTS` | Per-competitor strength/weakness blurbs |
| `AIM_VIS_DATA` | Mock chart series (overwritten by snapshot) |

The first one (`AIM_WORKSPACES`) blew up during `DOMContentLoaded` because the very first function the dashboard runs (`aimRenderTopbar`) reads from it. That meant `aimApplySnapshot()` — called *after* `aimRenderTopbar` in the same listener — never ran. The 16 MB of snapshot data was sitting on `window._AIM_SNAPSHOT` waiting, but nothing was reading it.

### Why these declarations went missing (informed guess)

The repo has commits like `Revert public template to last known-good state` and a revert of the revert. Comparing the original `fa46607` (72 top-level declarations) to current HEAD (133 declarations), the codebase has clearly been refactored — but 13 declarations got dropped along the way.

The pattern suggests an automated "remove unused variables" pass that misclassified these globals as dead code. The catch: these globals are **populated later via mutation** (`AI_BRANDS[0].visibility = avgVis`), not direct assignment. A static analyzer that only looks for `X = …` won't see them being used and will flag them as unused.

### Why the mock seed data doesn't pollute the real dashboard

You might wonder: "if we restored mock seed data with fake competitor names like 'Profound, 67% visibility', won't that show up?" No. `aimApplySnapshot(snap)` mutates these globals in place when it runs:

```js
AI_BRANDS[0].visibility = avgVis;            // overwrites mock
AI_BRANDS[0].sentiment  = avgSent;
const _ws1 = AIM_WORKSPACES.find(w => w.id === 1);
// _ws1.brands gets repopulated from snap.brand_global_vis
```

So the seed values are scaffolding. They have to exist so the script can parse and the boot sequence can run, but they get replaced with real snapshot data within milliseconds.

---

## Takeaways for a junior dev

These translate beyond this repo to almost any debugging session.

1. **Separate "no data" from "broken rendering" before doing anything else.** The fixes are completely different. A two-minute check (file size, grep for data markers) saves you an hour of looking in the wrong place.

2. **Fix `SyntaxError` first, always.** Until your script parses, nothing else in the file runs. Don't try to interpret other errors; they're either misleading or won't show up.

3. **A new error after a fix is a sign of progress.** "It used to crash on line 1, now it crashes on line 10" means 9 things are now working. Track the frontier of the error, not the count.

4. **`git log -S "string"` is the right tool for "when did this disappear?"** It searches the *diff content* across history. `git log --grep` searches commit messages — a different question. `git show <sha>:<path>` lets you read a file at any historical commit without checking out the branch.

5. **When you find one bug of a kind, search for the whole kind.** One missing global usually means several. One typo'd `}` usually means there's another somewhere. Find them all in one pass instead of letting users discover them one click at a time.

6. **A static-file dev server doesn't know your file changed.** If your fix doesn't seem to land, you're almost certainly looking at a cached browser copy. DevTools → Network → "Disable cache" while you debug.

7. **Static analyzers ("remove unused vars") can produce confidently-wrong results** for code that uses mutation patterns. If a variable is declared once and then *mutated* (not reassigned), an unused-variable check may flag it as dead. This is one of the few places where `// eslint-disable` is genuinely justified.

8. **Self-contained HTML files have no module system, so order matters.** Every `<script>` block runs top-to-bottom in source order, all globals share one namespace, and there's no compile-time check that the things you reference actually exist. The freedom is great until it isn't.

9. **Restore minimally, in the right place.** When patching from history, only bring back what's actually missing. Put it where similar code lives, not at the top of the file. Future readers will thank you.

10. **Hard-refresh before you trust anything.** `Cmd+Shift+R` on Mac, `Ctrl+Shift+R` on Linux/Windows. Combine with DevTools cache disable.

---

## License

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

## License

Internal tool for AI Peekaboo. Not for redistribution.

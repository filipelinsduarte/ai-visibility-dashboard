# Dashboard Architecture Map

## Overview

`dashboard.html` is a single-file HTML application: ~17,600 lines of HTML, CSS, and vanilla JavaScript, with Chart.js 4 as the only external runtime dependency. There is no build step, no module system, no routing library, and no framework. Everything lives in one file so Filipe can iterate on the design in seconds without a dev server, and so a snapshot of the file (with data injected) renders standalone on GitHub Pages.

Two browser-global data sources drive the entire UI:

- `window._AIM_SNAPSHOT`: the primary payload, written by `tools/peekaboo-snapshot/` and inlined into the HTML between `<!-- AIM_SNAPSHOT_INJECT_START -->` and `END` markers. This is the authoritative dataset: brand metadata, daily trends, per-provider visibility, prompt responses, top sources, sentiment buckets, and the global competitor timeline.
- `window.AIM_INJECTED_DATA`: a secondary payload reserved for legacy / cross-brand context (initialised to `null` at line 2640). It carries `competitorTrend`, `competitorTrendByProv`, heatmap fills, and a small set of derived fields that the snapshot does not yet emit. `aimApplyInjectedData` runs after `aimApplySnapshot` and may overwrite specific globals (see Known Issues, section 7).

There is no client-side routing. The body contains one `<div class="view" id="view-...">` per major area, and `showView(v)` toggles the `.active` class. Filters (`aimFilterDate`, `aimFilterModel`, `aimFilterTopic`, `aimFilterIntent`) are plain JS module-scope `let` bindings, and `aimRefreshCurrentView()` is the single re-render entry point after any filter change.

Charts are created lazily inside per-view `initAi*` functions and cached in `aimChartInstances` so subsequent renders can `destroy()` and recreate.

## 1. Section and View Inventory

| View | Container id | Approx. lines | Init function | Key data globals consumed | Renders |
|---|---|---|---|---|---|
| Sidebar | `aside.sidebar` | 2646 to 2740 | static HTML, mutated by `aimToggleSidebar` | `AI_BRANDS`, `aimSelectedBrandId` | nav links, brand selector trigger |
| Topbar / BrandSelector | injected by `aimRenderTopbar` | 5873 to 6022 | `aimRenderTopbar` (5873) | filter state, `aimGetDateTriggerLabel` | date / model / topic / intent dropdowns, brand chip |
| Overview | `#view-ai-overview` | 2741 to 2826 | `initAiOverview` (6161) | `AIM_VIS_BY_MODEL`, `AIM_DATE_CONFIGS`, snapshot `daily_trend`, `recent_chats`, `AIM_SOURCE_DOMAINS`, content-type buckets | visibility chart, competitors mini-table, top sources card, content-type donut, recent chats card |
| Prompts | `#view-ai-prompts` | 2827 to 2907 | `initAiPrompts` (6696) | `AIM_PROMPTS`, `AI_BRANDS`, `aimPromptsTab`, sort state | tabbed list (Active / Suggested / Inactive), detail panel, response modal |
| Competitors | `#view-ai-competitors` | 2908 to 2965 | `initAiCompetitors` (7326) | `AI_BRANDS`, `_aimBrandTimeline`, snapshot `comp_mentions`, heatmap matrix | mentions chart, brand x model heatmap, prompt x brand matrix, tracking banner |
| Sentiment | `#view-ai-sentiment` | 2966 to 3068 | `initAiSentiment` (8044), backed by `aimBuildSE` (7366) | `_aimSE`, `_aimSentFilters` | sentiment donut, category breakdown chart, sentiment over time, entries table, filter pills |
| Sources (Domains tab) | `#view-ai-sources` | 3069 to 3140 | `initAiSources` (9010) -> `aimSetSourcesTab('domains')` | `AIM_SOURCE_DOMAINS`, `AIM_SOURCE_LINE_DATA`, `AIM_SOURCE_BOOST` | line chart, donut, table, heatmap |
| Sources (URLs tab) | (same view) | 3140 to 3222 | `aimSetSourcesTab('urls')` | aggregated source URLs from prompt history | line chart, donut, URLs table |
| Settings | `#view-settings` | 3223 to 3497 | `initAiSettings` (10665) | brand record, manage modals state | Brand Details, Analysis Schedule, White-Label, Share Links, Manage Prompts, Manage Competitors |
| Search Console | `#view-search-console` | 3498 to 3660 | `initSearchConsole` (9897) | `window.AIM_SC_DATA` (static mock at line 9785) | period / granularity pills, metric toggles, line chart, queries table, intent filter |
| Action Plan / Todos | `#view-ai-todos` | 3661 to 3753 | `aimGenerateTodos` (14318) + `aimRenderTodosTable` (13533) | brand metrics, prompts, sources, sentiment, `localStorage` flags | todos table with parent / child expansion, detail panel |
| Ask AI | `#view-ask-ai` | 3754 to 3837 | inline | snapshot widgets via `_aimAskWidget*` | conversational responses with embedded charts |
| Integrations | `#view-integrations` | 3838 onwards | `aimSetIntgTab` (17390) | API keys list (mock) | tabs for API, MCP, etc.; copy snippets, key generation |

## 2. Key Functions Catalog

Roughly 40 of the most load-bearing functions, in load order:

| Function | Line | Purpose |
|---|---|---|
| `aimGetBrandMetrics(brand)` | 5523 | Filter-aware computation of visibility, sentiment, position for a brand. Reads `aimFilterDate`, `aimFilterModel`, and the brand's timeline. Used by the Prompts and Overview cards. |
| `aimEscHtml(s)` | 5603 | Single XSS guard for every user-supplied string. Mandatory wrap before `innerHTML`. |
| `aimGetDateConfig()` | 5611 | Resolves `aimFilterDate` to an `AIM_DATE_CONFIGS[...]` bundle (labels, point count). |
| `aimSetCardFilter(field, val, cid)` | 5786 | Mutates one filter (`date`, `model`, `topic`, `intent`), then debounce-calls `aimRefreshCurrentView`. |
| `aimRefreshCurrentView()` | 5815 | Master re-render dispatcher; switch over `aimCurrentView`. |
| `aimRenderTopbar()` | 5873 | Rebuilds the topbar HTML; runs on filter change and view change. |
| `aimSelectBrand(id)` | 6051 | Switches brand context, re-runs `initAi*` for the current view. |
| `showView(v)` | 6140 | Toggles `.view.active`, sets `aimCurrentView`, kicks the right `initAi*`. |
| `initAiOverview()` | 6161 | Builds the Overview view: visibility chart, competitors mini-table, sources, donut, recent chats. |
| `aimRenderVisibilityChart()` | 6319 | Chart.js multi-line chart, one line per provider plus an overall line. |
| `aimRenderCompetitorsTablePage()` | 6431 | Paginated competitors mini-table on Overview. Sorts by `b.visibility` (global), not per-prompt. |
| `aimRenderRecentChats()` | 6572 | Renders the latest N prompt x model entries with snippets and model badges. |
| `initAiPrompts()` | 6696 | Sets up the Prompts view with default tab, sort, and search wiring. |
| `aimRenderPromptsTable()` | 6787 | Renders the filtered, sorted prompt rows for the active tab. |
| `aimAddSuggestedPrompt(id, el)` | 6976 | Promotes a suggested prompt to Active. |
| `aimOpenResponseModal(model, date, promptId, storeKey)` | 7196 | Opens the full LLM response modal; defensive read of `aiModel` vs `model`. |
| `initAiCompetitors()` | 7326 | Initialises the Competitors view; depends on `_aimBuildCompMentionData`. |
| `aimBuildSE()` | 7366 | Materialises `_aimSE`: structured sentiment entries (per prompt x model with sentiment, snippet, category). The single source of truth for the Sentiment view. |
| `aimRenderCompMentionsChart()` | 8067 | Chart.js bar chart of competitor mention counts. |
| `aimRenderCompHeatmap()` | 8195 | Brand x model heatmap; snapshot fills win, injected fills gaps. |
| `aimRenderCompPromptMatrix()` | 8935 | Prompt x brand mention matrix. |
| `initAiSentiment()` | 8044 | Wires sentiment filters and triggers chart + table renders. |
| `aimUpdateSentiment()` | 7639 | Re-renders the sentiment donut, category chart, and entries when filters change. |
| `initAiSources()` | 9010 | Sets up the Sources view; default tab is Domains. |
| `aimSetSourcesTab(tab)` | 9015 | Switches between Domains and URLs tabs and triggers a render. |
| `aimRenderSourceLineChart()` | 9211 | Per-domain citations over time. |
| `aimRenderUrlLineChart()` | 9346 | Per-URL citations over time. |
| `aimRenderDomainsTable()` | 11489 | Sources Domains table with DR, type, share. |
| `aimRenderUrlsTable()` | 11554 | Sources URLs table with page-type classifier. |
| `initSearchConsole()` | 9897 | Wires Search Console view; reads `AIM_SC_DATA` static mock. |
| `initAiSettings()` | 10665 | Wires Settings tabs (brand details, schedule, white-label, share, manage prompts, manage competitors). |
| `aimStRenderPrompts()` | 10754 | Manage Prompts table with topic / intent inline edits and bulk actions. |
| `aimApplySnapshot(snap)` | 12352 | Master hydration. Reads `_AIM_SNAPSHOT`, mutates `AI_BRANDS`, `AIM_VIS_BY_MODEL`, `AIM_SOURCE_DOMAINS`, `AIM_DATE_CONFIGS`, `_aimBrandTimeline`, `_aimBrandTimelineByProvider`. Resets `_aimExtUrlCache`, `_aimCompMentionData`, `_aimSE`. |
| `aimApplyInjectedData()` | 13124 | Secondary hydration. Reads `AIM_INJECTED_DATA` and OVERWRITES `_aimBrandTimeline` and `_aimBrandTimelineByProvider` with `competitorTrend` / `competitorTrendByProv` so the timeline chart matches the global competitors table scale. Fills heatmap gaps but does not override existing snapshot values. |
| `aimRenderTodosTable()` | 13533 | Renders todos with parent rows and the expand-to-child UX. |
| `_aimExpandTodo(parent)` | 14275 | Materialises child todos from `parent.suggestions[]`. Child todos inherit `_groupLabel` for the why panel; they do NOT inherit parent steps. |
| `aimGenerateTodos()` | 14318 | Heuristic generator: walks brand metrics, prompts, sources, sentiment, and creates parent todos with `{title, steps[], signals[], suggestions[]}`. Singleton suggestions are folded into the parent (no expand affordance). |
| `aimOpenTodoDetail(id)` | 14069 | Right-side todo detail panel with why, steps, signals, brand badges. |

## 3. Filters and State

Global state, declared at lines 5485 to 5510:

```js
let aimSelectedBrandId   = 1;
let aimFilterModel       = 'all';
let aimFilterDate        = '7d';
let aimFilterTopic       = 'all';
let aimFilterIntent      = 'all';
let aimFilterDomainType  = 'all';
let aimFilterUrlDomain   = 'all';
let aimPromptsTab        = 'Active';
let aimPromptsSortField  = 'visibility';
let aimPromptsSortDir    = 'desc';
let aimCheckedPrompts    = new Set();
let aimCheckedSuggested  = new Set();
let aimCurrentPromptId   = null;
let aimCalYear           = 2026;
let aimCalMonth          = 4;
let aimCalStart          = null;
let aimCalEnd            = null;
let aimCalTargetCid      = null;
let aimChartInstances    = {};
let aimCurrentApTab      = 'ai';
let aimCurrentView       = 'ai-overview';
let aimCompPageIdx       = 0;
```

Filter awareness by view:

| View | Date | Model | Topic | Intent |
|---|---|---|---|---|
| Overview | yes | yes | yes | yes |
| Prompts | yes | yes | yes | yes |
| Competitors | yes | yes | partial | no |
| Sentiment | yes | yes (via SE) | yes (cat) | no |
| Sources | yes | yes | no | no |
| Settings | no | no | no | no |
| Search Console | independent period / granularity controls | no | no | yes (own intent pill) |
| Action Plan | no, derives from current snapshot | no | no | no |

Provider key naming inconsistency: internal keys (used as object keys and CSS hooks) are `chatgpt`, `gemini`, `perplexity`, `googleaio`, `googleaimode`. The API uses `google-aio` and `google-aim`. The map lives at `PMAP` inside `aimApplySnapshot` (line 12359). The production app should pick one canonical form and translate at the API boundary.

## 4. Data Flow

```
AI Peekaboo API
   |  (Python: peekaboo-snapshot)
   v
snapshot.json   ----+
                    |  inlined between AIM_SNAPSHOT_INJECT_START / END
                    v
window._AIM_SNAPSHOT
        |
        v
aimApplySnapshot(snap)         <-- primary hydration (line 12352)
        |  writes AI_BRANDS, AIM_VIS_BY_MODEL, AIM_SENT_BY_MODEL,
        |  AIM_DATE_CONFIGS labels, AIM_SOURCE_DOMAINS,
        |  _aimBrandTimeline, _aimBrandTimelineByProvider,
        |  prompt history, comp_mentions, sentiment buckets, etc.
        v
aimApplyInjectedData()         <-- secondary hydration (line 13124)
        |  reads window.AIM_INJECTED_DATA
        |  OVERWRITES _aimBrandTimeline with inj.competitorTrend
        |  fills heatmap gaps only
        v
initAi<View>() / aimRefreshCurrentView()
        |
        v
DOM via aimRender*Chart, aimRender*Table, innerHTML through aimEscHtml
```

Dual source resolution rules (from comments in `aimApplyInjectedData`):

1. `_aimBrandTimeline`: `AIM_INJECTED_DATA.competitorTrend` always wins. The snapshot's `brand_timeline` is a per-prompt position-weighted metric (typically 60 to 90 percent), while `competitorTrend` is global visibility (typically 5 to 40 percent). The timeline chart needs to share a scale with the competitors table, so it uses the global series.
2. Heatmap matrix: snapshot wins, injected only fills gaps where the snapshot did not emit a value.
3. Sources: snapshot is the only source; injected does not touch them.
4. Competitors list: snapshot.competitors is preferred; the prototype falls back to `/competitors` endpoint only if snapshot list is empty.

## 5. React Component Tree (Proposal)

Suggested Next.js 14 layout:

```
app/
  (dashboard)/
    layout.tsx                <DashboardShell> with sidebar + topbar
    page.tsx                  -> Overview
    prompts/
      page.tsx                Prompts list (tabbed)
      [promptId]/page.tsx     Prompt detail (replaces modal)
    competitors/page.tsx
    sentiment/page.tsx
    sources/
      page.tsx                Domains + URLs tabs as searchParams
    settings/
      page.tsx                tabs as searchParams
      manage-prompts/page.tsx
      manage-competitors/page.tsx
    search-console/page.tsx
    todos/
      page.tsx                Action Plan list
      [todoId]/page.tsx       Detail panel
    ask/page.tsx              Ask AI
    integrations/page.tsx

components/
  ui/                         Stateless, reusable
    DashboardShell.tsx
    Sidebar.tsx
    Topbar.tsx
    BrandSelector.tsx
    FilterBar.tsx             Date/Model/Topic/Intent
    CustomSelect.tsx          Replaces aimCardFilterHTML
    DateRangePicker.tsx       Replaces aimOpenCalendar
    BrandIcon.tsx             Replaces aimBrandIcon + fav fallbacks
    ModelBadge.tsx
    TopicBadge.tsx
    VisBar.tsx                Visibility bar chart cell
    SentimentSplit.tsx        Pos/Neu/Neg three-bar component
    ResponseModal.tsx
    DonutCard.tsx
    LineChartCard.tsx
    HeatmapCell.tsx
    InfoTip.tsx
    Toast.tsx

  charts/
    VisibilityChart.tsx
    CompetitorsMentionsChart.tsx
    CompetitorsHeatmap.tsx
    PromptBrandMatrix.tsx
    SourceLineChart.tsx
    SourceDonut.tsx
    UrlLineChart.tsx
    UrlDonut.tsx
    SentimentOverTime.tsx
    SentimentCategoryChart.tsx
    SearchConsoleChart.tsx

hooks/
  useFilterState.ts           Zustand store mirroring aimFilter* vars
  useSnapshot.ts              Server-action backed, includes 120s revalidate
  useBrand.ts
  useTodos.ts                 includes localStorage flags

lib/
  brandTimeline.ts            consolidate per-prompt vs global series
  sourceAggregation.ts        URL-level aggregation from prompt history
  todoGenerator.ts            port of aimGenerateTodos
  escHtml.ts                  React doesn't need this for rendering, but keep for any dangerouslySetInnerHTML or copy-to-clipboard paths
  providerKey.ts              canonical mapping between API and internal keys
  rateLimiter.ts              token bucket honoring X-RateLimit headers
```

`useFilterState` should be a Zustand store with the same shape as the current globals, so each chart can subscribe selectively and avoid full-tree re-renders.

## 6. Known Issues and Footguns

These are the non-obvious behaviours that have caused regressions in the prototype:

- `_aimBrandTimeline` two-source problem. The snapshot's `brand_timeline` is per-prompt position-weighted (60 to 90 percent), `AIM_INJECTED_DATA.competitorTrend` is global (5 to 40 percent). The timeline chart needs to match the competitors table scale, so `competitorTrend` always wins. Reversing this swaps the chart scale and breaks the visual comparison.
- Heatmap and matrix guards: snapshot wins, injected fills only when the snapshot did not emit a cell. Reverse this and known good data gets overwritten by stale aggregates.
- Competitors must sort by `b.visibility` (global), NOT by `aimGetBrandMetrics(b).vis` (filter-aware). The mini-table on Overview is intentionally a global view; making it filter-aware silently de-ranks brands when the user toggles a model.
- Main brand is `AI_BRANDS[0]` with `isMain: true`. Many functions assume index 0 is the project brand. Do not sort `AI_BRANDS` without preserving this invariant.
- `aimEscHtml` is mandatory on every interpolated string in `innerHTML`. The HTML pattern is the rule, not the exception. In React, prefer JSX expressions and reserve `escHtml` for clipboard / file paths.
- Provider key naming: internal keys are unhyphenated (`googleaio`, `googleaimode`), API keys are hyphenated (`google-aio`, `google-aim`). Map only once, at the API boundary.
- Chart.js 4 uses `scales.x.border: { display: false }`, not `drawBorder: false`. Several charts will silently render a default axis line if this is not set.
- Brand dropdown stacking context: the brand selector is positioned absolutely; it must be rendered into a portal in React to escape ancestor `transform` / `overflow` clipping.
- Todo `localStorage` cleanup runs on every page load (see `aimGenerateTodos`). Stale flags from a previous brand can phantom-mark new todos as completed; the cleanup is keyed by brand id and todo signature.
- Singleton suggestion fold rule: if a parent has exactly one suggestion, it is folded into the parent (no expand affordance, no child row). The expand UI only appears with 2+ suggestions.
- Child todos do not inherit parent steps. Each suggestion carries its own `{title, steps, signals}` object. Reusing parent steps was an early bug.
- `_groupLabel` placement: goes in the why panel (right side detail), not in the table row header. Putting it in the header crowds the title.
- `AIM_INJECTED_DATA` is secondary, not primary. Treat snapshot as authoritative and inject only the legacy fields it lacks (`competitorTrend`, `competitorTrendByProv`, heatmap fills).
- `time_range` of `'1y'`, `'30'`, `''`, or `'all'` is silently downgraded to `'7d'` by the API. Lint or type-guard.
- `history[].aiModel` vs `.model`: API returns `aiModel`. Reading `.model` returns undefined. Use a Zod transform.
- `/prompts/:id` is hard-capped at 100 entries; daily brands hit the cap at ~20 days. The production app must persist this server-side for any retention beyond ~3 weeks.

## Essential File Reference

| Path | Role |
|---|---|
| `dashboard.html` | Single-file prototype, ~17,600 lines. Snapshot is inlined between `AIM_SNAPSHOT_INJECT_START` / `END` markers. |
| `snapshot.json` | Latest snapshot payload (also lives in repo root for reference). |
| `tools/peekaboo-snapshot/` | Python data generator. Calls AI Peekaboo API, writes `snapshot.json`, injects into `dashboard.html`. |
| `scripts/` | Repo helper scripts (deploy, lint, etc.). |
| `docs/API_CONTRACT.md` | Upstream API reference. |
| `docs/DATA_MODEL.md` | TypeScript interfaces for the Next.js port. |
| `docs/HANDOFF.md` | Entry-point README for the production rebuild. |

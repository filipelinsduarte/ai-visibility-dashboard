# Data Model

TypeScript interface definitions covering both the upstream API shapes (as returned by `https://www.aipeekaboo.com/api/v1`) and the internal data shapes the prototype builds inside `aimApplySnapshot`. Drop these straight into the Next.js project as the basis for Zod schemas, Prisma models, and React component prop types.

Cross-references:

- API field semantics: see [./API_CONTRACT.md](./API_CONTRACT.md).
- Where each shape is consumed in the prototype: see [./ARCHITECTURE.md](./ARCHITECTURE.md).

## 1. Upstream API shapes

The first block mirrors what the AI Peekaboo REST API returns. Field names match the API exactly so that wire decoders are trivially compatible.

### Brand

Returned by `GET /brands` (list) and `GET /brands/:brandId` (detail). The detail call adds the six optional fields at the bottom.

### Prompt

Returned by `GET /brands/:brandId/prompts`. `score`, `bestScore`, `worstScore` are 0 to 100 percent visibility scores; `trend` is an optional delta vs. the prior period.

### PromptHistoryEntry

One entry per prompt x model x date. Returned inside `GET /brands/:brandId/prompts/:promptId#history[]`. Note that `aiModel` is the official field, not `model`.

### BrandMention

Sub-document inside `PromptHistoryEntry.brandMentions[]`. `type` distinguishes the project brand, tracked competitors, and untracked entities surfaced from the response text.

### Competitor

Returned by `GET /brands/:brandId/competitors` and embedded in `snapshot.competitors[]`.

### Source

Citation source returned inside `PromptHistoryEntry.sources[]`. `url` is the only place full URLs are exposed by the API; aggregate domain views must be built from this.

### AISuggestion

Suggested prompts returned inside `snapshot.aiSuggestions[]`.

```ts
// =====================================================================
// Upstream API shapes (from https://www.aipeekaboo.com/api/v1)
// =====================================================================

export interface Brand {
  id: string;
  name: string;
  url: string;
  industry: string | null;
  lastAnalysisAt: string | null;
  analysisFrequency: 'daily' | 'weekly';
  productDescription?: string;
  language?: string;
  location?: string | null;
  analysisEnabled?: boolean;
  promptCount?: number;
  competitorCount?: number;
}

export type SearchIntent =
  | 'INFORMATIONAL'
  | 'COMMERCIAL'
  | 'TRANSACTIONAL'
  | 'NAVIGATIONAL'
  | 'LOCAL'
  | 'INVESTIGATIONAL'
  | 'SENTIMENT'
  | 'BRANDED';

export interface Prompt {
  promptId: string;
  promptText: string;
  category: string;
  searchIntent: SearchIntent;
  score: number;
  bestScore: number;
  worstScore: number;
  trend?: number;
}

export type Sentiment = 'positive' | 'neutral' | 'negative';

export interface PromptHistoryEntry {
  aiModel: string;
  date: string;
  score: number;
  rank: number | null;
  mentioned: boolean;
  runId?: string;
  sentiment?: Sentiment | null;
  brandMentions: BrandMention[];
  sources: Source[];
  fullResponse?: string;
  responseSnippet?: string;
}

export interface BrandMention {
  entityName: string;
  type: 'brand' | 'competitor' | 'untracked';
  score: number;
  rank?: number;
  sentiment?: Sentiment | null;
  sentimentScore?: number | null;
}

export interface Competitor {
  id?: string;
  name: string;
  url?: string;
  score: number;
  rank: number | null;
  monthlyTraffic?: number;
}

export interface Source {
  domain: string;
  url: string;
  title: string;
}

export interface AISuggestion {
  id?: string;
  title: string;
  description?: string;
}

// =====================================================================
// Dashboard internal shapes (built by aimApplySnapshot)
// =====================================================================

/**
 * Summary row used by the Overview competitors mini-table, sidebar
 * brand chip, and any view that needs a brand at a glance.
 * Note: visibility is GLOBAL (not filter-aware).
 */
export interface BrandSummary {
  id: number;
  name: string;
  domain: string;
  icon?: string;
  isMain?: boolean;       // true only for AI_BRANDS[0]
  visibility: number;     // 0-100
  sentiment: number;      // -100 to 100 (or 0-100 if normalised)
  position: number | null;
  monthlyTraffic?: number;
}

/**
 * Per-prompt metric used in the Prompts table and detail panel.
 * `bestProvider` and `worstProvider` use internal provider keys.
 */
export interface PromptMetric {
  promptId: string;
  numericId: number;          // dashboard-local id, used as map key
  promptText: string;
  category: string;
  searchIntent: SearchIntent;
  visibility: number;         // 0-100, average across the active window
  bestScore: number;
  worstScore: number;
  bestProvider?: ProviderKey;
  worstProvider?: ProviderKey;
  trend?: number;
  history: PromptHistoryEntry[];
}

/**
 * One point on the per-provider visibility line chart.
 * Internal provider keys: no hyphens, even though the API returns
 * "google-aio" and "google-aim".
 */
export type ProviderKey =
  | 'chatgpt'
  | 'gemini'
  | 'perplexity'
  | 'googleaio'
  | 'googleaimode';

export interface DailyTrendPoint {
  date: string;             // human label, e.g. "May 18"
  iso_date: string;         // ISO date for filtering
  visibility: number;       // overall, 0-100
  chatgpt: number;
  gemini: number;
  perplexity: number;
  googleaio: number;
  googleaimode: number;
}

/**
 * Per-brand global timeline used by the Competitors view and the
 * Overview "visibility over time" chart. Lives at
 * window._aimBrandTimeline. The injected `competitorTrend` always
 * overwrites the snapshot's `brand_timeline` here (see
 * ARCHITECTURE.md section 7).
 */
export interface BrandTimelinePoint {
  date: string;
  iso_date: string;
  [brandName: string]: number | string;  // brand name -> visibility 0-100
}

/**
 * Domain-level source used by the Sources view and the Overview
 * top sources card.
 */
export interface SourceDomain {
  domain: string;
  favicon: string;
  mentions: number;
  share: number;            // percentage 0-100
  trend?: string;           // formatted delta, e.g. "+12%"
  dr?: number;              // Domain Rating (Ahrefs / DataForSEO)
  contentType?: ContentType;
}

export type ContentType =
  | 'editorial'
  | 'product'
  | 'forum'
  | 'video'
  | 'social'
  | 'review'
  | 'docs'
  | 'news'
  | 'directory'
  | 'other';

/**
 * URL-level source aggregated from PromptHistoryEntry.sources[].
 * The API does not expose URL counts directly; the dashboard builds
 * this client-side. In the Next.js port, do this aggregation in a
 * scheduled job and store on disk.
 */
export interface TopSourceUrl {
  url: string;
  domain: string;
  title: string;
  favicon: string;
  mentions: number;
  share: number;
  pageType?: PageType;
  contentType?: ContentType;
}

export type PageType =
  | 'homepage'
  | 'product'
  | 'blog'
  | 'review'
  | 'comparison'
  | 'listicle'
  | 'docs'
  | 'forum-thread'
  | 'video'
  | 'other';

/**
 * Recent chat row on the Overview view. Built from the latest N
 * PromptHistoryEntry items across all prompts.
 */
export interface RecentChat {
  promptId: string;
  promptText: string;
  aiModel: ProviderKey | string;
  date: string;             // ISO
  mentioned: boolean;
  rank: number | null;
  sentiment?: Sentiment | null;
  snippet?: string;
}

/**
 * Sentiment structured entry. One per prompt x model x date with a
 * non-null sentiment value. Materialised by aimBuildSE (line 7366)
 * and cached in window._aimSE.
 */
export interface StructuredSentimentEntry {
  promptId: string;
  promptText: string;
  category: string;
  searchIntent: SearchIntent;
  aiModel: ProviderKey | string;
  date: string;             // ISO
  sentiment: Sentiment;
  sentimentScore?: number;
  snippet: string;
  fullResponse?: string;
}

/**
 * Competitor mention aggregate used by the Competitors view's
 * mentions chart and prompt x brand matrix.
 */
export interface CompetitorMention {
  brandName: string;
  total: number;
  byModel: Partial<Record<ProviderKey, number>>;
  byPrompt: Record<string, number>;  // promptId -> count
  sentiment: {
    positive: number;
    neutral: number;
    negative: number;
  };
}

/**
 * Heatmap cell for the brand x model heatmap. Snapshot wins;
 * AIM_INJECTED_DATA only fills cells where snapshot did not emit.
 */
export interface HeatmapCell {
  brand: string;
  model: ProviderKey;
  value: number | null;       // 0-100, null if no data
  source: 'snapshot' | 'injected';
}

/**
 * Todo / Action Plan entity. Generated by aimGenerateTodos (line
 * 14318); children are materialised lazily by _aimExpandTodo
 * (line 14275) from parent.suggestions[].
 */
export interface Todo {
  id: string;
  parentId?: string;          // set only for child todos
  title: string;
  type: TodoType;
  priority: 'P1' | 'P2' | 'P3';
  effort: 1 | 2 | 3 | 4 | 5;
  page?: string;              // related page/URL
  status: 'open' | 'in_progress' | 'done' | 'archived';
  added?: boolean;            // user-flagged "added to plan"
  signals: TodoSignal[];      // evidence cards
  steps: TodoStep[];          // ordered steps
  suggestions: TodoSuggestion[];  // child todos
  _groupLabel?: string;       // bucket label shown in why panel
  brands?: string[];          // brand badges (multi-brand context)
  notes?: string;             // user-editable
  createdAt: string;
  completedAt?: string;
}

export type TodoType =
  | 'content'
  | 'technical'
  | 'authority'
  | 'reputation'
  | 'visibility'
  | 'sentiment'
  | 'competitor';

export interface TodoSignal {
  text: string;
  favDomain?: string;       // domain for the favicon chip
  metric?: string;          // e.g. "Visibility -12pt"
}

export interface TodoStep {
  text: string;
  expandItems?: string[];   // bullet list shown when row expanded
}

export interface TodoSuggestion {
  title: string;
  steps: TodoStep[];
  signals: TodoSignal[];
  _groupLabel?: string;
}

/**
 * Full snapshot payload. This is the type of window._AIM_SNAPSHOT
 * as it ships from the Python tool today. Keep it close to the
 * Python tool's output, do not refactor in the React layer.
 */
export interface PeekabooSnapshot {
  generated_at: string;
  brand: string;
  brand_id: string;
  all_brands: Brand[];
  total_runs: number;
  overall_visibility: number;
  overall_avg_position: number;
  daily_trend: DailyTrendPoint[];
  latest_by_provider: Partial<Record<ProviderKey, {
    visibility: number;
    sentiment: number;
    position: number | null;
  }>>;
  prompt_responses: Record<string, PromptHistoryEntry[]>;
  top_sources: Array<{
    domain: string;
    citation_count: number;
  }>;
  recent_chats: RecentChat[];
  competitors: Competitor[];
  comp_mentions?: Record<string, CompetitorMention>;
  brand_timeline?: BrandTimelinePoint[];
  brand_timeline_by_provider?: Partial<Record<ProviderKey, BrandTimelinePoint[]>>;
  sentiment_entries?: StructuredSentimentEntry[];
  aiSuggestions?: AISuggestion[];
}

/**
 * Secondary payload. Treat as additive and partial.
 * `competitorTrend` ALWAYS overwrites snapshot.brand_timeline at the
 * timeline chart layer; everywhere else, injected only fills gaps.
 */
export interface AimInjectedData {
  competitorTrend?: BrandTimelinePoint[];
  competitorTrendByProv?: Partial<Record<ProviderKey, BrandTimelinePoint[]>>;
  heatmapFills?: HeatmapCell[];
  recentChatsExtra?: RecentChat[];
}
```

## 2. Naming reconciliation

Where API field names, dashboard variable names, and recommended production names diverge.

| API field | Dashboard variable | Recommended production name | Notes |
|---|---|---|---|
| `aiModel` | `aiModel` / sometimes mis-read as `model` | `provider` | Add a Zod transform that maps `aiModel` to `provider`. Forbid raw `.model` reads. |
| `google-aio` | `googleaio` | `googleaio` (internal) / `google-aio` (wire) | Map at the API boundary only. Pick one and stick to it. |
| `google-aim` | `googleaimode` | `googleaimode` (internal) / `google-aim` (wire) | Same. |
| `searchIntent` | `searchIntent` (PromptMetric), `intent` (filter) | `searchIntent` | Filter state can stay `intent`; type the enum. |
| `score` (visibility) | `visibility` | `visibilityScore` | API uses `score`; dashboard renames to `visibility`. Recommend `visibilityScore` to avoid confusion with `sentimentScore`. |
| `bestScore` / `worstScore` | `bestScore` / `worstScore` | `visibilityScoreMax` / `visibilityScoreMin` | Optional rename for clarity. |
| `promptId` (UUID) | `promptId` + dashboard-local `numericId` | `promptId` (UUID) only | Drop the numeric local id; React keys can be the UUID. |
| `brand_timeline` (snapshot) | `_aimBrandTimeline` | `perPromptVisibilityTimeline` | This is the per-prompt position-weighted series. |
| `competitorTrend` (injected) | also `_aimBrandTimeline` after `aimApplyInjectedData` overwrites | `globalVisibilityTimeline` | This is the global series. They are different metrics. Give them different names. |
| `top_sources[].citation_count` | `mentions` | `citationCount` | Pick one and use it everywhere. |
| `latest_by_provider[k].visibility` | `AIM_VIS_BY_MODEL[k][0]` | `latestVisibilityByProvider[k]` | The `[0]` index is "latest", `[1]` is "delta", etc. Make this a named struct. |
| `competitors[].monthlyTraffic` | `b.monthlyTraffic` | `monthlyOrganicTraffic` | Match the Ahrefs / DataForSEO column it maps to. |
| `mentioned` (boolean on history) | `mentioned` | `mentioned` | OK as is. |
| `sentimentScore` | `sentimentScore` | `sentimentScore` (numeric) | Keep distinct from `sentiment` (label). |
| `category` (prompt) | `topic` (filter), `category` (prompt) | `category` everywhere | The filter is called Topic in the UI but the data field is `category`. Standardise. |
| `aiSuggestions` (snapshot) | `aiSuggestions` | `promptSuggestions` | Avoid "AI" prefix on internal types; reserve for user-facing copy. |

## 3. Recommended Zod schema pattern

Use one schema per endpoint, with transforms to normalise the divergent fields above. Example sketch:

```ts
import { z } from 'zod';

export const ProviderKey = z.enum([
  'chatgpt', 'gemini', 'perplexity', 'googleaio', 'googleaimode'
]);

export const PromptHistoryEntrySchema = z.object({
  aiModel: z.string(),
  date: z.string(),
  score: z.number(),
  rank: z.number().nullable(),
  mentioned: z.boolean(),
  sentiment: z.enum(['positive', 'neutral', 'negative']).nullable().optional(),
  brandMentions: z.array(BrandMentionSchema).default([]),
  sources: z.array(SourceSchema).default([]),
  fullResponse: z.string().optional(),
  responseSnippet: z.string().optional(),
}).transform((row) => ({
  ...row,
  provider: mapApiModelToProviderKey(row.aiModel), // canonical internal key
}));
```

Centralise `mapApiModelToProviderKey` (and the inverse for write endpoints) in `lib/providerKey.ts` and re-use everywhere.

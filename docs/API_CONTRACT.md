# AI Peekaboo API Contract

This document is the canonical reference for the AI Peekaboo REST API as consumed by the prototype in this repo. It captures every endpoint, parameter, pitfall, and rate-limit rule that the Python snapshot tool (`tools/peekaboo-snapshot/`) relies on today, and provides porting guidance for the Next.js 14 + Prisma + PlanetScale production app. Reads in this doc are taken from the live API reference and verified against actual snapshot runs against `aipeekaboo.com`.

Last verified: 2026-05-20.

Reference document for porting the AI Peekaboo data pipeline from Python to Next.js 14 + Prisma + PlanetScale. Reflects the live API as consumed by `tools/peekaboo-snapshot/` and verified against the AI Peekaboo API reference (May 2026).

## 1. Auth and Base URL

| Field | Value |
|---|---|
| Base URL | `https://www.aipeekaboo.com/api/v1` (note: NOT `api.aipeekaboo.com`) |
| Auth header | `X-API-Key: pk_<projectId>_<secret>` |
| Accept | `application/json` |
| Content-Type (writes) | `application/json` |

Two key types issued in Settings, Integrations: Read (every GET) and Read + Write (POST/PUT/DELETE). Keys are project-scoped; revocation is immediate; full secret only shown once at generation.

Response envelope (success):

```json
{
  "success": true,
  "data": { },
  "pagination": { "offset": 0, "limit": 50, "total": 42, "hasMore": false },
  "metadata": { "requestId": "...", "timestamp": "...", "queryTimeMs": 245 }
}
```

`pagination` only appears on list endpoints. Client code should read `body.data` and fall back to `body`.

Error codes: `UNAUTHORIZED 401`, `FORBIDDEN 403`, `SUBSCRIPTION_INACTIVE 403`, `LIMIT_EXCEEDED 403`, `NOT_FOUND 404`, `INVALID_PARAMS 400`, `CONFLICT 409`, `RATE_LIMITED 429`, `INTERNAL_ERROR 500`.

## 2. Rate Limits

| Plan | Per minute | Per day |
|---|---|---|
| Grow | 20 | 1,000 |
| Pro / Enterprise | 40 | 2,000 |

Every response carries: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (Unix seconds), `X-RateLimit-Daily-Limit`, `X-RateLimit-Daily-Remaining`.

The Python client throttles to 18 req/min for safety, sleeps until `X-RateLimit-Reset` when remaining drops below 3, and uses exponential backoff (2^n) on transient errors. For the Next.js port: route this through a server-side queue (BullMQ or Trigger.dev) so user-facing routes never block on the upstream API.

## 3. Endpoints

### 3.1 GET /brands

List every brand in the project. No parameters.

### 3.2 GET /brands/:brandId

Brand detail. Adds `productDescription`, `language`, `location`, `analysisEnabled`, `promptCount`, `competitorCount` to the list-call fields. Pitfall: the prototype loops this per brand, burning ~N requests for fields rarely shown. See section 6.

### 3.3 GET /brands/:brandId/snapshot  (recommended default)

Pre-computed nightly aggregate. Returns everything most dashboards need in 300 to 500ms. Fields: `visibility.score`, `visibility.totalChatsAnalyzed`, `competitors[]`, `topSources[]`, `topPrompts[]`, `aiSuggestions[]`, `traffic.monthly`. Snapshot is nightly, so same-day analyses won't reflect until the next cycle.

### 3.4 GET /brands/:brandId/prompts

| Param | Type | Notes |
|---|---|---|
| `time_range` | `'7d' \| '30d' \| '90d'` | Default `7d`. Any other value silently falls back to `7d`, so lint or type-guard this. |
| `category` | string | Filter by category name |
| `search_intent` | enum | One of `INFORMATIONAL`, `COMMERCIAL`, `TRANSACTIONAL`, `NAVIGATIONAL`, `LOCAL`, `INVESTIGATIONAL`, `SENTIMENT`, `BRANDED` |
| `offset` | int | default 0 |
| `limit` | int | default 50, max 200 |

Response items: `promptId`, `promptText`, `category`, `searchIntent`, `score`, `bestScore`, `worstScore`, `trend?`.

### 3.5 GET /brands/:brandId/prompts/:promptId  (the richest endpoint)

| Param | Type | Notes |
|---|---|---|
| `time_range` | `'7d' \| '30d' \| '90d'` | Same silent-fallback rule |
| `include_full_response` | `'true' \| 'false'` | When `true`, each history entry includes `fullResponse` (uncapped LLM text) |

Returns: `promptId`, `promptText`, `category`, `searchIntent`, `history[]`, `sourceSummary[]`.
`Cache-Control: private, max-age=120`, respect it.

Critical pitfalls (load-bearing for the port):

- AI model field is `history[].aiModel`, NOT `history[].model`. Reading `.model` returns `undefined`. Use a defensive fallback or a Zod transform.
- Hard cap of 100 entries per call. Pagination is always `null`; `offset` and `limit` are ignored.
- Daily brands hit the cap at ~20 days (5 entries per run x 20 days = 100). `30d` and `90d` return identical data for daily brands. To retain anything older than ~20 days, pull and persist on a schedule.
- `fullResponse` ships entire LLM responses inline (tens of KB per entry). Plan storage accordingly. The Python script truncates to 4,000 chars; the production app should probably store full and truncate at the API or UI boundary.

### 3.6 GET /brands/:brandId/competitors

No documented filters. Returns `{ competitors: Competitor[] }`. The prototype keeps whichever is longer between this and `snapshot.competitors`; the production app should prefer `/snapshot.competitors` and only fall back to `/competitors` if that array is empty.

### 3.7 Documented but currently unused

`GET /visibility` (5 to 10s response time, avoid for live UI), `GET /sources`, `GET /categories`, all write endpoints (`POST/PUT/DELETE` for brands, prompts, prompts/bulk, prompts/bulk-delete, competitors, competitors/bulk, categories). Bulk writes count as one rate-limited request and accept up to 100 prompts or 50 competitors per call.

## 4. Cost Per Run (Grow tier, 20 req/min)

| Endpoint | Cost | Notes |
|---|---|---|
| `/brands` | 1 | Single call covers the dropdown |
| `/brands/:id` | N (one per brand) | The expensive one, script loops every brand |
| `/snapshot` | 1 per brand displayed | Cheap (300 to 500ms) |
| `/prompts` | 1 per brand | Even with `limit=200` |
| `/prompts/:id` | N (one per prompt) | 20 to 100+ calls per brand |
| `/competitors` | 1 per brand | Redundant with `/snapshot.competitors` |
| `/visibility` | 1, but 5 to 10s wall time | Avoid for dashboards |

A typical AI Peekaboo run (~2 brands, ~38 prompts): roughly 35 calls, well under daily budget, but 2+ minutes wall time on Grow tier due to throttling.

## 5. Suggestions for the Next.js Port

1. Drop the per-brand `/brands/:id` loop. Lazy-load detail when a brand is selected, OR cache in Prisma and refresh nightly.
2. Pick one source of truth for competitors. Prefer `/snapshot.competitors`; fall back to `/competitors` only if empty.
3. Persist `/prompts/:id` history server-side. Schedule a Trigger.dev job that upserts new entries into PlanetScale (key on `promptId + date + aiModel`) for unlimited retention and zero-API-call reads.
4. Honour `Cache-Control: max-age=120`. `revalidate: 120` on prompt-detail server actions.
5. Standardise field defensiveness in one Zod schema per endpoint. Bare-array vs `{ brands: [...] }` vs `{ data: [...] }` shapes; `aiModel` vs `.model`.
6. Lint `time_range`. Only `7d`, `30d`, `90d` work. Anything else silently downgrades to `7d`.
7. Use a concurrency limiter (`p-limit` ~15) plus a token bucket honoring `X-RateLimit-Remaining`.
8. Source URLs only exist on `/prompts/:id`. Other endpoints return domains only. The dashboard's URL-level views must aggregate from prompt-detail responses.
9. Use write endpoints in onboarding (`POST /brands`, `POST /brands/:id/prompts/bulk`, `POST /brands/:id/competitors/bulk`).
10. Treat `/visibility` as deprecated for live UI. Cron it and serve from DB.

## 6. Known Issues in the Prototype Today

- Per-brand `/brands/:id` loop burns 20+ requests for low-value fields.
- Double-fetches competitors from both `/snapshot` and `/competitors`.
- Time range `'1y'` and other invalid values are silently treated as `7d`, never surfaced as an error.
- The 4,000-char truncation of `fullResponse` is set in the Python script as a single global constant; the dashboard sometimes needs the full text (sentiment view) and sometimes a snippet (table rows), so the production app should split this concern.

## See also

- [./ARCHITECTURE.md](./ARCHITECTURE.md) for how the dashboard consumes this API.
- [./DATA_MODEL.md](./DATA_MODEL.md) for the TypeScript interfaces that wrap these responses.
- [./HANDOFF.md](./HANDOFF.md) for the broader handover context.

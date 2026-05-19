# Handoff

Audience: John, CTO co-founder, picking up the AI Peekaboo dashboard prototype and rebuilding it as a production Next.js application.

## 1. What this repo is

This repo is a design-handoff artifact, not a production codebase. It contains two things:

1. `dashboard.html`, a single-file HTML prototype (~17,600 lines, vanilla JS + Chart.js 4) that is the UI/UX specification for the production app. Every view, every interaction, every component layout is final here. The product designer (Filipe) iterates on this file directly because it has no build step.
2. `tools/peekaboo-snapshot/`, a Python data generator that calls the live AI Peekaboo REST API, writes a `snapshot.json`, and inlines it into `dashboard.html` between two HTML comment markers. This lets the design be validated against real data before any production code is written.

The expectation is that you will port each view of `dashboard.html` to a React component, swap the inlined snapshot for live data via Prisma and Trigger.dev, and ship the result as the new aipeekaboo.com dashboard.

## 2. Where to start

Read in this order. Each doc builds on the previous one.

1. [./HANDOFF.md](./HANDOFF.md), this file. The why and the rules of the road.
2. [./ARCHITECTURE.md](./ARCHITECTURE.md), how the prototype is organised, view by view, with line numbers, key function inventory, filter and state model, data flow diagram, a proposed React component tree, and the non-obvious footguns.
3. [./API_CONTRACT.md](./API_CONTRACT.md), the upstream AI Peekaboo REST API: endpoints, params, rate limits, response envelopes, and the silent failure modes (silent fallback on `time_range`, hard cap of 100 history entries per prompt, `aiModel` vs `.model`).
4. [./DATA_MODEL.md](./DATA_MODEL.md), TypeScript interfaces for every entity in the system, both the API wire shapes and the dashboard's internal shapes, plus a naming-reconciliation table to standardise across the API, the prototype, and the production app.

## 3. The two-file system

`dashboard.html` is the prototype. It is intentionally a single file so Filipe can open it directly with `file://` and iterate on copy, layout, and interactions in seconds. There is no module system, no router, and no transpilation. All state is module-scope `let` bindings. Charts use Chart.js 4 directly.

`tools/peekaboo-snapshot/` is the data injector. It calls the AI Peekaboo API (see [./API_CONTRACT.md](./API_CONTRACT.md)), writes a snapshot, and patches `dashboard.html` so the file renders standalone with real data. This is the validation loop: design, inject, eyeball, iterate.

The split exists because Filipe and John work in parallel: Filipe designs in HTML for fastest iteration, John ports each view to a React component on the production side. The HTML never becomes the production app; it is the spec.

## 4. Tech stack target

These were agreed during planning. See `project_peekaboo_nextjs_website.md` in Filipe's memory if you need the full context.

- Next.js 14 with the App Router and React Server Components
- TypeScript
- Tailwind for layout, with custom CSS variables for the design tokens
- Radix UI primitives (Dialog, Popover, Select, Tabs)
- Lucide for icons (replace the inline SVGs in the prototype)
- Recharts for charts (replace Chart.js 4)
- Zustand for client-side filter and UI state
- Prisma + PlanetScale for the database
- Trigger.dev for the snapshot cron and any background ingestion
- Vercel for hosting

## 5. The product

AI Peekaboo monitors how brands are mentioned across AI models, ChatGPT, Gemini, Perplexity, Google AI Overviews, and Google AI Mode, when users ask the kinds of questions that used to be Google searches. The dashboard surfaces:

- Visibility score over time, per provider and overall
- Competitive position vs. tracked competitors, plus a brand x model heatmap and a prompt x brand matrix
- Source citations, what URLs and domains the AI models pull from when answering
- Sentiment of how the brand is framed in responses (positive, neutral, negative, with category breakdown)
- An action plan: heuristic todos that translate the data into concrete next steps

A 30-second pitch lives at aipeekaboo.com.

## 6. Critical rules that don't show up in code

These are non-obvious decisions Filipe made during prototyping. They are easy to miss when reading code in isolation.

- The UI/UX in `dashboard.html` is final. Don't redesign during the port. If a layout or interaction looks redundant, assume it is intentional and ask first. Port faithfully.
- Use the design tokens documented in `reference_peekaboo_design_system_bundle.md` (Filipe's memory). Inter font, `#b352b3` primary purple, the specific hero gradient, radii, shadows, type scale, buttons, inputs. The prototype already follows these; the React port should compile them into a Tailwind config plus a CSS variable layer.
- Provider keys: internal storage and CSS hooks use `chatgpt`, `gemini`, `perplexity`, `googleaio`, `googleaimode`. The API returns hyphenated keys (`google-aio`, `google-aim`). Translate once at the API boundary. See [./DATA_MODEL.md](./DATA_MODEL.md) section 2.
- Competitor visibility uses the GLOBAL score everywhere, not the per-prompt filter-aware score. The Overview competitors mini-table sorts by `brand.visibility`, NOT `aimGetBrandMetrics(brand).vis`. See [./ARCHITECTURE.md](./ARCHITECTURE.md) section 7.
- No em dashes in user-facing text. Anywhere. Comma, colon, or reword. This is a hard rule Filipe enforces across all surfaces.
- All user-supplied strings must go through an HTML-escape equivalent before injection. In the prototype this is `aimEscHtml`; in React, lean on JSX rendering and only fall back to a manual escape for `dangerouslySetInnerHTML` paths or clipboard / file writes. XSS preventative is non-negotiable.
- The snapshot is the primary data source. `AIM_INJECTED_DATA` is a legacy secondary payload that ONLY fills a few specific gaps (`competitorTrend`, `competitorTrendByProv`, some heatmap fills). Don't reinvent this dual-source pattern in the React app; consolidate on a single Prisma-backed model and drop the secondary payload entirely.

## 7. How to run the data tool

```bash
cd tools/peekaboo-snapshot
pip install -e .
export PEEKABOO_API_KEY=pk_...
export PEEKABOO_BRAND_ID=...
peekaboo-snapshot --time-range 30d --dashboard ~/Desktop/ai-monitoring-dashboard-v3.html
```

The tool fetches a full set of API responses, writes `snapshot.json` next to the dashboard HTML, then patches the HTML between the `AIM_SNAPSHOT_INJECT_START` and `AIM_SNAPSHOT_INJECT_END` markers. Reload the HTML in your browser to see the new data.

If you want to test the dashboard with a fresh API key, generate a Read key in Settings, Integrations on aipeekaboo.com and export it as `PEEKABOO_API_KEY`. The brand id is visible in the URL when you select a brand in the live app.

## 8. Open questions for the production app

These are not yet decided. Each one is worth a short alignment call before you commit to an approach.

- Onboarding flow design. The prototype has a stub onboarding flow (see `aimOpenAddBrand` and `_aimNb*` in `dashboard.html`); Filipe is still iterating on this in a separate file (`~/Desktop/peekaboo-onboarding-v2.html`). Don't lift the prototype version directly until the v2 design lands.
- White-label routing. The Settings, White-Label tab has UI for it but no decision yet on subdomain vs. custom-domain vs. per-brand theming at the route level.
- Share-link generation. Stub buttons exist; the canonical URL pattern, expiry, and access scope are TBD.
- GSC OAuth scope. Search Console view uses static mock data (`window.AIM_SC_DATA`). Production needs real GSC integration; the OAuth scope (`webmasters.readonly` vs. `webmasters`) and refresh-token handling are not yet decided.
- Trigger.dev vs. Inngest for the snapshot cron. Trigger.dev is the working assumption, but no contract is signed.
- Where prompt history lives long-term. The API hard-caps `/prompts/:id` at 100 entries; the production app must persist this. Decision needed on retention (90 days? 1 year? forever?) and on whether to store `fullResponse` inline or in object storage.

## 9. Where to find Filipe

- Email: `filipe@aipeekaboo.com`
- Calendly (30 min): `https://calendly.com/filipe-aipeekaboo/30min`
- Live product: `https://aipeekaboo.com`
- Public repo: `https://github.com/filipelinsduarte/ai-visibility-dashboard`

For anything load-bearing (rule changes, design decisions, API surface), grab time on Calendly. For small clarifications, email or Slack is faster.

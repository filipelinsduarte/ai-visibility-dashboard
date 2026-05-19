"""Pure aggregation functions producing the dashboard-shaped snapshot.

Every function here is side-effect free: it takes typed inputs and returns
typed outputs. No I/O, no logging, no global state. This is the layer that
gets unit-tested with fixtures.
"""

from __future__ import annotations

import datetime
import re
from collections import defaultdict
from typing import Iterable
from urllib.parse import urlparse

from peekaboo_snapshot.models import (
    BrandPosition,
    Competitor,
    CompetitorEntity,
    DailyTrendPoint,
    FlatResponse,
    PromptAnalysisEntry,
    PromptDetail,
    PromptHistoryEntry,
    PromptMetric,
    PromptMetricByProvider,
    ProviderSnapshot,
    SEEntry,
    SourceTally,
    TimelinePoint,
    TopSource,
    TopSourceUrl,
)

# ─── Constants ──────────────────────────────────────────────────────────────

MODEL_KEY: dict[str, str] = {
    "gpt-4o-mini": "chatgpt",
    "gpt-4o": "chatgpt",
    "chatgpt": "chatgpt",
    "gemini-2.5-flash": "gemini",
    "gemini-2.0-flash": "gemini",
    "gemini": "gemini",
    "sonar": "perplexity",
    "sonar-pro": "perplexity",
    "perplexity": "perplexity",
    "google-aio": "googleaio",
    "google-ai-overview": "googleaio",
    "google-ai-mode": "googleaimode",
}

MODEL_DISPLAY: dict[str, str] = {
    "chatgpt": "ChatGPT",
    "gemini": "Gemini",
    "perplexity": "Perplexity",
    "googleaio": "Google AIO",
    "googleaimode": "Google AI Mode",
}

ALL_PROVIDERS: list[str] = [
    "chatgpt",
    "gemini",
    "perplexity",
    "googleaio",
    "googleaimode",
]

SENT_SCORE: dict[str, int] = {"positive": 75, "neutral": 50, "negative": 25}

HM_PROV_KEY: dict[str, str] = {
    "chatgpt": "chatgpt",
    "gemini": "gemini",
    "perplexity": "perplexity",
    "googleaio": "google-aio",
    "googleaimode": "google-aim",
}


# ─── Small helpers ─────────────────────────────────────────────────────────


def sent_label(raw: str | None) -> str:
    """Normalize any sentiment input to one of ``positive``/``neutral``/``negative``."""
    if raw is None:
        return "neutral"
    s = str(raw).lower().strip()
    return s if s in ("positive", "negative", "neutral") else "neutral"


def fmt_date(iso: str) -> str:
    """Format an ISO date to ``Mon D`` (e.g. ``May 12``); falls back to the input."""
    try:
        d = datetime.date.fromisoformat(iso[:10])
        return f"{d.strftime('%b')} {d.day}"
    except ValueError:
        return iso[:10]


def _norm_key(name: str) -> str:
    """Normalize a brand name for deduplication: lowercase, strip suffixes."""
    n = name.strip()
    n = re.sub(r"\s+(ai|io|radar)$", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\.(ai|io|com|dev|net|org)$", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\s+", " ", n).strip()
    return re.sub(r"[^a-z0-9]", "", n.lower())


def _comp_lookup(raw_map: dict[str, object], name: str) -> object | None:
    """Case-insensitive + suffix-stripped lookup for competitor accumulators."""
    key = name.lower().strip()
    if key in raw_map:
        return raw_map[key]
    bare = re.sub(r"\s*(ai|io)$", "", key, flags=re.IGNORECASE).strip()
    for k, v in raw_map.items():
        k2 = k.lower().strip()
        if (
            k2 == bare
            or re.sub(r"\s*(ai|io)$", "", k2, flags=re.IGNORECASE).strip() == bare
        ):
            return v
    return None


# ─── Per-entry processing primitives ───────────────────────────────────────


def _entry_provider(entry: PromptHistoryEntry) -> str | None:
    """Map a history entry's model name to the internal provider key."""
    raw_model = entry.model_name()
    return MODEL_KEY.get(raw_model)


def _entry_date(entry: PromptHistoryEntry) -> str:
    """Return the YYYY-MM-DD prefix of an entry date, or ''."""
    return (entry.date or "")[:10]


def _peekaboo_brand_sentiment(
    bm_list: list,
    fallback_score: int,
) -> int:
    """Pick brand-level sentiment for the main brand within a single run."""
    pb_entry = next(
        (
            bm
            for bm in bm_list
            if bm.type not in ("competitor", "untracked")
            or "peekaboo" in (bm.entityName or "").lower()
        ),
        None,
    )
    raw_sent = pb_entry.sentiment if pb_entry else None
    return SENT_SCORE.get(sent_label(raw_sent), fallback_score)


# ─── Aggregation results bundle ────────────────────────────────────────────


class _AggregationState:
    """Mutable accumulator used while iterating prompt history.

    Encapsulates the dozen-or-so defaultdicts the legacy script kept in one
    function-local scope. Methods on it are intentionally low-level; the
    public aggregator functions below own the final shaping.
    """

    def __init__(self) -> None:
        self.prompt_response_history: dict[str, dict[str, dict[str, FlatResponse]]] = {}
        self.prompt_responses: dict[str, dict[str, FlatResponse]] = {}
        self.prompt_analysis: dict[str, PromptAnalysisEntry] = {}
        self.prompt_metrics: list[PromptMetric] = []
        self.all_responses_flat: list[FlatResponse] = []
        self.prompt_matrix_data: dict[str, list[BrandPosition]] = {}

        self.daily_prov_scores: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.latest_prov_data: dict[
            str, list[tuple[str, float, float, float | None]]
        ] = defaultdict(list)
        self.source_count: dict[str, int] = defaultdict(int)
        self.source_runs_map: dict[str, set[str]] = defaultdict(set)
        self.source_url_runs_map: dict[str, set[str]] = defaultdict(set)
        self.source_url_count: dict[str, int] = defaultdict(int)
        self.source_url_meta: dict[str, dict[str, str]] = {}
        self.brand_timeline_raw: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.bt_by_prov_raw: dict[
            str, dict[str, dict[str, list[float]]]
        ] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        self.src_by_date_raw: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self.src_by_prov_raw: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self.global_entity_model_scores: dict[
            str, dict[str, list[float]]
        ] = defaultdict(lambda: defaultdict(list))
        self.comp_sentiment_raw: dict[str, dict[str, float]] = defaultdict(
            lambda: {"sum": 0.0, "count": 0}
        )
        self.comp_position_raw: dict[str, dict[str, float]] = defaultdict(
            lambda: {"sum": 0.0, "count": 0}
        )
        self.source_url_prov_raw: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self.brand_global_vis_raw: dict[str, float] = defaultdict(float)
        self.total_processed_entry_count: int = 0
        self.global_brand_counts: dict[str, int] = defaultdict(int)


# ─── Top-level orchestrating builder ───────────────────────────────────────


def aggregate(
    prompts: list[dict[str, str]],
    details: dict[str, PromptDetail],
    competitors: list[Competitor],
    max_history_dates: int,
    max_text_len: int,
) -> _AggregationState:
    """Walk every prompt × run pair, populating an :class:`_AggregationState`.

    ``prompts`` is a list of small dicts: ``{"prompt_id": ..., "ap_id": ...}``.
    ``details`` maps prompt_id -> PromptDetail. The function mutates and
    returns an aggregation state for the higher-level builders below.
    """
    state = _AggregationState()
    comp_name_map = {
        (c.name or "").lower(): (c.url or "") for c in competitors if c.name
    }

    for p in prompts:
        pid = p["prompt_id"]
        ap_id = p["ap_id"]
        det = details.get(pid)
        if det is None:
            continue
        history = det.history or []

        by_date_prov: dict[str, dict[str, FlatResponse]] = defaultdict(dict)
        vis_by_prov: dict[str, list[float]] = defaultdict(list)
        sent_by_prov: dict[str, list[float]] = defaultdict(list)
        pos_by_prov: dict[str, list[float]] = defaultdict(list)
        brand_counts: dict[str, int] = defaultdict(int)
        domain_counts: dict[str, int] = defaultdict(int)

        for entry in history:
            prov_key = _entry_provider(entry)
            if not prov_key:
                continue
            entry_date = _entry_date(entry)
            if not entry_date:
                continue

            state.total_processed_entry_count += 1
            score = float(entry.score or 0.0)
            rank = entry.rank
            is_mentioned = bool((entry.mentioned or False) or score > 0)
            run_id = entry.runId or f"{ap_id}_{entry_date}_{prov_key}"

            bm_list = entry.brandMentions or []
            e_sent_score = _peekaboo_brand_sentiment(bm_list, fallback_score=50)
            e_sent_label = "positive" if e_sent_score >= 65 else (
                "negative" if e_sent_score <= 35 else "neutral"
            )

            # Sources
            src_objs: list[dict[str, str]] = []
            for s in entry.sources or []:
                dom = s.domain or ""
                url = s.url or ""
                lbl = s.title or dom
                src_objs.append({"domain": dom, "url": url, "label": lbl})
                if dom:
                    domain_counts[dom] += 1
                    state.source_count[dom] += 1
                    state.source_runs_map[dom].add(run_id)
                    state.src_by_date_raw[entry_date][dom] += 1
                    state.src_by_prov_raw[prov_key][dom] += 1
                if url and dom:
                    state.source_url_count[url] += 1
                    state.source_url_runs_map[url].add(run_id)
                    if url not in state.source_url_meta:
                        state.source_url_meta[url] = {
                            "domain": dom,
                            "label": lbl,
                            "last_seen": entry_date,
                        }
                    elif entry_date > state.source_url_meta[url]["last_seen"]:
                        state.source_url_meta[url]["last_seen"] = entry_date
                    state.source_url_prov_raw[url][prov_key] += 1

            brands_in = [bm.entityName for bm in bm_list if bm.entityName]
            for b in brands_in:
                brand_counts[b] += 1
                state.global_brand_counts[b] += 1

            total_in_run = len(bm_list)
            for bm in bm_list:
                bname = (bm.entityName or "").strip()
                if not bname:
                    continue
                bscore = float(bm.score or 0.0)
                state.brand_timeline_raw[bname][entry_date].append(bscore)
                state.bt_by_prov_raw[bname][prov_key][entry_date].append(bscore)
                state.brand_global_vis_raw[bname] += bscore

                # Brand-level sentiment with response-level fallback.
                bm_sent: float | str | None
                bm_sent = bm.sentimentScore if bm.sentimentScore is not None else bm.sentiment
                if bm_sent is None:
                    bm_sent_num = float(e_sent_score)
                elif isinstance(bm_sent, str):
                    bm_sent_num = float(SENT_SCORE.get(sent_label(bm_sent), 50))
                else:
                    bm_sent_num = float(bm_sent)
                state.comp_sentiment_raw[bname]["sum"] += bm_sent_num
                state.comp_sentiment_raw[bname]["count"] += 1

                if total_in_run > 0:
                    derived_rank = total_in_run * (1.0 - bscore / 100.0) + 1.0
                    state.comp_position_raw[bname]["sum"] += derived_rank
                    state.comp_position_raw[bname]["count"] += 1

                state.global_entity_model_scores[bname][prov_key].append(bscore)

            full_text = (entry.fullResponse or entry.responseSnippet or "")[
                :max_text_len
            ]
            resp = FlatResponse(
                model=MODEL_DISPLAY[prov_key],
                date=entry_date,
                text=full_text,
                brands=brands_in,
                sources=[s.domain for s in (entry.sources or []) if s.domain],
                source_objects=src_objs,
                sentiment_label=e_sent_label,
                sentiment_score=float(e_sent_score),
                visibility_score=score,
                position=float(rank) if rank is not None else None,
                is_mentioned=1 if is_mentioned else 0,
                prompt_id=ap_id,
                prompt_text=det.promptText or "",
            )

            by_date_prov[entry_date][prov_key] = resp
            vis_by_prov[prov_key].append(score)
            sent_by_prov[prov_key].append(float(e_sent_score))
            if rank is not None:
                pos_by_prov[prov_key].append(float(rank))
            state.daily_prov_scores[entry_date][prov_key].append(score)
            state.latest_prov_data[prov_key].append(
                (entry_date, score, float(e_sent_score), float(rank) if rank is not None else None)
            )
            state.all_responses_flat.append(resp)

        sorted_dates = sorted(by_date_prov.keys(), reverse=True)
        history_dates = sorted_dates[:max_history_dates]
        state.prompt_response_history[ap_id] = {
            d: by_date_prov[d] for d in history_dates
        }

        latest_per_prov: dict[str, FlatResponse] = {}
        for d in sorted_dates:
            for prov, resp in by_date_prov[d].items():
                if prov not in latest_per_prov:
                    latest_per_prov[prov] = resp
        state.prompt_responses[ap_id] = latest_per_prov

        top_brands = sorted(brand_counts.items(), key=lambda x: -x[1])
        top_doms = sorted(domain_counts.items(), key=lambda x: -x[1])
        state.prompt_analysis[ap_id] = PromptAnalysisEntry(
            top_brand=top_brands[0][0] if top_brands else "",
            top_citation=top_doms[0][0] if top_doms else "",
            brands=[b for b, _ in top_brands[:8]],
            citations=[d for d, _ in top_doms[:8]],
        )

        # Prompt-level metrics.
        all_vis = [v for vv in vis_by_prov.values() for v in vv]
        all_sent = [s for ss in sent_by_prov.values() for s in ss]
        all_pos = [v for vv in pos_by_prov.values() for v in vv]
        vis_all = round(sum(all_vis) / len(all_vis), 2) if all_vis else 0.0
        sent_all = round(sum(all_sent) / len(all_sent), 2) if all_sent else 50.0
        pos_all = round(sum(all_pos) / len(all_pos), 2) if all_pos else None

        by_prov_m: dict[str, PromptMetricByProvider] = {}
        for prov in ALL_PROVIDERS:
            v = vis_by_prov.get(prov, [])
            s = sent_by_prov.get(prov, [])
            pp = pos_by_prov.get(prov, [])
            by_prov_m[prov] = PromptMetricByProvider(
                visibility=round(sum(v) / len(v), 2) if v else 0.0,
                sentiment=round(sum(s) / len(s), 2) if s else 50.0,
                position=round(sum(pp) / len(pp), 2) if pp else None,
            )

        # Per-prompt brand ranking list (prompt matrix).
        matrix_entry: list[BrandPosition] = []
        for name, cnt in sorted(brand_counts.items(), key=lambda x: -x[1])[:10]:
            url = comp_name_map.get(name.lower(), "")
            domain = ""
            if url:
                try:
                    domain = urlparse(url).netloc.replace("www.", "")
                except ValueError:
                    domain = ""
            matrix_entry.append(BrandPosition(n=name, count=cnt, d=domain))
        state.prompt_matrix_data[ap_id] = matrix_entry

        prompt_text = det.promptText or ""
        category = det.category or "General"
        search_intent = (det.searchIntent or "Informational").capitalize()
        last_run = sorted_dates[0] if sorted_dates else ""

        state.prompt_metrics.append(
            PromptMetric(
                prompt_id=ap_id,
                prompt_text=prompt_text,
                topic=category,
                intent=search_intent,
                visibility_all=vis_all,
                sentiment_all=sent_all,
                position_all=pos_all,
                by_provider=by_prov_m,
                last_run=last_run,
            )
        )

    return state


# ─── Public builder functions ──────────────────────────────────────────────


def build_daily_trend(state: _AggregationState) -> list[DailyTrendPoint]:
    """Roll up daily provider scores into a sorted ``daily_trend`` series."""
    out: list[DailyTrendPoint] = []
    for d in sorted(state.daily_prov_scores.keys()):
        pv = state.daily_prov_scores[d]
        all_today = [s for scores in pv.values() for s in scores]
        row: dict[str, float | str] = {
            "date": fmt_date(d),
            "iso_date": d,
            "visibility": round(sum(all_today) / len(all_today), 2)
            if all_today
            else 0.0,
        }
        for prov in ALL_PROVIDERS:
            scores = pv.get(prov, [])
            row[prov] = round(sum(scores) / len(scores), 2) if scores else 0.0
        out.append(DailyTrendPoint.model_validate(row))
    return out


def build_latest_by_provider(
    state: _AggregationState,
) -> dict[str, ProviderSnapshot]:
    """Compute the most-recent-day visibility/sentiment/position per provider."""
    out: dict[str, ProviderSnapshot] = {}
    for prov in ALL_PROVIDERS:
        entries = sorted(
            state.latest_prov_data.get(prov, []), key=lambda x: x[0], reverse=True
        )
        if not entries:
            out[prov] = ProviderSnapshot()
            continue
        latest_d = entries[0][0]
        recent = [e for e in entries if e[0] == latest_d]
        vis_avg = round(sum(e[1] for e in recent) / len(recent), 2)
        sent_avg = round(sum(e[2] for e in recent) / len(recent), 2)
        pos_vals = [e[3] for e in recent if e[3] is not None]
        pos_avg = round(sum(pos_vals) / len(pos_vals), 2) if pos_vals else None
        lbl = (
            "positive"
            if sent_avg >= 65
            else "negative"
            if sent_avg <= 35
            else "neutral"
        )
        out[prov] = ProviderSnapshot(
            visibility=vis_avg,
            sentiment=sent_avg,
            sentiment_label=lbl,
            position=pos_avg,
        )
    return out


def build_top_sources(state: _AggregationState) -> list[TopSource]:
    """Top 20 cited source domains by raw citation count."""
    rows = sorted(
        (
            TopSource(
                domain=d,
                citation_count=count,
                run_count=len(state.source_runs_map.get(d, set())),
            )
            for d, count in state.source_count.items()
        ),
        key=lambda x: -x.citation_count,
    )
    return rows[:20]


def build_top_source_urls(state: _AggregationState) -> list[TopSourceUrl]:
    """Top 300 cited source URLs with per-provider counts."""
    total_url = sum(state.source_url_count.values()) or 1
    rows: list[TopSourceUrl] = []
    for url, count in state.source_url_count.items():
        meta = state.source_url_meta[url]
        rows.append(
            TopSourceUrl(
                url=url,
                domain=meta["domain"],
                label=meta["label"],
                citation_count=count,
                run_count=len(state.source_url_runs_map.get(url, set())),
                last_seen=meta["last_seen"],
                share=round(count / total_url * 100, 1),
                by_provider=dict(state.source_url_prov_raw.get(url, {})),
            )
        )
    rows.sort(key=lambda x: -x.citation_count)
    return rows[:300]


def build_competitor_entities(
    state: _AggregationState, competitors: list[Competitor], total_runs: int
) -> list[CompetitorEntity]:
    """Combine tracked competitor metadata with derived sentiment/position."""
    sentiment_map = {
        k.lower().strip(): v for k, v in state.comp_sentiment_raw.items()
    }
    position_map = {
        k.lower().strip(): v for k, v in state.comp_position_raw.items()
    }
    mention_lookup = {
        k.lower().strip(): v for k, v in state.global_brand_counts.items()
    }

    out: list[CompetitorEntity] = []
    for c in competitors:
        name = c.name or ""
        vis = float(c.score or 0.0)
        sd = _comp_lookup(sentiment_map, name)
        ce_sent = (
            round(sd["sum"] / sd["count"])
            if isinstance(sd, dict) and sd["count"] > 0
            else 50
        )
        pd = _comp_lookup(position_map, name)
        ce_pos = (
            round(pd["sum"] / pd["count"], 1)
            if isinstance(pd, dict) and pd["count"] > 0
            else None
        )
        mc = mention_lookup.get(name.lower().strip(), 0)
        out.append(
            CompetitorEntity(
                name=name,
                visibility=round(vis, 2),
                rank=c.rank,
                sentiment=int(ce_sent),
                avg_position=ce_pos,
                mention_count=int(mc),
                run_count=int(total_runs),
            )
        )
    return out


def build_brand_timeline(
    state: _AggregationState, competitors: list[Competitor]
) -> dict[str, list[TimelinePoint]]:
    """Brand visibility series per date, deduplicated across spelling variants."""
    tracked_names = {(c.name or "").lower().strip() for c in competitors if c.name}
    top_global = sorted(state.global_brand_counts.items(), key=lambda x: -x[1])[:50]
    keep_names = tracked_names | {n.lower().strip() for n, _ in top_global}

    filtered: dict[str, dict[str, list[float]]] = {}
    for name, by_date in state.brand_timeline_raw.items():
        if name.lower().strip() in keep_names:
            filtered[name] = dict(by_date)

    norm_to_canonical: dict[str, str] = {}
    for name in filtered:
        nk = _norm_key(name)
        if nk not in norm_to_canonical:
            norm_to_canonical[nk] = name
        else:
            existing = norm_to_canonical[nk]
            is_tracked = name.lower().strip() in tracked_names
            existing_tracked = existing.lower().strip() in tracked_names
            if is_tracked and not existing_tracked:
                norm_to_canonical[nk] = name
            elif (
                not is_tracked and not existing_tracked and len(name) < len(existing)
            ):
                norm_to_canonical[nk] = name

    deduped: dict[str, dict[str, list[float]]] = {}
    for name, by_date in filtered.items():
        canonical = norm_to_canonical[_norm_key(name)]
        bucket = deduped.setdefault(canonical, {})
        for d, scores in by_date.items():
            bucket.setdefault(d, []).extend(scores)

    return {
        name: [
            TimelinePoint(date=d, visibility=round(sum(vs) / len(vs), 2))
            for d, vs in sorted(by_date.items())
        ]
        for name, by_date in deduped.items()
    }


def build_brand_timeline_by_provider(
    state: _AggregationState, competitors: list[Competitor]
) -> dict[str, dict[str, list[TimelinePoint]]]:
    """Per-provider brand timeline, sharing the same canonicalization rules."""
    tracked_names = {(c.name or "").lower().strip() for c in competitors if c.name}
    top_global = sorted(state.global_brand_counts.items(), key=lambda x: -x[1])[:50]
    keep_names = tracked_names | {n.lower().strip() for n, _ in top_global}

    base = build_brand_timeline(state, competitors)
    canonical_lookup: dict[str, str] = {_norm_key(k): k for k in base}

    filtered: dict[str, dict[str, dict[str, list[float]]]] = {}
    for name, by_prov in state.bt_by_prov_raw.items():
        if name.lower().strip() not in keep_names:
            continue
        canonical = canonical_lookup.get(_norm_key(name), name)
        target = filtered.setdefault(canonical, {p: {} for p in ALL_PROVIDERS})
        for prov in ALL_PROVIDERS:
            for d, scores in by_prov.get(prov, {}).items():
                target.setdefault(prov, {}).setdefault(d, []).extend(scores)

    return {
        name: {
            prov: [
                TimelinePoint(date=d, visibility=round(sum(vs) / len(vs), 2))
                for d, vs in sorted(by_date.items())
            ]
            for prov, by_date in by_prov.items()
        }
        for name, by_prov in filtered.items()
    }


def build_sources_by_date(
    state: _AggregationState,
) -> dict[str, list[SourceTally]]:
    """Top-10 source domains per ISO date."""
    return {
        d: [
            SourceTally(domain=dom, citation_count=count)
            for dom, count in sorted(counts.items(), key=lambda x: -x[1])[:10]
        ]
        for d, counts in state.src_by_date_raw.items()
    }


def build_sources_by_provider(
    state: _AggregationState,
) -> dict[str, list[SourceTally]]:
    """Top-15 source domains per provider."""
    return {
        prov: [
            SourceTally(domain=dom, citation_count=count)
            for dom, count in sorted(counts.items(), key=lambda x: -x[1])[:15]
        ]
        for prov, counts in state.src_by_prov_raw.items()
    }


def build_brand_global_vis(state: _AggregationState) -> dict[str, float]:
    """Mean visibility score across every processed entry for each brand."""
    denom = max(state.total_processed_entry_count, 1)
    return {
        name: round(total / denom, 2)
        for name, total in state.brand_global_vis_raw.items()
    }


def build_heatmap(state: _AggregationState) -> dict[str, dict[str, float]]:
    """Brand × provider visibility means, keyed for the heatmap component."""
    out: dict[str, dict[str, float]] = {}
    for entity, prov_scores in state.global_entity_model_scores.items():
        out[entity] = {}
        for int_key, hm_key in HM_PROV_KEY.items():
            vals = prov_scores.get(int_key, [])
            out[entity][hm_key] = round(sum(vals) / len(vals), 1) if vals else 0
    return out


def build_recent_responses(
    state: _AggregationState, limit: int = 20
) -> list[FlatResponse]:
    """Most-recent flat responses across all prompts (limited)."""
    return sorted(
        state.all_responses_flat, key=lambda r: r.date or "", reverse=True
    )[:limit]


def build_mentioned_responses(
    state: _AggregationState, limit: int = 10
) -> list[FlatResponse]:
    """Most-recent mentioned-only responses (limited)."""
    return [
        r
        for r in sorted(
            state.all_responses_flat, key=lambda r: r.date or "", reverse=True
        )
        if r.is_mentioned > 0
    ][:limit]


def build_overall_avg_position(prompt_metrics: list[PromptMetric]) -> float | None:
    """Mean of all provider-level positions across all prompts (None if empty)."""
    positions: list[float] = []
    for pm in prompt_metrics:
        for prov_d in pm.by_provider.values():
            if prov_d.position is not None:
                positions.append(prov_d.position)
    return round(sum(positions) / len(positions), 2) if positions else None


def build_se(
    responses: Iterable[FlatResponse],
    prompt_metrics: list[PromptMetric],
    main_brand_name: str,
) -> dict[str, list[SEEntry]]:
    """Sentiment-bucketed entries for the ``aim_se`` block.

    A response is included only if it mentioned the main brand. The reason
    snippet is the first sentence containing the brand name (up to 240 chars),
    or the first 180 chars of the response otherwise.
    """
    brand_low = (main_brand_name or "").lower()
    pid_topic: dict[str, str] = {}
    pid_text: dict[str, str] = {}
    for pm in prompt_metrics:
        pid_topic[pm.prompt_id] = pm.topic or "General"
        pid_text[pm.prompt_id] = pm.prompt_text or ""

    mkey = {
        "ChatGPT": "chatgpt",
        "Gemini": "gemini",
        "Perplexity": "perplexity",
        "Google AIO": "googleaio",
        "Google AI Mode": "googleaimode",
    }

    def _reason(text: str) -> str:
        if not text:
            return ""
        for s in re.split(r"(?<=[.!?])\s+|\n+", text):
            if brand_low and brand_low in s.lower():
                s = s.strip()
                return (s[:240] + "...") if len(s) > 240 else s
        return text[:180].strip()

    buckets: dict[str, list[SEEntry]] = {
        "positive": [],
        "negative": [],
        "neutral": [],
        "uncertain": [],
    }
    seen: set[str] = set()
    for r in responses:
        if not r.is_mentioned:
            continue
        pid = r.prompt_id
        mk = mkey.get(r.model, (r.model or "").lower().replace(" ", ""))
        dk = r.date
        key = f"{pid}|{mk}|{dk}"
        if key in seen:
            continue
        seen.add(key)
        label = (r.sentiment_label or "neutral").lower()
        stype = (
            "positive"
            if label == "positive"
            else "negative"
            if label == "negative"
            else "neutral"
        )
        buckets[stype].append(
            SEEntry(
                runId=key,
                prompt=r.prompt_text or pid_text.get(pid, ""),
                promptId=pid,
                model=mk,
                category=pid_topic.get(pid, "General"),
                sentiment=stype,
                reason=_reason(r.text or ""),
                date=dk,
            )
        )
    return buckets

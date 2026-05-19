"""End-to-end orchestrator for building and writing a Peekaboo snapshot.

Composes the client (I/O), the aggregator (pure data shaping), the checkpoint
manager (resume), and the injector (dashboard write) into one builder. Tests
typically exercise the aggregator directly; the builder itself is best covered
by an end-to-end smoke test against a recorded fixture.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path

from peekaboo_snapshot.aggregator import (
    aggregate,
    build_brand_global_vis,
    build_brand_timeline,
    build_brand_timeline_by_provider,
    build_competitor_entities,
    build_daily_trend,
    build_heatmap,
    build_latest_by_provider,
    build_mentioned_responses,
    build_overall_avg_position,
    build_recent_responses,
    build_se,
    build_sources_by_date,
    build_sources_by_provider,
    build_top_source_urls,
    build_top_sources,
)
from peekaboo_snapshot.checkpoint import CheckpointManager
from peekaboo_snapshot.client import PeekabooClient
from peekaboo_snapshot.config import Config
from peekaboo_snapshot.injector import SnapshotInjector
from peekaboo_snapshot.models import (
    AllBrandsEntry,
    Brand,
    Competitor,
    OutputSnapshot,
    PromptDetail,
)

logger = logging.getLogger(__name__)


def _domain_from_url(url: str | None) -> str:
    """Strip scheme/www/path from a URL, returning the bare domain."""
    if not url:
        return ""
    bare = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
    return bare.split("/")[0]


def _filter_brands(brands: list[Brand], keywords: tuple[str, ...]) -> list[Brand]:
    """Apply substring brand filter (case-insensitive OR match) and sort."""
    sorted_brands = sorted(
        brands, key=lambda b: b.lastAnalysisAt or "", reverse=True
    )
    if not keywords:
        return sorted_brands
    lowered = tuple(k.lower() for k in keywords)
    return [
        b for b in sorted_brands if any(k in (b.name or "").lower() for k in lowered)
    ]


class SnapshotBuilder:
    """Compose API + aggregator + checkpoint + injector into one pipeline."""

    def __init__(self, config: Config, client: PeekabooClient) -> None:
        self._config = config
        self._client = client
        self._checkpoint = CheckpointManager(config.checkpoint_dir)
        self._injector = SnapshotInjector()

    # ─── Build ────────────────────────────────────────────────────────────

    def build(self) -> OutputSnapshot:
        """Fetch every required payload and aggregate into an OutputSnapshot."""
        cfg = self._config
        brand_id = cfg.brand_id

        logger.info("fetching brand list")
        raw_brands = self._client.list_brands()
        filtered = _filter_brands(raw_brands, cfg.brand_filter)
        logger.info("brand list: %d total, %d after filter", len(raw_brands), len(filtered))

        all_brands = [
            AllBrandsEntry(
                id=b.id,
                name=b.name,
                domain=_domain_from_url(b.url),
                industry=b.industry,
                lastAnalysisAt=b.lastAnalysisAt or None,
                analysisFrequency=b.analysisFrequency,
            )
            for b in filtered
        ]

        logger.info("fetching snapshot for %s", brand_id)
        snap = self._client.get_snapshot(brand_id)
        overall_visibility = float(snap.visibility.score or 0.0)
        total_runs = int(snap.visibility.totalChatsAnalyzed or 0)
        snap_competitors = snap.competitors or []
        ai_suggestions = snap.aiSuggestions or []

        # Resolve the main brand name from the filtered list (falls back to id).
        main_brand_name = next(
            (b.name for b in filtered if b.id == brand_id),
            brand_id,
        )

        logger.info("fetching prompt list (time_range=%s)", cfg.time_range)
        prompts = self._client.list_prompts(
            brand_id, time_range=cfg.time_range, limit=200
        )
        logger.info("prompts: %d", len(prompts))

        ap_ids: dict[str, str] = {
            p.resolved_id(): f"ap{i + 1}" for i, p in enumerate(prompts)
        }

        cached: dict[str, PromptDetail] = (
            self._checkpoint.load(brand_id) if cfg.resume else {}
        )
        details: dict[str, PromptDetail] = {}
        for idx, p in enumerate(prompts, start=1):
            pid = p.resolved_id()
            if not pid:
                continue
            if pid in cached:
                details[pid] = cached[pid]
                logger.debug("checkpoint hit %d/%d %s", idx, len(prompts), pid[:8])
                continue
            logger.info(
                "fetching prompt %d/%d %s", idx, len(prompts), pid[:8]
            )
            detail = self._client.get_prompt_detail(
                brand_id,
                pid,
                time_range=cfg.time_range,
                include_full_response=True,
            )
            details[pid] = detail
            self._checkpoint.save(brand_id, pid, detail)

        competitors: list[Competitor] = snap_competitors
        if not competitors:
            logger.info("fetching competitor list (snapshot had none)")
            competitors = self._client.list_competitors(brand_id)
        else:
            # Cross-check against /competitors and use the longer of the two.
            try:
                extra = self._client.list_competitors(brand_id)
                if len(extra) > len(competitors):
                    competitors = extra
            except Exception as exc:  # noqa: BLE001 - we want to log but continue
                logger.warning("competitor list cross-check failed: %s", exc)

        prompt_records = [
            {"prompt_id": p.resolved_id(), "ap_id": ap_ids[p.resolved_id()]}
            for p in prompts
            if p.resolved_id()
        ]

        logger.info("aggregating snapshot data")
        state = aggregate(
            prompts=prompt_records,
            details=details,
            competitors=competitors,
            max_history_dates=cfg.max_history_dates,
            max_text_len=cfg.max_text_len,
        )

        daily_trend = build_daily_trend(state)
        latest_by_provider = build_latest_by_provider(state)
        top_sources = build_top_sources(state)
        top_source_urls = build_top_source_urls(state)
        competitor_entities = build_competitor_entities(state, competitors, total_runs)
        brand_timeline = build_brand_timeline(state, competitors)
        brand_timeline_by_provider = build_brand_timeline_by_provider(state, competitors)
        sources_by_date = build_sources_by_date(state)
        sources_by_provider = build_sources_by_provider(state)
        brand_global_vis = build_brand_global_vis(state)
        heatmap = build_heatmap(state)
        recent_responses = build_recent_responses(state)
        mentioned_responses = build_mentioned_responses(state)
        overall_avg_position = build_overall_avg_position(state.prompt_metrics)
        se = build_se(state.all_responses_flat, state.prompt_metrics, main_brand_name)

        snapshot = OutputSnapshot(
            generated_at=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            brand=main_brand_name,
            brand_id=brand_id,
            all_brands=all_brands,
            total_runs=total_runs,
            overall_visibility=round(overall_visibility, 2),
            overall_avg_position=overall_avg_position,
            daily_trend=daily_trend,
            latest_by_provider=latest_by_provider,
            top_sources=top_sources,
            competitor_entities=competitor_entities,
            prompt_metrics=state.prompt_metrics,
            prompt_responses=state.prompt_responses,
            prompt_response_history=state.prompt_response_history,
            recent_responses=recent_responses,
            mentioned_responses=mentioned_responses,
            prompt_analysis=state.prompt_analysis,
            brand_timeline=brand_timeline,
            brand_timeline_by_provider=brand_timeline_by_provider,
            sources_by_date=sources_by_date,
            sources_by_provider=sources_by_provider,
            top_source_urls=top_source_urls,
            brand_global_vis=brand_global_vis,
            ai_suggestions=ai_suggestions,
            aim_real_hm_data=heatmap,
            aim_real_matrix_data=state.prompt_matrix_data,
            aim_se=se,
        )
        logger.info(
            "snapshot built: visibility=%.2f%% runs=%d prompts=%d competitors=%d",
            snapshot.overall_visibility,
            snapshot.total_runs,
            len(snapshot.prompt_metrics),
            len(snapshot.competitor_entities),
        )
        return snapshot

    # ─── Run ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Execute the pipeline end-to-end and write all configured outputs."""
        cfg = self._config
        snapshot = self.build()

        if cfg.dry_run:
            self._print_dry_run_summary(snapshot)
            return

        if cfg.save_path:
            payload = json.dumps(
                snapshot.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            )
            cfg.save_path.parent.mkdir(parents=True, exist_ok=True)
            cfg.save_path.write_text(payload, encoding="utf-8")
            logger.info("wrote snapshot JSON to %s", cfg.save_path)

        for dashboard in cfg.dashboard_paths:
            self._injector.inject(snapshot, dashboard)

        # Clear checkpoint only after every output succeeded.
        self._checkpoint.clear(cfg.brand_id)

    # ─── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _print_dry_run_summary(snapshot: OutputSnapshot) -> None:
        """Log a one-screen summary of the built snapshot."""
        logger.info("=== Snapshot summary ===")
        logger.info("Generated:           %s", snapshot.generated_at)
        logger.info("Overall visibility:  %.2f%%", snapshot.overall_visibility)
        logger.info("Overall avg pos:     %s", snapshot.overall_avg_position)
        logger.info("Total runs:          %d", snapshot.total_runs)
        logger.info("Prompts:             %d", len(snapshot.prompt_metrics))
        logger.info("Daily trend points:  %d", len(snapshot.daily_trend))
        logger.info("Competitors:         %d", len(snapshot.competitor_entities))
        logger.info("Top sources:         %d", len(snapshot.top_sources))
        logger.info("Recent responses:    %d", len(snapshot.recent_responses))
        logger.info("Mentioned responses: %d", len(snapshot.mentioned_responses))
        logger.info("Brand timeline:      %d brands", len(snapshot.brand_timeline))
        logger.info("AI Suggestions:      %d", len(snapshot.ai_suggestions))
        if snapshot.daily_trend:
            logger.info(
                "Date range:          %s – %s",
                snapshot.daily_trend[0].iso_date,
                snapshot.daily_trend[-1].iso_date,
            )

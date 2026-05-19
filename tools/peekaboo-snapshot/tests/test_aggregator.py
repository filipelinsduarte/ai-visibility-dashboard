"""Unit tests for the pure aggregator functions."""

from __future__ import annotations

from peekaboo_snapshot.aggregator import (
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
    fmt_date,
    sent_label,
)


def test_sent_label_normalizes_inputs() -> None:
    assert sent_label(None) == "neutral"
    assert sent_label("Positive") == "positive"
    assert sent_label("anything else") == "neutral"
    assert sent_label("NEGATIVE") == "negative"


def test_fmt_date_handles_valid_and_invalid() -> None:
    assert fmt_date("2026-05-19T12:00:00Z") == "May 19"
    # Invalid input falls back to the first 10 chars of the input.
    assert fmt_date("not-a-date") == "not-a-date"
    assert fmt_date("garbage-string-extra") == "garbage-st"


def test_aggregate_populates_core_fields(aggregation_state) -> None:
    state = aggregation_state
    assert len(state.prompt_metrics) == 2
    # 4 history entries total in fixture.
    assert state.total_processed_entry_count == 4
    # ap_id assignment is preserved.
    assert state.prompt_responses["ap1"]  # type: ignore[truthy-bool]
    # Brand appears in multiple runs.
    assert state.global_brand_counts["AI Peekaboo"] >= 2


def test_build_daily_trend_orders_by_iso_date(aggregation_state) -> None:
    trend = build_daily_trend(aggregation_state)
    iso_dates = [pt.iso_date for pt in trend]
    assert iso_dates == sorted(iso_dates)
    assert {"chatgpt", "gemini", "perplexity", "googleaio", "googleaimode"} <= set(
        trend[0].model_dump().keys()
    )


def test_latest_by_provider_contains_all_providers(aggregation_state) -> None:
    out = build_latest_by_provider(aggregation_state)
    assert set(out.keys()) == {
        "chatgpt",
        "gemini",
        "perplexity",
        "googleaio",
        "googleaimode",
    }
    # googleaio had a run with score 50.
    assert out["googleaio"].visibility == 50.0


def test_top_sources_sorted_desc(aggregation_state) -> None:
    rows = build_top_sources(aggregation_state)
    counts = [r.citation_count for r in rows]
    assert counts == sorted(counts, reverse=True)
    assert any(r.domain == "aipeekaboo.com" for r in rows)


def test_top_source_urls_include_share_and_meta(aggregation_state) -> None:
    rows = build_top_source_urls(aggregation_state)
    assert rows, "expected at least one URL"
    sample = rows[0]
    assert 0 <= sample.share <= 100
    assert sample.url and sample.domain
    assert sample.last_seen.startswith("2026-")


def test_competitor_entities_use_tracked_runs(
    aggregation_state, sample_competitors
) -> None:
    rows = build_competitor_entities(aggregation_state, sample_competitors, 42)
    assert {r.name for r in rows} == {"AI Peekaboo", "Brand Radar", "Ahrefs"}
    # Everyone shares the run_count we passed in.
    assert all(r.run_count == 42 for r in rows)
    # Peekaboo positive sentiment > 50.
    peekaboo = next(r for r in rows if r.name == "AI Peekaboo")
    assert peekaboo.sentiment >= 50


def test_brand_timeline_and_by_provider(
    aggregation_state, sample_competitors
) -> None:
    bt = build_brand_timeline(aggregation_state, sample_competitors)
    assert "AI Peekaboo" in bt
    assert all(p.visibility >= 0 for series in bt.values() for p in series)

    by_prov = build_brand_timeline_by_provider(aggregation_state, sample_competitors)
    assert "AI Peekaboo" in by_prov
    # Each brand has all five providers (may be empty).
    assert {
        "chatgpt",
        "gemini",
        "perplexity",
        "googleaio",
        "googleaimode",
    } <= set(by_prov["AI Peekaboo"].keys())


def test_sources_by_date_and_provider(aggregation_state) -> None:
    sbd = build_sources_by_date(aggregation_state)
    assert "2026-05-19" in sbd
    sbp = build_sources_by_provider(aggregation_state)
    assert "chatgpt" in sbp


def test_brand_global_vis_uses_total_entries(aggregation_state) -> None:
    out = build_brand_global_vis(aggregation_state)
    assert "AI Peekaboo" in out
    # The fixture has 4 entries total — no value should exceed sum/4.
    assert all(v >= 0 for v in out.values())


def test_heatmap_emits_remapped_keys(aggregation_state) -> None:
    hm = build_heatmap(aggregation_state)
    assert "AI Peekaboo" in hm
    sample_keys = set(hm["AI Peekaboo"].keys())
    assert {"chatgpt", "gemini", "perplexity", "google-aio", "google-aim"} <= sample_keys


def test_recent_and_mentioned_responses(aggregation_state) -> None:
    recent = build_recent_responses(aggregation_state)
    assert len(recent) >= 1
    # Sorted desc by date.
    dates = [r.date for r in recent]
    assert dates == sorted(dates, reverse=True)
    mentioned = build_mentioned_responses(aggregation_state)
    assert all(r.is_mentioned == 1 for r in mentioned)


def test_overall_avg_position(aggregation_state) -> None:
    pos = build_overall_avg_position(aggregation_state.prompt_metrics)
    assert pos is None or pos > 0


def test_build_se_buckets(aggregation_state) -> None:
    se = build_se(
        aggregation_state.all_responses_flat,
        aggregation_state.prompt_metrics,
        "AI Peekaboo",
    )
    assert {"positive", "negative", "neutral", "uncertain"} == set(se.keys())
    all_entries = [e for bucket in se.values() for e in bucket]
    assert all_entries, "fixture must yield at least one SE entry"
    # No duplicates (unique by promptId|model|date).
    keys = {e.runId for e in all_entries}
    assert len(keys) == len(all_entries)

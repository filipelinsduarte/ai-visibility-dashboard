"""Tests for the atomic snapshot injector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from peekaboo_snapshot.injector import (
    INJECT_END,
    INJECT_START,
    InjectionError,
    SnapshotInjector,
)
from peekaboo_snapshot.models import OutputSnapshot


def _make_snapshot() -> OutputSnapshot:
    """Build a minimal-but-valid OutputSnapshot for injection tests."""
    return OutputSnapshot(
        generated_at="2026-05-20T00:00:00",
        brand="AI Peekaboo",
        brand_id="brand-uuid",
        all_brands=[],
        total_runs=0,
        overall_visibility=0.0,
        overall_avg_position=None,
        daily_trend=[],
        latest_by_provider={},
        top_sources=[],
        competitor_entities=[],
        prompt_metrics=[],
        prompt_responses={},
        prompt_response_history={},
        recent_responses=[],
        mentioned_responses=[],
        prompt_analysis={},
        brand_timeline={},
        brand_timeline_by_provider={},
        sources_by_date={},
        sources_by_provider={},
        top_source_urls=[],
        brand_global_vis={},
        ai_suggestions=[],
        aim_real_hm_data={},
        aim_real_matrix_data={},
        aim_se={"positive": [], "negative": [], "neutral": [], "uncertain": []},
    )


def _html(initial_payload: str = "PLACEHOLDER") -> str:
    return (
        "<html><head><title>t</title></head><body>\n"
        "<!-- before -->\n"
        f"{INJECT_START}{initial_payload}{INJECT_END}\n"
        "<!-- after -->\n"
        "</body></html>\n"
    )


def test_inject_replaces_block(tmp_path: Path) -> None:
    dash = tmp_path / "dashboard.html"
    dash.write_text(_html(), encoding="utf-8")
    SnapshotInjector().inject(_make_snapshot(), dash)

    result = dash.read_text(encoding="utf-8")
    assert INJECT_START in result
    assert INJECT_END in result
    assert "<script>window._AIM_SNAPSHOT=" in result
    # Markers appear exactly once each.
    assert result.count(INJECT_START) == 1
    assert result.count(INJECT_END) == 1


def test_injected_payload_is_valid_json(tmp_path: Path) -> None:
    dash = tmp_path / "dashboard.html"
    dash.write_text(_html(), encoding="utf-8")
    SnapshotInjector().inject(_make_snapshot(), dash)

    text = dash.read_text(encoding="utf-8")
    start_token = "<script>window._AIM_SNAPSHOT="
    start = text.find(start_token) + len(start_token)
    end = text.find(";</script>", start)
    payload = text[start:end]
    parsed = json.loads(payload)
    assert parsed["brand"] == "AI Peekaboo"
    assert parsed["brand_id"] == "brand-uuid"


def test_verify_markers_reports_presence(tmp_path: Path) -> None:
    dash = tmp_path / "dashboard.html"
    dash.write_text(_html(), encoding="utf-8")
    inj = SnapshotInjector()
    assert inj.verify_markers(dash) == (True, True)

    only_start = tmp_path / "half.html"
    only_start.write_text(f"<html>{INJECT_START}x</html>", encoding="utf-8")
    assert inj.verify_markers(only_start) == (True, False)


def test_inject_raises_when_markers_missing(tmp_path: Path) -> None:
    dash = tmp_path / "dashboard.html"
    dash.write_text("<html>no markers here</html>", encoding="utf-8")
    with pytest.raises(InjectionError):
        SnapshotInjector().inject(_make_snapshot(), dash)


def test_inject_raises_when_file_missing(tmp_path: Path) -> None:
    dash = tmp_path / "does-not-exist.html"
    with pytest.raises(FileNotFoundError):
        SnapshotInjector().inject(_make_snapshot(), dash)


def test_inject_is_atomic_no_temp_left(tmp_path: Path) -> None:
    """After a successful inject, no .tmp scratch file remains."""
    dash = tmp_path / "dashboard.html"
    dash.write_text(_html(), encoding="utf-8")
    SnapshotInjector().inject(_make_snapshot(), dash)
    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []

"""Tests for the CheckpointManager save/load/clear roundtrip."""

from __future__ import annotations

from pathlib import Path

from peekaboo_snapshot.checkpoint import CheckpointManager
from peekaboo_snapshot.models import PromptDetail, PromptHistoryEntry


def _make_detail(pid: str) -> PromptDetail:
    return PromptDetail(
        promptId=pid,
        promptText=f"text for {pid}",
        category="Commercial",
        searchIntent="COMMERCIAL",
        history=[
            PromptHistoryEntry(
                aiModel="gpt-4o-mini",
                date="2026-05-19",
                score=67.0,
                rank=2,
                mentioned=True,
                runId="r1",
            )
        ],
    )


def test_load_returns_empty_when_no_file(tmp_path: Path) -> None:
    mgr = CheckpointManager(tmp_path)
    assert mgr.load("brand-x") == {}


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    mgr = CheckpointManager(tmp_path)
    mgr.save("brand-x", "p1", _make_detail("p1"))
    mgr.save("brand-x", "p2", _make_detail("p2"))
    loaded = mgr.load("brand-x")
    assert set(loaded.keys()) == {"p1", "p2"}
    assert loaded["p1"].promptId == "p1"
    assert loaded["p1"].history[0].aiModel == "gpt-4o-mini"


def test_clear_removes_checkpoint(tmp_path: Path) -> None:
    mgr = CheckpointManager(tmp_path)
    mgr.save("brand-x", "p1", _make_detail("p1"))
    assert any(tmp_path.iterdir())
    mgr.clear("brand-x")
    # File for this brand is gone.
    assert mgr.load("brand-x") == {}


def test_clear_is_noop_when_missing(tmp_path: Path) -> None:
    mgr = CheckpointManager(tmp_path)
    mgr.clear("brand-never-existed")  # must not raise


def test_load_ignores_corrupt_file(tmp_path: Path) -> None:
    mgr = CheckpointManager(tmp_path)
    # Simulate a corrupted checkpoint.
    target = tmp_path / "checkpoint_brand-x.json"
    target.write_text("not json {", encoding="utf-8")
    assert mgr.load("brand-x") == {}


def test_brand_id_is_sanitized_in_filename(tmp_path: Path) -> None:
    mgr = CheckpointManager(tmp_path)
    mgr.save("weird/brand id!", "p1", _make_detail("p1"))
    files = list(tmp_path.glob("checkpoint_*.json"))
    assert len(files) == 1
    # No raw slashes or spaces in the filename.
    assert "/" not in files[0].name
    assert " " not in files[0].name

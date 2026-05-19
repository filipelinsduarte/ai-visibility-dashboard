"""Shared fixtures for the peekaboo-snapshot test suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from peekaboo_snapshot.aggregator import aggregate
from peekaboo_snapshot.models import Competitor, PromptDetail

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixture_payload() -> dict:
    """Load and return the canonical sample snapshot fixture."""
    return json.loads((FIXTURES_DIR / "sample_snapshot.json").read_text("utf-8"))


@pytest.fixture
def sample_competitors(fixture_payload: dict) -> list[Competitor]:
    """Pydantic-parsed competitor list."""
    return [Competitor.model_validate(c) for c in fixture_payload["competitors"]]


@pytest.fixture
def sample_prompt_details(fixture_payload: dict) -> dict[str, PromptDetail]:
    """Pydantic-parsed prompt detail map keyed by prompt id."""
    return {
        p["promptId"]: PromptDetail.model_validate(p)
        for p in fixture_payload["prompts"]
    }


@pytest.fixture
def sample_prompt_records(fixture_payload: dict) -> list[dict[str, str]]:
    """Lightweight ``{prompt_id, ap_id}`` records as fed into ``aggregate``."""
    return [
        {"prompt_id": p["promptId"], "ap_id": f"ap{i + 1}"}
        for i, p in enumerate(fixture_payload["prompts"])
    ]


@pytest.fixture
def aggregation_state(
    sample_prompt_records,
    sample_prompt_details,
    sample_competitors,
):
    """A fully-populated _AggregationState built from the fixture."""
    return aggregate(
        prompts=sample_prompt_records,
        details=sample_prompt_details,
        competitors=sample_competitors,
        max_history_dates=20,
        max_text_len=4000,
    )

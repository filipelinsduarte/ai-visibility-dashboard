"""Pydantic v2 models for AI Peekaboo API payloads and internal snapshot shapes.

Models intentionally accept extra fields (``extra='allow'``) so the upstream
API can add fields without breaking the pipeline. Field names mirror the API
exactly (e.g. ``aiModel`` not ``model``); aliases are configured via
``populate_by_name`` so snake_case input also works.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _APIBase(BaseModel):
    """Common base for inbound API models."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")


# ─── Brand ──────────────────────────────────────────────────────────────────


class Brand(_APIBase):
    """Brand summary as returned by ``GET /brands``."""

    id: str
    name: str
    url: str | None = None
    industry: str | None = None
    lastAnalysisAt: str | None = None
    analysisFrequency: str | None = None


class BrandDetail(_APIBase):
    """Detail payload returned by ``GET /brands/:id``.

    Adds the fields enriched per-brand: ``location``, ``promptCount``, and
    ``analysisEnabled`` (defaults to True if absent).
    """

    id: str | None = None
    name: str | None = None
    url: str | None = None
    industry: str | None = None
    location: str | None = None
    promptCount: int | None = None
    analysisEnabled: bool = True
    lastAnalysisAt: str | None = None


# ─── Snapshot / Visibility ──────────────────────────────────────────────────


class VisibilityBlock(_APIBase):
    """``visibility`` sub-block of the snapshot response."""

    score: float = 0.0
    totalChatsAnalyzed: int = 0


class AISuggestion(_APIBase):
    """One entry in the snapshot's ``aiSuggestions`` array."""

    title: str | None = None
    description: str | None = None
    type: str | None = None


class SnapshotResponse(_APIBase):
    """Top-level response from ``GET /brands/:id/snapshot``."""

    visibility: VisibilityBlock = Field(default_factory=VisibilityBlock)
    competitors: list[Competitor] = Field(default_factory=list)
    aiSuggestions: list[AISuggestion] = Field(default_factory=list)


# ─── Prompts ────────────────────────────────────────────────────────────────


class Prompt(_APIBase):
    """Prompt summary entry (item in the ``prompts`` list)."""

    promptId: str | None = None
    id: str | None = None
    promptText: str | None = None
    category: str | None = None
    searchIntent: str | None = None

    def resolved_id(self) -> str:
        """Return the canonical id (``promptId`` preferred over legacy ``id``)."""
        return self.promptId or self.id or ""


class BrandMention(_APIBase):
    """One brand/competitor mention inside a single history entry."""

    entityName: str = ""
    type: str | None = None
    score: float = 0.0
    rank: int | None = None
    sentiment: str | None = None
    sentimentScore: float | None = None


class Source(_APIBase):
    """One cited source inside a single history entry."""

    domain: str = ""
    url: str = ""
    title: str | None = None


class PromptHistoryEntry(_APIBase):
    """One run inside ``/prompts/:id`` history.

    ``aiModel`` is the canonical field name; legacy ``model`` is supported via
    extra-allow and consumers should fall back when ``aiModel`` is empty.
    """

    aiModel: str | None = None
    model: str | None = None
    date: str | None = None
    score: float = 0.0
    rank: int | None = None
    mentioned: bool = False
    runId: str | None = None
    sentiment: str | None = None
    fullResponse: str | None = None
    responseSnippet: str | None = None
    sources: list[Source] = Field(default_factory=list)
    brandMentions: list[BrandMention] = Field(default_factory=list)

    def model_name(self) -> str:
        """Return the canonical model identifier, falling back to ``model``."""
        return (self.aiModel or self.model or "").strip()


class PromptDetail(_APIBase):
    """Response from ``GET /brands/:id/prompts/:promptId``."""

    promptId: str | None = None
    id: str | None = None
    promptText: str | None = None
    category: str | None = None
    searchIntent: str | None = None
    history: list[PromptHistoryEntry] = Field(default_factory=list)


# ─── Competitors ────────────────────────────────────────────────────────────


class Competitor(_APIBase):
    """Competitor as returned by ``/snapshot.competitors`` or ``/competitors``."""

    name: str = ""
    url: str | None = None
    score: float = 0.0
    rank: int | None = None


# Resolve forward reference for SnapshotResponse.competitors.
SnapshotResponse.model_rebuild()


# ─── Output snapshot shapes ────────────────────────────────────────────────
# These are the *internal* shapes produced by the aggregator and written into
# the dashboard HTML as ``window._AIM_SNAPSHOT``.


class _OutputBase(BaseModel):
    """Common base for outbound dashboard models."""

    model_config = ConfigDict(extra="allow")


class AllBrandsEntry(_OutputBase):
    """One row in the ``all_brands`` dropdown."""

    id: str
    name: str
    domain: str = ""
    industry: str | None = None
    lastAnalysisAt: str | None = None
    analysisFrequency: str | None = None
    location: str | None = None
    promptCount: int | None = None
    analysisEnabled: bool = True


class DailyTrendPoint(_OutputBase):
    """One row in the ``daily_trend`` series."""

    date: str
    iso_date: str
    visibility: float
    chatgpt: float = 0
    gemini: float = 0
    perplexity: float = 0
    googleaio: float = 0
    googleaimode: float = 0


class ProviderSnapshot(_OutputBase):
    """``latest_by_provider`` entry for one model."""

    visibility: float = 0
    sentiment: float = 50
    sentiment_label: str = "neutral"
    position: float | None = None


class TopSource(_OutputBase):
    """One row in ``top_sources``."""

    domain: str
    citation_count: int
    run_count: int


class CompetitorEntity(_OutputBase):
    """One row in ``competitor_entities``."""

    name: str
    visibility: float
    rank: int | None = None
    sentiment: int = 50
    avg_position: float | None = None
    mention_count: int = 0
    run_count: int = 0


class PromptMetricByProvider(_OutputBase):
    """Inner per-provider metrics inside ``prompt_metrics[i].by_provider``."""

    visibility: float = 0.0
    sentiment: float = 50.0
    position: float | None = None


class PromptMetric(_OutputBase):
    """One row in ``prompt_metrics``."""

    prompt_id: str
    prompt_text: str
    topic: str
    intent: str
    visibility_all: float
    sentiment_all: float
    position_all: float | None
    by_provider: dict[str, PromptMetricByProvider]
    last_run: str


class FlatResponse(_OutputBase):
    """A flattened single (prompt × provider × date) response object."""

    model: str
    date: str
    text: str
    brands: list[str]
    sources: list[str]
    source_objects: list[dict[str, Any]]
    sentiment_label: str
    sentiment_score: float
    visibility_score: float
    position: float | None
    is_mentioned: int
    prompt_id: str
    prompt_text: str


class PromptAnalysisEntry(_OutputBase):
    """One row in ``prompt_analysis``."""

    top_brand: str
    top_citation: str
    brands: list[str]
    citations: list[str]


class TimelinePoint(_OutputBase):
    """One ``{date, visibility}`` point in a brand timeline series."""

    date: str
    visibility: float


class SourceTally(_OutputBase):
    """One ``{domain, citation_count}`` row in sources-by-date / by-provider."""

    domain: str
    citation_count: int


class TopSourceUrl(_OutputBase):
    """One row in ``top_source_urls``."""

    url: str
    domain: str
    label: str
    citation_count: int
    run_count: int
    last_seen: str
    share: float
    by_provider: dict[str, int] = Field(default_factory=dict)


class BrandPosition(_OutputBase):
    """One brand-rank cell inside ``aim_real_matrix_data``."""

    n: str
    count: int
    d: str = ""


class SEEntry(_OutputBase):
    """One row inside ``aim_se[bucket]``."""

    runId: str
    prompt: str
    promptId: str
    model: str
    category: str
    sentiment: str
    reason: str
    date: str


class OutputSnapshot(_OutputBase):
    """The complete JSON blob written as ``window._AIM_SNAPSHOT``.

    All fields mirror the legacy generator one-for-one so the dashboard JS
    can consume the new output unchanged.
    """

    generated_at: str
    brand: str
    brand_id: str
    all_brands: list[AllBrandsEntry]
    total_runs: int
    overall_visibility: float
    overall_avg_position: float | None
    daily_trend: list[DailyTrendPoint]
    latest_by_provider: dict[str, ProviderSnapshot]
    top_sources: list[TopSource]
    competitor_entities: list[CompetitorEntity]
    prompt_metrics: list[PromptMetric]
    prompt_responses: dict[str, dict[str, FlatResponse]]
    prompt_response_history: dict[str, dict[str, dict[str, FlatResponse]]]
    recent_responses: list[FlatResponse]
    mentioned_responses: list[FlatResponse]
    prompt_analysis: dict[str, PromptAnalysisEntry]
    brand_timeline: dict[str, list[TimelinePoint]]
    brand_timeline_by_provider: dict[str, dict[str, list[TimelinePoint]]]
    sources_by_date: dict[str, list[SourceTally]]
    sources_by_provider: dict[str, list[SourceTally]]
    top_source_urls: list[TopSourceUrl]
    brand_global_vis: dict[str, float]
    ai_suggestions: list[AISuggestion]
    aim_real_hm_data: dict[str, dict[str, float]]
    aim_real_matrix_data: dict[str, list[BrandPosition]]
    aim_se: dict[str, list[SEEntry]]

"""HTTP client for the AI Peekaboo REST API.

The client wraps a single ``requests.Session`` with sensible retry semantics,
a token-bucket rate limiter sized to fit under the per-minute API allowance,
and explicit handling for the ``X-RateLimit-*`` headers. Each public method
returns a Pydantic-typed payload so callers never touch raw dicts.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

import requests
from pydantic import TypeAdapter, ValidationError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from peekaboo_snapshot.config import Config
from peekaboo_snapshot.models import (
    Brand,
    BrandDetail,
    Competitor,
    Prompt,
    PromptDetail,
    SnapshotResponse,
)

logger = logging.getLogger(__name__)


# ─── Exceptions ─────────────────────────────────────────────────────────────


class PeekabooAPIError(RuntimeError):
    """Base exception for any Peekaboo API failure."""


class RateLimited(PeekabooAPIError):
    """Raised when the API responds 429 and retries are exhausted."""


class DailyLimitExhausted(PeekabooAPIError):
    """Raised when ``X-RateLimit-Daily-Remaining`` reaches zero."""


class NotFound(PeekabooAPIError):
    """Raised on HTTP 404."""


class Unauthorized(PeekabooAPIError):
    """Raised on HTTP 401 or 403."""


# ─── Type adapters (cached) ─────────────────────────────────────────────────

_BRAND_LIST = TypeAdapter(list[Brand])
_PROMPT_LIST = TypeAdapter(list[Prompt])
_COMPETITOR_LIST = TypeAdapter(list[Competitor])


# ─── Token-bucket rate limiter ──────────────────────────────────────────────


class _RateLimiter:
    """Simple sliding-window rate limiter.

    Keeps a deque of timestamps from the last 60 seconds. If the deque has
    reached the configured size when ``acquire()`` is called, the call blocks
    until the oldest entry ages out.
    """

    def __init__(self, max_per_minute: int) -> None:
        self._max = max(1, int(max_per_minute))
        self._calls: deque[float] = deque()

    def acquire(self) -> None:
        """Block until a request slot is available, then record one."""
        now = time.time()
        while self._calls and now - self._calls[0] >= 60.0:
            self._calls.popleft()
        if len(self._calls) >= self._max:
            wait = 61.0 - (now - self._calls[0])
            if wait > 0:
                logger.info("rate limiter pausing %.1fs", wait)
                time.sleep(wait)
                now = time.time()
                while self._calls and now - self._calls[0] >= 60.0:
                    self._calls.popleft()
        self._calls.append(time.time())


# ─── Client ─────────────────────────────────────────────────────────────────


class PeekabooClient:
    """Typed HTTP client for the AI Peekaboo REST API.

    Construct one per pipeline run and reuse for all GET calls. The client is
    thread-safe only insofar as :py:class:`requests.Session` is; the rate
    limiter is process-local and not safe for concurrent use across threads.
    """

    def __init__(self, config: Config, session: requests.Session | None = None) -> None:
        self._config = config
        self._session = session or self._build_session()
        self._limiter = _RateLimiter(config.rate_limit_per_min)

    # ─── Session bootstrap ────────────────────────────────────────────────

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    # ─── Core GET ─────────────────────────────────────────────────────────

    def _get(self, path: str, **params: Any) -> Any:
        """Issue a GET with rate limiting and 429/4xx handling.

        Returns the parsed JSON body unwrapped from the standard
        ``{success, data, ...}`` envelope.
        """
        url = f"{self._config.base_url}/{path.lstrip('/')}"
        clean_params = {k: v for k, v in params.items() if v is not None}

        max_attempts = 3
        for attempt in range(max_attempts):
            self._limiter.acquire()
            logger.debug("GET %s params=%s (attempt %d)", url, clean_params, attempt + 1)
            response = self._session.get(
                url,
                params=clean_params or None,
                headers={
                    "X-API-Key": self._config.api_key,
                    "Accept": "application/json",
                },
                timeout=30,
            )

            if response.status_code == 200:
                return self._handle_success(response)

            if response.status_code in (401, 403):
                raise Unauthorized(
                    f"{response.status_code} for {url}: "
                    f"check PEEKABOO_API_KEY scope and plan tier."
                )

            if response.status_code == 404:
                raise NotFound(f"404 Not Found: {url}")

            if response.status_code == 429:
                daily_remaining = response.headers.get("X-RateLimit-Daily-Remaining")
                if daily_remaining is not None and daily_remaining.strip() == "0":
                    raise DailyLimitExhausted(
                        "Daily API rate limit exhausted. Resets at midnight UTC. "
                        "Try again tomorrow or upgrade plan."
                    )
                if attempt < max_attempts - 1:
                    reset_ts = self._reset_seconds(response)
                    wait = max(2.0, reset_ts) + 1.0
                    logger.warning("429 received, sleeping %.1fs before retry", wait)
                    time.sleep(wait)
                    continue
                raise RateLimited(
                    f"Rate limit exhausted after {max_attempts} retries for {url}"
                )

            # Other 4xx/5xx: retry with backoff, then surface.
            if attempt < max_attempts - 1:
                wait = 2.0**attempt
                logger.warning(
                    "HTTP %d for %s — retrying in %.1fs",
                    response.status_code,
                    url,
                    wait,
                )
                time.sleep(wait)
                continue

            raise PeekabooAPIError(
                f"HTTP {response.status_code} for {url}: {response.text[:200]}"
            )

        # Loop should always either return or raise.
        raise PeekabooAPIError(f"Exhausted retries without resolution for {url}")

    @staticmethod
    def _handle_success(response: requests.Response) -> Any:
        """Parse the JSON body and warn when nearing the rate limit."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            try:
                if int(remaining) < 3:
                    reset = PeekabooClient._reset_seconds(response)
                    wait = max(1.0, reset) + 0.5
                    logger.info(
                        "low rate-limit headroom (%s left); sleeping %.1fs",
                        remaining,
                        wait,
                    )
                    time.sleep(wait)
            except ValueError:
                pass
        return response.json()

    @staticmethod
    def _reset_seconds(response: requests.Response) -> float:
        """Return seconds until ``X-RateLimit-Reset``, never negative."""
        raw = response.headers.get("X-RateLimit-Reset")
        if not raw:
            return 60.0
        try:
            reset_ts = float(raw)
        except ValueError:
            return 60.0
        return max(0.0, reset_ts - time.time())

    # ─── List shape unwrap ────────────────────────────────────────────────

    @staticmethod
    def _unwrap(body: Any, *list_keys: str) -> list[Any]:
        """Normalize list endpoints into a plain list.

        The API has three observed shapes for list endpoints: a bare array,
        ``{"data": [...]}``, and ``{"<key>": [...]}``. This helper accepts
        any of them and returns the underlying list (or an empty list).
        """
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            payload = body.get("data", body)
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                for key in list_keys:
                    inner = payload.get(key)
                    if isinstance(inner, list):
                        return inner
                # Sometimes ``data`` wraps a dict that itself wraps the list.
                for key in list_keys:
                    inner = body.get(key)
                    if isinstance(inner, list):
                        return inner
        return []

    @staticmethod
    def _unwrap_obj(body: Any) -> dict[str, Any]:
        """Normalize single-object responses to a plain dict.

        Handles both bare-object and ``{"data": {...}}`` shapes.
        """
        if isinstance(body, dict):
            payload = body.get("data") if "data" in body and isinstance(body.get("data"), dict) else body
            if isinstance(payload, dict):
                return payload
        return {}

    # ─── Endpoints ────────────────────────────────────────────────────────

    def list_brands(self) -> list[Brand]:
        """Return all brands visible to the API key."""
        body = self._get("brands")
        raw = self._unwrap(body, "brands")
        try:
            return _BRAND_LIST.validate_python(raw)
        except ValidationError as exc:
            logger.error("brand list validation failed: %s", exc)
            raise PeekabooAPIError("Invalid /brands payload") from exc

    def get_brand_detail(self, brand_id: str) -> BrandDetail:
        """Fetch enriched detail for one brand.

        Expensive. Do **not** call inside a tight loop over every brand: the
        new pipeline only calls it for the main brand when extra fields are
        actually needed downstream.
        """
        body = self._get(f"brands/{brand_id}")
        raw = self._unwrap_obj(body)
        try:
            return BrandDetail.model_validate(raw)
        except ValidationError as exc:
            logger.error("brand detail validation failed: %s", exc)
            raise PeekabooAPIError(f"Invalid /brands/{brand_id} payload") from exc

    def get_snapshot(self, brand_id: str) -> SnapshotResponse:
        """Fetch the pre-computed snapshot for one brand."""
        body = self._get(f"brands/{brand_id}/snapshot")
        raw = self._unwrap_obj(body)
        try:
            return SnapshotResponse.model_validate(raw)
        except ValidationError as exc:
            logger.error("snapshot validation failed: %s", exc)
            raise PeekabooAPIError(f"Invalid /snapshot payload for {brand_id}") from exc

    def list_prompts(
        self,
        brand_id: str,
        time_range: str = "30d",
        limit: int = 200,
    ) -> list[Prompt]:
        """List all prompts for the given brand."""
        body = self._get(
            f"brands/{brand_id}/prompts",
            time_range=time_range,
            limit=limit,
        )
        raw = self._unwrap(body, "prompts")
        try:
            return _PROMPT_LIST.validate_python(raw)
        except ValidationError as exc:
            logger.error("prompt list validation failed: %s", exc)
            raise PeekabooAPIError(f"Invalid /prompts payload for {brand_id}") from exc

    def get_prompt_detail(
        self,
        brand_id: str,
        prompt_id: str,
        time_range: str = "30d",
        include_full_response: bool = True,
    ) -> PromptDetail:
        """Fetch the per-run history for one prompt."""
        body = self._get(
            f"brands/{brand_id}/prompts/{prompt_id}",
            time_range=time_range,
            include_full_response="true" if include_full_response else "false",
        )
        raw = self._unwrap_obj(body)
        try:
            return PromptDetail.model_validate(raw)
        except ValidationError as exc:
            logger.error("prompt detail validation failed: %s", exc)
            raise PeekabooAPIError(
                f"Invalid /prompts/{prompt_id} payload for {brand_id}"
            ) from exc

    def list_competitors(self, brand_id: str) -> list[Competitor]:
        """List tracked competitors for the given brand."""
        body = self._get(f"brands/{brand_id}/competitors")
        raw = self._unwrap(body, "competitors")
        try:
            return _COMPETITOR_LIST.validate_python(raw)
        except ValidationError as exc:
            logger.error("competitor list validation failed: %s", exc)
            raise PeekabooAPIError(
                f"Invalid /competitors payload for {brand_id}"
            ) from exc

"""Configuration dataclass for the peekaboo-snapshot generator.

A single immutable ``Config`` instance carries every knob needed by the client,
the orchestrator, and the injector. Values come from environment variables and
CLI arguments via :py:meth:`Config.from_env_and_args`.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

TimeRange = Literal["7d", "30d", "90d"]


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration for the snapshot pipeline.

    Use :py:meth:`from_env_and_args` to build a Config from a parsed
    ``argparse.Namespace`` plus environment variables.
    """

    api_key: str
    brand_id: str
    base_url: str = "https://www.aipeekaboo.com/api/v1"
    time_range: TimeRange = "30d"
    max_history_dates: int = 20
    max_text_len: int = 4000
    rate_limit_per_min: int = 18
    brand_filter: tuple[str, ...] = ()
    dashboard_paths: tuple[Path, ...] = ()
    checkpoint_dir: Path = field(default_factory=lambda: Path(".peekaboo"))
    dry_run: bool = False
    save_path: Path | None = None
    resume: bool = True

    @classmethod
    def from_env_and_args(cls, args: argparse.Namespace) -> Config:
        """Build a Config from parsed CLI args plus ``PEEKABOO_*`` env vars.

        Raises :py:class:`ConfigError` if ``PEEKABOO_API_KEY`` is unset or the
        brand id is missing on both the CLI and environment.
        """
        api_key = os.environ.get("PEEKABOO_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                "PEEKABOO_API_KEY environment variable is required.\n"
                "Set it in your shell, e.g.:\n"
                "  export PEEKABOO_API_KEY='pk_...'\n"
                "or place it in a .env file (see .env.example)."
            )

        brand_id = (
            getattr(args, "brand_id", None)
            or os.environ.get("PEEKABOO_BRAND_ID", "").strip()
        )
        if not brand_id:
            raise ConfigError(
                "Brand id is required. Pass --brand-id <uuid> "
                "or set PEEKABOO_BRAND_ID in the environment."
            )

        dashboards = tuple(Path(p).expanduser() for p in (args.dashboard or ()))
        brand_filter = tuple(s.strip() for s in (args.brand_filter or ()) if s.strip())

        return cls(
            api_key=api_key,
            brand_id=brand_id,
            time_range=args.time_range,
            max_text_len=args.max_text_len,
            brand_filter=brand_filter,
            dashboard_paths=dashboards,
            dry_run=bool(args.dry_run),
            save_path=Path(args.save).expanduser() if args.save else None,
            resume=not bool(args.no_resume),
        )

"""Command-line entry point for ``peekaboo-snapshot``.

Wires environment variables, ``argparse`` flags, the client, and the orchestrator
together. Friendly error messages are emitted for the common configuration and
API failure modes.
"""

from __future__ import annotations

import argparse
import logging
import sys

from peekaboo_snapshot.client import (
    DailyLimitExhausted,
    NotFound,
    PeekabooAPIError,
    PeekabooClient,
    RateLimited,
    Unauthorized,
)
from peekaboo_snapshot.config import Config, ConfigError
from peekaboo_snapshot.logging_config import setup_logging
from peekaboo_snapshot.snapshot import SnapshotBuilder

logger = logging.getLogger(__name__)


def _try_load_dotenv() -> None:
    """Load a local ``.env`` file if python-dotenv is installed (optional)."""
    try:
        from dotenv import load_dotenv  # type: ignore[import-not-found]
    except ImportError:
        return
    load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the CLI."""
    p = argparse.ArgumentParser(
        prog="peekaboo-snapshot",
        description=(
            "Fetch AI Peekaboo data and inject it into one or more dashboard HTML files."
        ),
    )
    p.add_argument(
        "--time-range",
        choices=("7d", "30d", "90d"),
        default="30d",
        help="History window to request from the API (default: 30d).",
    )
    p.add_argument(
        "--brand-id",
        dest="brand_id",
        default=None,
        help="Brand UUID. Overrides PEEKABOO_BRAND_ID env var.",
    )
    p.add_argument(
        "--brand-filter",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Substring filter applied to brand names (case-insensitive). "
            "Repeat to OR-match multiple substrings."
        ),
    )
    p.add_argument(
        "--dashboard",
        action="append",
        default=[],
        metavar="PATH",
        help="Dashboard HTML file to inject into. Repeat for multiple files.",
    )
    p.add_argument(
        "--max-text-len",
        type=int,
        default=4000,
        help="Truncate full response text to N chars (default: 4000).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip all writes; print a summary of the built snapshot.",
    )
    p.add_argument(
        "--save",
        default=None,
        metavar="PATH",
        help="Also write the snapshot JSON to PATH (pretty-printed).",
    )
    p.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore any existing checkpoint and refetch every prompt detail.",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code."""
    _try_load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    try:
        config = Config.from_env_and_args(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    client = PeekabooClient(config)
    builder = SnapshotBuilder(config, client)

    try:
        builder.run()
    except Unauthorized as exc:
        logger.error("unauthorized: %s", exc)
        print(
            "error: PEEKABOO_API_KEY rejected by the API. "
            "Check the key is valid and your plan includes API access.",
            file=sys.stderr,
        )
        return 2
    except DailyLimitExhausted as exc:
        logger.error("%s", exc)
        print(
            "error: daily API quota exhausted. Resets at midnight UTC.",
            file=sys.stderr,
        )
        return 3
    except RateLimited as exc:
        logger.error("rate limited: %s", exc)
        print("error: rate limited after retries; try again later.", file=sys.stderr)
        return 4
    except NotFound as exc:
        logger.error("not found: %s", exc)
        print(f"error: resource not found ({exc}).", file=sys.stderr)
        return 5
    except PeekabooAPIError as exc:
        logger.error("api error: %s", exc)
        print(f"error: API failure: {exc}", file=sys.stderr)
        return 6
    return 0


if __name__ == "__main__":  # pragma: no cover - manual smoke run
    raise SystemExit(main())

"""Logging setup for the peekaboo-snapshot package.

Every module obtains its logger via ``logging.getLogger(__name__)``. Calling
``setup_logging`` once from the CLI configures the root logger format and
level for the whole process.
"""

from __future__ import annotations

import logging

_LOG_FORMAT = "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s"


def setup_logging(verbose: bool) -> None:
    """Configure root logging for the CLI.

    Parameters
    ----------
    verbose:
        When True the root logger is set to DEBUG, otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S")
    # Silence noisy third-party libs at INFO.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

"""Peekaboo snapshot — production-grade data generator for the AI visibility dashboard.

Fetches data from the AI Peekaboo REST API, aggregates it into a single JSON
snapshot, and injects that snapshot into one or more dashboard HTML files
between sentinel markers.
"""

from peekaboo_snapshot.config import Config
from peekaboo_snapshot.snapshot import SnapshotBuilder

__all__ = ["Config", "SnapshotBuilder"]
__version__ = "0.1.0"

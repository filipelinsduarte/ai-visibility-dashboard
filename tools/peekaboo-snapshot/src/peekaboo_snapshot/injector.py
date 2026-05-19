"""Atomic snapshot injection into dashboard HTML files.

The dashboard reserves a sentinel block:

.. code-block:: html

   <!-- AIM_SNAPSHOT_INJECT_START -->...<!-- AIM_SNAPSHOT_INJECT_END -->

This module replaces everything between (and including) those markers with a
``<script>window._AIM_SNAPSHOT=...</script>`` block carrying a compact JSON
payload. Writes are performed atomically via a temp file + ``os.replace``.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from peekaboo_snapshot.models import OutputSnapshot

logger = logging.getLogger(__name__)


INJECT_START: str = "<!-- AIM_SNAPSHOT_INJECT_START -->"
INJECT_END: str = "<!-- AIM_SNAPSHOT_INJECT_END -->"


class InjectionError(RuntimeError):
    """Raised when the target HTML is missing one or both injection markers."""


class SnapshotInjector:
    """Atomic injector for ``window._AIM_SNAPSHOT`` payloads.

    Construct one instance per pipeline (no state is required) and call
    :py:meth:`inject` for each dashboard file in ``Config.dashboard_paths``.
    """

    def verify_markers(self, path: Path) -> tuple[bool, bool]:
        """Return ``(start_present, end_present)`` flags for ``path``."""
        text = path.read_text(encoding="utf-8")
        return (INJECT_START in text, INJECT_END in text)

    def inject(self, snapshot: OutputSnapshot, path: Path) -> None:
        """Atomically replace the snapshot block in ``path`` with new data.

        Raises :py:class:`InjectionError` if either marker is missing, or
        :py:class:`FileNotFoundError` if the file does not exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"Dashboard not found: {path}")

        html = path.read_text(encoding="utf-8")
        start_pos = html.find(INJECT_START)
        end_pos = html.find(INJECT_END)
        if start_pos == -1 or end_pos == -1:
            raise InjectionError(
                f"Injection markers missing in {path} "
                f"(start={start_pos != -1}, end={end_pos != -1})"
            )
        if end_pos < start_pos:
            raise InjectionError(
                f"Injection markers out of order in {path}: "
                f"end appears before start."
            )

        json_str = json.dumps(
            snapshot.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        new_block = f"{INJECT_START}<script>window._AIM_SNAPSHOT={json_str};</script>{INJECT_END}"
        new_html = html[:start_pos] + new_block + html[end_pos + len(INJECT_END):]

        self._atomic_write(path, new_html)
        logger.info(
            "injected snapshot into %s (%d bytes payload)", path, len(json_str)
        )

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """Write ``content`` to ``path`` via temp file + os.replace."""
        directory = path.parent
        directory.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=path.name + ".",
            suffix=".tmp",
            dir=str(directory),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(content)
            os.replace(tmp_name, path)
        except Exception:
            # Best-effort cleanup of the temp file if replace failed.
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

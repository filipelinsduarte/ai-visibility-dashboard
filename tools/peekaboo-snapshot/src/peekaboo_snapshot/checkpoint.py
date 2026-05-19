"""Resumable checkpoint for partially-completed snapshot runs.

The full snapshot involves one ``/prompts/:id`` call per prompt; on a 200-prompt
brand that can be ~10 minutes of API time. If the run is interrupted the
checkpoint lets the next invocation skip every prompt whose detail has already
been fetched. A successful injection clears the file.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from peekaboo_snapshot.models import PromptDetail

logger = logging.getLogger(__name__)


class CheckpointManager:
    """JSON-file backed prompt-detail cache scoped to one brand id.

    Files live under ``{checkpoint_dir}/checkpoint_{brand_id}.json`` and store
    a flat mapping of prompt_id -> raw PromptDetail JSON.
    """

    def __init__(self, checkpoint_dir: Path) -> None:
        self._dir = checkpoint_dir

    def _path(self, brand_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in brand_id)
        return self._dir / f"checkpoint_{safe}.json"

    def load(self, brand_id: str) -> dict[str, PromptDetail]:
        """Return the prompt_id -> PromptDetail map (empty if no checkpoint)."""
        path = self._path(brand_id)
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "checkpoint at %s is unreadable (%s); ignoring and starting fresh",
                path,
                exc,
            )
            return {}
        if not isinstance(raw, dict):
            logger.warning("checkpoint at %s is not a dict; ignoring", path)
            return {}
        out: dict[str, PromptDetail] = {}
        for pid, payload in raw.items():
            try:
                out[pid] = PromptDetail.model_validate(payload)
            except ValidationError as exc:
                logger.warning(
                    "checkpoint entry %s invalid (%s); dropping", pid, exc
                )
        logger.info("loaded %d cached prompt details for %s", len(out), brand_id)
        return out

    def save(self, brand_id: str, prompt_id: str, detail: PromptDetail) -> None:
        """Append ``detail`` to the checkpoint for ``brand_id``."""
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(brand_id)
        existing: dict[str, object] = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing = loaded
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "existing checkpoint %s unreadable (%s); will overwrite", path, exc
                )
        existing[prompt_id] = detail.model_dump(mode="json")
        self._atomic_write(path, json.dumps(existing, ensure_ascii=False))

    def clear(self, brand_id: str) -> None:
        """Remove the checkpoint for ``brand_id`` (no-op if absent)."""
        path = self._path(brand_id)
        try:
            path.unlink()
            logger.info("cleared checkpoint %s", path)
        except FileNotFoundError:
            pass

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """Write JSON atomically via temp file + os.replace."""
        directory = path.parent
        directory.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=path.name + ".", suffix=".tmp", dir=str(directory)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(content)
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

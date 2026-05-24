"""Shared helpers for writing per-task Markdown pages.

Both eval (single-run) and SBS comparison flows need:
- stable, sanitized filenames
- collision detection (multiple task keys mapping to same file path)
- best-effort disk writes (log and continue)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class Page:
    out_path: Path
    task_key: str
    content: str
    metric_name: Optional[str] = None


def write_pages(*, pages: Iterable[Page], log: logging.Logger) -> int:
    written = 0
    seen: dict[Path, str] = {}

    for page in pages:
        prev_task = seen.get(page.out_path)
        if prev_task is not None and prev_task != page.task_key:
            log.error(
                "Markdown filename collision: %r and %r -> %s",
                prev_task,
                page.task_key,
                page.out_path,
            )
            continue

        seen[page.out_path] = page.task_key

        try:
            page.out_path.parent.mkdir(parents=True, exist_ok=True)
            page.out_path.write_text(page.content, encoding="utf-8")
            written += 1
        except Exception as e:  # noqa: BLE001
            metric_hint = f" ({page.metric_name})" if page.metric_name else ""
            log.warning(
                "Failed to write Markdown: %s%s (%s)", page.out_path, metric_hint, e
            )

    return written

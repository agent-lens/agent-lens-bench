"""Best-effort JSON scanning helpers for Markdown generation.

These helpers are intentionally lenient:
- invalid JSON files are logged and skipped

They are used by eval + SBS Markdown generators.
"""

import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

from agent_lens.eval.common.json_io import read_json


def load_json_mappings(
    paths: Iterable[Path],
    *,
    log: logging.Logger,
) -> list[tuple[Path, Mapping[str, Any]]]:
    loaded: list[tuple[Path, Mapping[str, Any]]] = []

    for path in paths:
        try:
            data = read_json(path)
        except Exception as e:  # noqa: BLE001
            log.warning("Skipping invalid JSON: %s (%s)", path, e)
            continue

        if isinstance(data, Mapping):
            loaded.append((path, data))

    return loaded

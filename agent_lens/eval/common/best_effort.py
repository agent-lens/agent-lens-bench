"""Small helper for steps that must not fail the main pipeline.

Used for non-critical actions like Markdown rendering.
"""

import logging
from collections.abc import Callable
from typing import TypeVar

LOG = logging.getLogger(__name__)

_T = TypeVar("_T")


def best_effort(fn: Callable[[], _T], *, what: str) -> _T | None:
    """Run `fn()` and swallow any exception.

    Returns the function result, or `None` if it failed.
    """

    try:
        return fn()
    except Exception:  # noqa: BLE001 - intentional best-effort semantics
        LOG.exception("Best-effort step failed: %s", what)
        return None

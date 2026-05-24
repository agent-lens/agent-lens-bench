import logging

LOG = logging.getLogger(__name__)


def add_comment(clearml_task, comment: str) -> None:
    """Best-effort: enrich ClearML task comment with a GitHub Actions link."""
    try:
        clearml_task.set_comment(comment)
    except Exception as e:  # noqa: BLE001
        LOG.exception("Failed to set ClearML comment: %r", e)

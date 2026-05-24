"""Shared (non-comparison-specific) constants for Markdown rendering.

This module exists to avoid eval code importing from `comparison_constants.py`.
"""

from agent_lens.eval.common.paths import sanitize_path_component

FONT_WRAPPER_DIV = "<div style='font-size: 1.3em'>"
REVIEWS_DIR_NAME = "reviews"
UNNAMED_TASK_STEM = "unnamed_task"


def safe_task_file_name(task_key: str) -> str:
    """Sanitize a dataset key so it can be safely used as a file name."""

    stem = sanitize_path_component(task_key).strip() or UNNAMED_TASK_STEM
    return f"{stem}.md"

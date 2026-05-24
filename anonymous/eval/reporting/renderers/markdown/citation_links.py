"""Rewrite judge citation tokens (R1/C1) into Markdown links to per-task pages."""

import logging
import re
from typing import Any, Sequence

from anonymous.eval.reporting.renderers.markdown.markdown_constants import (
    safe_task_file_name,
)
from anonymous.eval.reporting.renderers.markdown.markdown_utils import (
    safe_metric_dir_name,
)

_DEFAULT_RUN_REFERENCE_PREFIX = "R"
_DEFAULT_COMPARISON_REFERENCE_PREFIX = "C"
_DEFAULT_CHATS_REVIEWED_ENTRY_SEPARATOR = ":"


def parse_chats_reviewed_entries(
    *,
    chats_reviewed: Sequence[Any],
    entry_separator: str,
    section_name: str,
    log: logging.Logger | None,
) -> dict[int, str]:
    """Parse `chats reviewed` entries into a 1-indexed mapping.

    Expected entry format: "<index>: <task_key>".
    """

    index_to_task_key: dict[int, str] = {}

    for idx, raw in enumerate(chats_reviewed):
        text = str(raw)
        try:
            prefix, task_key = text.split(entry_separator, 1)
            index = int(prefix.strip())
        except (ValueError, TypeError):
            if log is not None:
                log.warning(
                    "Invalid chats_reviewed entry %r at index %d in section %s",
                    raw,
                    idx,
                    section_name,
                )
            continue

        # Defensive check: preserve the original contract (1-indexed sequential).
        if index != idx + 1:
            if log is not None:
                log.warning(
                    "Unexpected chats_reviewed index %d at position %d in section %s",
                    index,
                    idx,
                    section_name,
                )
            continue

        task_key = task_key.strip()
        if task_key:
            index_to_task_key[index] = task_key

    return index_to_task_key


def metric_dir_from_section_name(section_name: str) -> str:
    metric_dir = section_name
    if metric_dir.endswith("_Judge_Trajectory"):
        metric_dir = metric_dir[: -len("_Judge_Trajectory")]
    elif metric_dir.endswith("_Judge"):
        metric_dir = metric_dir[: -len("_Judge")]
    return metric_dir


def link_review_citations(
    *,
    review: str,
    chats_reviewed: Sequence[Any] | None,
    metric_dir: str,
    reviews_rel_dir: str,
    comparisons_rel_dir: str | None = None,
    run_reference_prefix: str = _DEFAULT_RUN_REFERENCE_PREFIX,
    comparison_reference_prefix: str = _DEFAULT_COMPARISON_REFERENCE_PREFIX,
    chats_reviewed_entry_separator: str = _DEFAULT_CHATS_REVIEWED_ENTRY_SEPARATOR,
    section_name: str = "(unknown)",
    log: logging.Logger | None = None,
) -> str:
    """Replace occurrences of Rk/Ck tokens in `review` with Markdown links.

    `chats_reviewed` must contain entries like "1: <task_key>".
    """

    if not review or not chats_reviewed:
        return review

    metric_dir = safe_metric_dir_name(metric_dir)

    index_to_task_key = parse_chats_reviewed_entries(
        chats_reviewed=chats_reviewed,
        entry_separator=chats_reviewed_entry_separator,
        section_name=section_name,
        log=log,
    )

    index_to_target: dict[str, str] = {}
    for index, task_key in index_to_task_key.items():
        task_file = safe_task_file_name(task_key)

        index_to_target[f"{run_reference_prefix}{index}"] = (
            f"{reviews_rel_dir}/{metric_dir}/{task_file}"
        )

        if comparisons_rel_dir is not None:
            index_to_target[f"{comparison_reference_prefix}{index}"] = (
                f"{comparisons_rel_dir}/{metric_dir}/{task_file}"
            )

    prefix_group = re.escape(run_reference_prefix)
    if comparisons_rel_dir is not None:
        prefix_group = prefix_group + "|" + re.escape(comparison_reference_prefix)

    # Rewrite bracketed tokens like "[R1]" and bare tokens like "R1".
    # Skip already-linked tokens "[R1](...)".
    token_re = re.compile(
        rf"\[(?P<bracketed>(?:{prefix_group})\d+)\](?!\()|\b(?P<bare>(?:{prefix_group})\d+)\b(?!\]\()"
    )

    def _repl(match: re.Match[str]) -> str:
        token = match.group("bracketed") or match.group("bare")
        if not token:
            return match.group(0)

        target = index_to_target.get(token)
        if not target:
            return match.group(0)

        return f"[{token}]({target})"

    return token_re.sub(_repl, review)

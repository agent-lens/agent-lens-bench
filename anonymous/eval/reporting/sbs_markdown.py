"""Render Markdown summaries + per-task comparisons for one dumped SBS folder."""

import argparse
import logging
from pathlib import Path
from typing import Any, List

from anonymous.eval.comparison.io.comparison_dump import COMPARISON_DATA_SUBDIR
from anonymous.eval.common.json_io import read_json
from anonymous.eval.reporting.dialogue_parsing import extract_comparison_text
from anonymous.eval.reporting.markdown_common import (
    append_details_block,
    dump_full_trajectory,
)
from anonymous.eval.reporting.markdown_scan import load_json_mappings
from anonymous.eval.reporting.per_task_pages import Page, write_pages
from anonymous.eval.reporting.renderers.markdown import (
    comparison_report_renderer,
)
from anonymous.eval.reporting.renderers.markdown.comparison_constants import (
    COMPARISONS_DIR_NAME,
)
from anonymous.eval.reporting.renderers.markdown.markdown_constants import (
    FONT_WRAPPER_DIV,
    safe_task_file_name,
)
from anonymous.eval.reporting.renderers.markdown.markdown_utils import (
    ensure_dir,
    safe_metric_dir_name,
)

IGNORE_ROOT_JSON_FILES = {"quality_index.json"}

LOG = logging.getLogger(__name__)

ROOT_JSON_GLOB = "*.json"
DATASET1_PATTERN = "dataset1_*.json"
DATASET2_PATTERN = "dataset2_*.json"
DATASET_PREFIX = "dataset"
REPORT_PREFIX = "report"


def convert_root_jsons_to_md(comparison_dir: Path) -> int:
    """Convert root JSONs to Markdown; returns written count or -1 if no inputs."""

    candidates = [
        p
        for p in sorted(comparison_dir.glob(ROOT_JSON_GLOB))
        if p.name not in IGNORE_ROOT_JSON_FILES
        and not p.name.startswith(DATASET_PREFIX)
        and not p.name.startswith(REPORT_PREFIX)
    ]
    if not candidates:
        return -1

    written = 0
    for json_path in candidates:
        try:
            comparison_report_renderer.convert_file(json_path)
            written += 1
        except Exception as e:  # noqa: BLE001
            LOG.warning("Skipping root JSON Markdown conversion: %s (%s)", json_path, e)

    return written


def _extract_metric_name_from_comparator(comparator_name: str) -> str | None:
    # Expected: "TrajectoryPairsComparator for ToolCalls"
    marker = " for "
    if marker not in comparator_name:
        return None
    return comparator_name.split(marker, 1)[1].strip() or None


def _render_combined_comparison_md(
    *,
    metric_name: str,
    task_key: str,
    point1: Any,
    point2: Any,
    per_task_dialogue: str,
) -> str:
    lines: List[str] = [
        FONT_WRAPPER_DIV,
        f"\n# {metric_name} comparison for `{task_key}`",
        "",
    ]

    judge_text = extract_comparison_text(per_task_dialogue)

    # 3 sections: judge response first, then both trajectories.
    append_details_block(lines=lines, title="Judge's comparison", body=judge_text)

    append_details_block(
        lines=lines,
        title="Agent 1 trajectory",
        body=dump_full_trajectory(point1),
    )
    append_details_block(
        lines=lines,
        title="Agent 2 trajectory",
        body=dump_full_trajectory(point2),
    )

    lines.append("</div>")
    return "\n".join(lines)


def dump_combined_comparisons(comparison_dir: Path) -> int:
    """Dump per-task comparisons; returns written count or -1 if no inputs."""

    data_dir = comparison_dir / COMPARISON_DATA_SUBDIR
    judge_dialogues_dir = data_dir / "judge_dialogues"

    dataset1_files = sorted(data_dir.glob(DATASET1_PATTERN))
    dataset2_files = sorted(data_dir.glob(DATASET2_PATTERN))
    per_task_files = sorted(judge_dialogues_dir.glob("*_perTask.json"))

    if (
        not dataset1_files
        or not dataset2_files
        or not per_task_files
        or not judge_dialogues_dir.is_dir()
    ):
        return -1

    try:
        dataset1 = read_json(dataset1_files[0])
        dataset2 = read_json(dataset2_files[0])
    except Exception as e:  # noqa: BLE001
        LOG.warning("Failed to load datasets for comparisons: %s", e)
        return 0

    comparisons_root = comparison_dir / COMPARISONS_DIR_NAME

    pages: list[Page] = []

    for path, payload in load_json_mappings(per_task_files, log=LOG):
        if not isinstance(payload, dict):
            continue

        # payload: { comparator_name: { task_key: dialogue } }
        for comparator_name, per_task_map in payload.items():
            if not isinstance(per_task_map, dict):
                continue

            metric_name = _extract_metric_name_from_comparator(str(comparator_name))
            if not metric_name:
                LOG.warning(
                    "Cannot infer metric name from comparator: %r", comparator_name
                )
                continue

            metric_dir = comparisons_root / safe_metric_dir_name(metric_name)
            ensure_dir(metric_dir)

            for task_key, dialogue in per_task_map.items():
                if task_key not in dataset1 or task_key not in dataset2:
                    continue

                file_name = safe_task_file_name(str(task_key))
                md_path = metric_dir / file_name
                content = _render_combined_comparison_md(
                    metric_name=metric_name,
                    task_key=str(task_key),
                    point1=dataset1.get(task_key),
                    point2=dataset2.get(task_key),
                    per_task_dialogue=str(dialogue) if dialogue is not None else "",
                )
                pages.append(
                    Page(
                        out_path=md_path,
                        task_key=str(task_key),
                        content=content,
                        metric_name=metric_name,
                    )
                )

    return write_pages(pages=pages, log=LOG)


def generate_comparison_markdown(comparison_dir: Path) -> int:
    """Generate SBS Markdown; returns written count or -1 if no inputs."""

    root_written = convert_root_jsons_to_md(comparison_dir)
    per_task_written = dump_combined_comparisons(comparison_dir)
    if root_written == -1 and per_task_written == -1:
        return -1
    return max(root_written, 0) + max(per_task_written, 0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create Markdown summaries (general.md, etc.) and per-task pairwise "
            "comparison pages for a comparison folder."
        )
    )
    parser.add_argument(
        "comparison_dir",
        help=f"Path to comparison folder with json reports and {COMPARISON_DATA_SUBDIR}/ subdir",
    )
    args = parser.parse_args()

    comparison_dir = Path(args.comparison_dir)
    if not comparison_dir.is_dir():
        raise SystemExit(f"Comparison folder not found: {comparison_dir}")

    generate_comparison_markdown(comparison_dir)


if __name__ == "__main__":  # pragma: no cover
    main()

"""Generate Markdown reports + per-task reviews for one eval run folder."""

import argparse
import logging
from pathlib import Path
from typing import Any, Iterable, List, Mapping

from agent_lens.eval.common.json_io import read_json
from agent_lens.eval.data_framework.field_names import FieldNames
from agent_lens.eval.reporting.dialogue_parsing import extract_final_response
from agent_lens.eval.reporting.markdown_common import (
    append_details_block,
    dump_full_trajectory,
)
from agent_lens.eval.reporting.markdown_scan import load_json_mappings
from agent_lens.eval.reporting.per_task_pages import Page, write_pages
from agent_lens.eval.reporting.renderers.markdown.markdown_constants import (
    FONT_WRAPPER_DIV,
    REVIEWS_DIR_NAME,
    safe_task_file_name,
)
from agent_lens.eval.reporting.renderers.markdown.citation_links import (
    parse_chats_reviewed_entries,
)
from agent_lens.eval.reporting.renderers.markdown.eval_report_renderer import (
    render_report as render_eval_report,
)

from agent_lens.eval.reporting.renderers.markdown.markdown_utils import (
    ensure_dir,
    ordered_unique,
    safe_metric_dir_name,
)

LOG = logging.getLogger(__name__)

REPORTS_DIR_NAME = "reports"
DATASET_GLOB = "dataset_*.json"


def _load_reports(reports_dir: Path) -> list[tuple[Path, Mapping[str, Any]]]:
    return load_json_mappings(reports_dir.glob("*.json"), log=LOG)


def _collect_review_targets_from_reports(
    report_jsons: Iterable[Mapping[str, Any]],
) -> dict[str, list[str]]:
    """Return metric_name -> list of task_keys to render."""

    metric_to_task_keys: dict[str, list[str]] = {}

    for report in report_jsons:
        for metric_name, section in report.items():
            if not isinstance(section, Mapping):
                continue

            chats = section.get("chats reviewed")
            if not isinstance(chats, list) or not chats:
                continue

            index_to_task_key = parse_chats_reviewed_entries(
                chats_reviewed=chats,
                entry_separator=":",
                section_name=str(metric_name),
                log=LOG,
            )
            for task_key in index_to_task_key.values():
                metric_to_task_keys.setdefault(str(metric_name), []).append(task_key)

    return {
        metric: ordered_unique(keys) for metric, keys in metric_to_task_keys.items()
    }


def _render_single_run_review_md(
    *,
    metric_name: str,
    task_key: str,
    point: Mapping[str, Any],
    metric_payload: Mapping[str, Any],
) -> str:
    lines: List[str] = [
        FONT_WRAPPER_DIV,
        "",
        f"# {metric_name} review for `{task_key}`",
        "",
    ]

    dialogue = str(metric_payload.get(FieldNames.JUDGE_DIALOGUE) or "")
    judge_text = extract_final_response(dialogue)

    append_details_block(lines=lines, title="Judge output", body=judge_text)
    append_details_block(
        lines=lines,
        title="Agent trajectory (raw JSON)",
        body=dump_full_trajectory(point),
    )

    lines.append("</div>")
    return "\n".join(lines)


def convert_reports_to_markdown(
    *,
    run_dir: Path,
    reports: list[tuple[Path, Mapping[str, Any]]],
) -> int:
    """Convert `reports/*.json` into sibling `reports/*.md` files."""

    del run_dir  # reserved for future use

    files_written = 0

    for json_path, report in reports:
        scenario_tag = report.get("scenario tag")
        title = (
            str(scenario_tag).strip()
            if isinstance(scenario_tag, str) and scenario_tag.strip()
            else json_path.stem.replace("_", " ")
        )

        try:
            render_eval_report(
                report=report,
                title=title,
                out_path=json_path.with_suffix(".md"),
                reviews_rel_dir=f"../{REVIEWS_DIR_NAME}",
            )
            files_written += 1
        except Exception as e:  # noqa: BLE001
            LOG.warning("Skipping report Markdown conversion: %s (%s)", json_path, e)

    return files_written


def _pick_dataset_path(
    *, run_dir: Path, reports: Iterable[Mapping[str, Any]]
) -> Path | None:
    dataset_rel_path = None
    for report in reports:
        raw = report.get("dataset rel path")
        if isinstance(raw, str) and raw.strip():
            dataset_rel_path = raw
            break

    if dataset_rel_path:
        candidate = run_dir / dataset_rel_path
        if candidate.is_file():
            return candidate

    dataset_files = sorted(run_dir.glob(DATASET_GLOB))
    return dataset_files[0] if dataset_files else None


def dump_task_reviews(*, run_dir: Path, reports: Iterable[Mapping[str, Any]]) -> int:
    files_written = 0

    targets = _collect_review_targets_from_reports(reports)
    if not targets:
        return files_written

    dataset_path = _pick_dataset_path(run_dir=run_dir, reports=reports)
    if dataset_path is None:
        return files_written

    try:
        dataset = read_json(dataset_path)
    except Exception as e:  # noqa: BLE001
        LOG.warning("Failed to load dataset JSON: %s (%s)", dataset_path, e)
        return files_written

    if not isinstance(dataset, dict):
        return files_written

    reviews_root = run_dir / REVIEWS_DIR_NAME

    pages: list[Page] = []

    for metric_name, task_keys in targets.items():
        metric_dir = reviews_root / safe_metric_dir_name(metric_name)
        ensure_dir(metric_dir)

        for task_key in task_keys:
            point = dataset.get(task_key)
            if not isinstance(point, Mapping):
                continue

            metric_payload = point.get(metric_name)
            if not isinstance(metric_payload, Mapping):
                continue

            md_path = metric_dir / safe_task_file_name(task_key)
            content = _render_single_run_review_md(
                metric_name=metric_name,
                task_key=task_key,
                point=point,
                metric_payload=metric_payload,
            )
            pages.append(
                Page(
                    out_path=md_path,
                    task_key=task_key,
                    content=content,
                    metric_name=metric_name,
                )
            )

    files_written += write_pages(pages=pages, log=LOG)

    return files_written


def generate_run_markdown(run_dir: Path) -> int:
    reports_dir = run_dir / REPORTS_DIR_NAME
    if not reports_dir.is_dir():
        return -1

    had_inputs = any(reports_dir.glob("*.json"))

    loaded = _load_reports(reports_dir)
    reports = [r for _, r in loaded]

    files_written = convert_reports_to_markdown(run_dir=run_dir, reports=loaded)
    files_written += dump_task_reviews(run_dir=run_dir, reports=reports)

    return files_written if had_inputs else -1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Markdown reports and per-task reviews for a single run folder."
    )
    parser.add_argument("run_dir", help="Path to <dump_dir>/<run>/<language> folder")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        raise SystemExit(f"Run folder not found: {run_dir}")

    generate_run_markdown(run_dir)


if __name__ == "__main__":  # pragma: no cover
    main()

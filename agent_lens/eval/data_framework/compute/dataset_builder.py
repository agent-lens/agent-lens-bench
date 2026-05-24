import logging
from pathlib import Path
from typing import Any, Mapping

from agent_lens.eval.data_framework.compute.augmentation import (
    augment_point_with_dumps,
)
from agent_lens.eval.data_framework.compute.ids import get_point_id
from agent_lens.eval.data_framework.field_names import FieldNames
from agent_lens.eval.data_framework.io.summary_finder import pick_summary_file
from agent_lens.eval.data_framework.io.summary_reader import read_summary_file
from agent_lens.eval.data_framework.models import SummaryFile

LOG = logging.getLogger(__name__)


def dumps_to_dataset(dump_path: str) -> dict[str, dict[str, dict[str, Any]]]:
    summaries = process_summary_files(dump_path)
    dataset: dict[str, dict[str, dict[str, Any]]] = {}

    dump_root = Path(dump_path)

    for summary in summaries:
        if summary.get("type") == "FailureResult":
            LOG.info("Skipping failed point:\n%s", summary)
            continue

        language = summary.get(FieldNames.LANGUAGE, "java")
        dataset.setdefault(language, {})[get_point_id(summary)] = (
            summary_point_to_datapoint(summary, dump_root=dump_root)
        )

    return dataset


def get_run_info(dump_path: str) -> dict[str, Any]:
    summary = read_summary_file(Path(dump_path))
    return dict(summary.run_info.raw)


def _iter_summary_points(summary: SummaryFile) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for project in summary.projects_results:
        for point in project.iter_points():
            points.append(point.to_summary_dict())
    return points


def process_summary_files(directory: str) -> list[dict[str, Any]]:
    summary = read_summary_file(Path(directory))
    return _iter_summary_points(summary)


def get_last_summary(directory: str | Path) -> str:
    return str(pick_summary_file(Path(directory)))


def summary_point_to_datapoint(
    summary: Mapping[str, Any],
    *,
    dump_root: Path,
) -> dict[str, Any]:
    return augment_point_with_dumps(dump_root=dump_root, point=summary)

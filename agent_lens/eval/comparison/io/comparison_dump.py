import logging
from pathlib import Path
from typing import Any

from agent_lens.eval.comparison.compute.models import Comparison, RunData
from agent_lens.eval.common.json_io import read_json, write_json
from agent_lens.eval.common.paths import sanitize_path_component

LOG = logging.getLogger(__name__)

COMPARISON_DATA_SUBDIR = "data"
JUDGE_DIALOGUES_SUBDIR = "judge_dialogues"


def _merge_datasets_keep_existing(
    *, existing: dict[str, Any] | None, incoming: dict[str, Any], context: str
) -> dict[str, Any]:
    if existing is None:
        return dict(incoming)

    merged = dict(existing)
    for task_key, point in incoming.items():
        if task_key not in merged:
            merged[task_key] = point
            continue

        if merged[task_key] != point:
            LOG.warning(
                "Dataset key collision while merging datasets (%s): task_key=%r differs; keeping the existing entry",
                context,
                task_key,
            )

    return merged


def _get_dirs(
    *, config: dict[str, Any], comparison_name: str, language: str
) -> tuple[Path, Path]:
    comparison_dir = (
        Path(config["dump_dir"]) / sanitize_path_component(comparison_name) / language
    )
    data_dir = comparison_dir / COMPARISON_DATA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    return comparison_dir, data_dir


def _sanitize_names(
    *, config: dict[str, Any], bench_tag_name: str
) -> tuple[str, str, str]:
    run_name1 = sanitize_path_component(str(config["run1_name"]))
    run_name2 = sanitize_path_component(str(config["run2_name"]))
    tag_name = sanitize_path_component(bench_tag_name)
    return run_name1, run_name2, tag_name


def _dump_reports(
    *,
    data_dir: Path,
    tag_name: str,
    run_name1: str,
    run_name2: str,
    report1: dict[str, Any],
    report2: dict[str, Any],
) -> None:
    write_json(data_dir / f"{tag_name}_report1_{run_name1}.json", report1)
    write_json(data_dir / f"{tag_name}_report2_{run_name2}.json", report2)


def _dump_datasets(
    *,
    data_dir: Path,
    run_name1: str,
    run_name2: str,
    run_data: RunData,
    bench_tag_name: str,
) -> None:
    dataset1_path = data_dir / f"dataset1_{run_name1}.json"
    dataset2_path = data_dir / f"dataset2_{run_name2}.json"

    merged_dataset1 = _merge_datasets_keep_existing(
        existing=_read_json_dict_if_exists(dataset1_path),
        incoming=run_data.dataset1,
        context=f"dataset1, run={run_name1}, tag={bench_tag_name}",
    )
    merged_dataset2 = _merge_datasets_keep_existing(
        existing=_read_json_dict_if_exists(dataset2_path),
        incoming=run_data.dataset2,
        context=f"dataset2, run={run_name2}, tag={bench_tag_name}",
    )

    write_json(dataset1_path, merged_dataset1)
    write_json(dataset2_path, merged_dataset2)


def _read_json_dict_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return data


def _dump_judge_dialogues(
    *,
    data_dir: Path,
    tag_name: str,
    judge_summary_dialogues: dict[str, str],
    judge_comparison_dialogues: dict[str, dict[str, str]] | None,
) -> None:
    judge_dialogues_dir = data_dir / JUDGE_DIALOGUES_SUBDIR
    judge_dialogues_dir.mkdir(parents=True, exist_ok=True)

    write_json(
        judge_dialogues_dir / f"{tag_name}_summarization.json", judge_summary_dialogues
    )

    if judge_comparison_dialogues is not None:
        write_json(
            judge_dialogues_dir / f"{tag_name}_perTask.json", judge_comparison_dialogues
        )


def dump_comparison(
    comparison: list[Comparison],
    tldr: str,
    metadata: dict[str, Any],
    config: dict[str, Any],
    run_data: RunData,
    bench_tag_name: str,
    language: str,
    judge_summary_dialogues: dict[str, str],
    judge_comparison_dialogues: dict[str, dict[str, str]] | None = None,
) -> None:
    comparison_name = config.get("name")
    if not comparison_name:
        raise ValueError("Comparison name is empty; expected config['name']")

    comparison_dir, data_dir = _get_dirs(
        config=config, comparison_name=str(comparison_name), language=language
    )

    comparison_dump = [{"TLDR": tldr}] + [c.to_dict() for c in comparison] + [metadata]
    write_json(comparison_dir / f"{bench_tag_name}.json", comparison_dump)

    run_name1, run_name2, tag_name = _sanitize_names(
        config=config, bench_tag_name=bench_tag_name
    )

    _dump_reports(
        data_dir=data_dir,
        tag_name=tag_name,
        run_name1=run_name1,
        run_name2=run_name2,
        report1=run_data.report1,
        report2=run_data.report2,
    )

    _dump_datasets(
        data_dir=data_dir,
        run_name1=run_name1,
        run_name2=run_name2,
        run_data=run_data,
        bench_tag_name=bench_tag_name,
    )

    _dump_judge_dialogues(
        data_dir=data_dir,
        tag_name=tag_name,
        judge_summary_dialogues=judge_summary_dialogues,
        judge_comparison_dialogues=judge_comparison_dialogues,
    )

    LOG.info(
        "\nComparison data for tag `%s` for %s language for `%s` saved to: \n%s",
        bench_tag_name,
        language,
        comparison_name,
        comparison_dir,
    )

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from anonymous.eval.comparison.compute.models import RunData
from anonymous.eval.common.json_io import read_json
from anonymous.eval.common.paths import sanitize_path_component

LOG = logging.getLogger(__name__)


def _load_json(filepath: str | Path) -> Dict[str, Any]:
    data = read_json(Path(filepath))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root is not an object: {filepath}")
    return data


def find_run_dir(base_dir: Path, run_name: str) -> Path:
    if not base_dir.exists() or not base_dir.is_dir():
        raise FileNotFoundError(
            f"Data directory not found or not a directory: {base_dir}"
        )

    run_name_dir = sanitize_path_component(run_name)
    candidates = [
        p for p in base_dir.iterdir() if p.is_dir() and p.name.startswith(run_name_dir)
    ]

    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) == 0:
        raise FileNotFoundError(
            f"No directory found for name '{run_name}' under {base_dir}. "
            f"Expected a folder like '{run_name_dir}-<timestamp>' (or just '{run_name_dir}')."
        )

    raise ValueError(
        f"Multiple directories found for name '{run_name}' under {base_dir}: {[p.name for p in candidates]}."
    )


def get_language_dirs(run_dir: Path) -> tuple[dict[str, Path], bool]:
    inner_dirs = [p for p in run_dir.iterdir() if p.is_dir()]
    if len(inner_dirs) == 0:
        return {"java": run_dir}, True
    return {p.name: run_dir / p.name for p in inner_dirs}, False


def get_run_data(
    *,
    language: str,
    run1_dir: Path,
    run2_dir: Path,
    run1_name: str,
    run2_name: str,
    bench_tag_name: str,
) -> Optional[RunData]:
    for run_dir, run_name in zip([run1_dir, run2_dir], [run1_name, run2_name]):
        report_path = run_dir / "reports" / f"{run_name}-{bench_tag_name}.json"
        if not report_path.is_file():
            LOG.error(
                "No report found for tag `%s` for %s language for `%s`, skipping...",
                bench_tag_name,
                language,
                run_name,
            )
            return None

    report1 = _load_json(run1_dir / "reports" / f"{run1_name}-{bench_tag_name}.json")
    report2 = _load_json(run2_dir / "reports" / f"{run2_name}-{bench_tag_name}.json")

    dataset1_path = run1_dir / report1["dataset rel path"]
    dataset2_path = run2_dir / report2["dataset rel path"]

    dataset1_full = _load_json(dataset1_path)
    dataset2_full = _load_json(dataset2_path)

    def _filter_dataset(ds: Dict[str, Any]) -> Dict[str, Any]:
        return {
            k: v
            for k, v in ds.items()
            if bench_tag_name in v.get("agent_bench_tags", [])
        }

    return RunData(
        dataset1=_filter_dataset(dataset1_full),
        dataset2=_filter_dataset(dataset2_full),
        report1=report1,
        report2=report2,
    )


def get_runs_data_for_tag(config: Dict, bench_tag_name: str) -> Dict[str, RunData]:
    data_dir = Path(config["data_dir"]).resolve()
    run1_name = sanitize_path_component(config["run1_name"])
    run2_name = sanitize_path_component(config["run2_name"])

    run1_dir = find_run_dir(data_dir, run1_name)
    run2_dir = find_run_dir(data_dir, run2_name)

    run1_name = run1_dir.name
    run2_name = run2_dir.name

    run1_lang_dirs, run1_no_langs = get_language_dirs(run1_dir)
    run2_lang_dirs, run2_no_langs = get_language_dirs(run2_dir)

    all_run_data: Dict[str, RunData] = {}

    run1_langs = run1_lang_dirs.keys()
    run2_langs = run2_lang_dirs.keys()
    if len(run1_langs - run2_langs) > 0:
        LOG.error(
            "Some languages found only for run 1, skipping them: %s",
            run1_langs - run2_langs,
        )
    if len(run2_langs - run1_langs) > 0:
        LOG.error(
            "Some languages found only for run 2, skipping them: %s",
            run2_langs - run1_langs,
        )

    for language in run1_langs & run2_langs:
        dir1 = run1_dir if run1_no_langs else (run1_dir / language)
        dir2 = run2_dir if run2_no_langs else (run2_dir / language)

        run_data = get_run_data(
            language=language,
            run1_dir=dir1,
            run2_dir=dir2,
            run1_name=run1_name,
            run2_name=run2_name,
            bench_tag_name=bench_tag_name,
        )
        if run_data is not None:
            all_run_data[language] = run_data

    return all_run_data

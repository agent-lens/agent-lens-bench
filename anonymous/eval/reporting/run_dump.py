import logging
import shlex
import sys
from pathlib import Path
from typing import Dict

from anonymous.eval.common.json_io import write_json
from anonymous.eval.common.run_naming import run_task_name_from_run_info
from anonymous.eval.common.time import get_nice_time
from anonymous.eval.data_framework.field_names import FieldNames
from anonymous.eval.metrics.llm_judge.common.review_style_user import (
    get_review_timezone,
)
from anonymous.eval.reporting.quality_index import save_quality_index_json

LOG = logging.getLogger(__name__)


def dump_data(
    run_info: Dict,
    dataset: Dict,
    reports: Dict,
    dump_dir: str,
    language: str,
    config: Dict,
) -> None:
    run_name = run_task_name_from_run_info(run_info)
    run_dir = Path(dump_dir) / run_name / language

    dataset_dump_filename = f"dataset_{run_name}.json"
    dataset_dump_path = run_dir / dataset_dump_filename
    dataset_dump_path.parent.mkdir(parents=True, exist_ok=True)

    LOG.info("\nSaving dataset to %s", dataset_dump_path)
    write_json(dataset_dump_path, dataset)

    for scenario_tag in reports:
        reports_dump_path = run_dir / "reports" / f"{run_name}-{scenario_tag}.json"

        reports[scenario_tag].update(
            {
                "dataset rel path": dataset_dump_filename,
                "time of creation": get_nice_time(get_review_timezone(config)),
                "scenario tag": scenario_tag,
                "run name": run_name,
                "dataset_config_hash": run_info[
                    FieldNames.RUN_INFO_DATASET_CONFIG_HASH
                ],
                "model_info": f"{run_info[FieldNames.RUN_INFO_PROVIDER_NAME]}:{run_info[FieldNames.RUN_INFO_MODEL_NAME]}",
                "plugin_hash": run_info[FieldNames.RUN_INFO_PLUGIN_HASH],
                "launch args": get_launch_args(),
                "language": language,
            }
        )

        write_json(reports_dump_path, reports[scenario_tag])

    save_quality_index_json(
        run_dir=str(run_dir),
        workflows_report=reports.get("workflows"),
    )


_SENSITIVE_ARG_SUBSTRINGS = ("key", "token", "password")
_MASKED_ARG_VALUE = "***"


def _is_sensitive_arg_name(arg_name: str) -> bool:
    name = arg_name.lower()
    return any(s in name for s in _SENSITIVE_ARG_SUBSTRINGS)


def get_launch_args() -> str:
    """Return CLI args with secret values masked."""

    filtered_args: list[str] = []

    i = 0
    while i < len(sys.argv):
        arg = sys.argv[i]

        # Short-hand for the judge API key.
        if arg == "-k":
            filtered_args.extend([arg, _MASKED_ARG_VALUE])
            if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-"):
                i += 2
            else:
                i += 1
            continue

        if arg.startswith("-k="):
            filtered_args.append(f"-k={_MASKED_ARG_VALUE}")
            i += 1
            continue

        if arg.startswith("--"):
            # Supports both --flag=value and --flag value forms.
            name_value = arg[2:]
            arg_name = name_value.split("=", 1)[0]
            if _is_sensitive_arg_name(arg_name):
                if "=" in name_value:
                    filtered_args.append(f"--{arg_name}={_MASKED_ARG_VALUE}")
                    i += 1
                    continue
                filtered_args.extend([arg, _MASKED_ARG_VALUE])
                if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-"):
                    i += 2
                else:
                    i += 1
                continue

        filtered_args.append(arg)
        i += 1

    return shlex.join(filtered_args)

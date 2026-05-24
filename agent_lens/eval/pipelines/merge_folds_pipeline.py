import json
import logging
import shutil
from copy import deepcopy
from pathlib import Path
from typing import List, Dict

from agent_lens.eval.common.json_io import read_json, write_json
from agent_lens.eval.common.run_naming import run_task_name_from_run_info

import dateutil.parser
import tqdm

from agent_lens.eval.data_framework.compute.dataset_builder import (
    get_last_summary,
)
from agent_lens.eval.data_framework.io.summary_finder import (
    MERGED_SUMMARY_JSON_NAME,
)
from agent_lens.eval.data_framework.field_names import FieldNames
from agent_lens.eval.integrations.bench_constants import IDEA_DUMPS_ARTIFACT_NAME
from agent_lens.eval.integrations.sbs_schedule import SbsRunMode
from agent_lens.eval.integrations.tracking_projects import eval_project_name
from agent_lens.eval.integrations.tracking import (
    PublishInfo,
    TrackingConfig,
    publish_merged_folds,
)

LOG = logging.getLogger(__name__)


def _require_run_info(json_data: object, source: Path) -> Dict:
    if not isinstance(json_data, dict):
        raise ValueError(f"Summary JSON root is not an object: {source}")

    run_info = json_data.get("run_info")
    if not isinstance(run_info, dict):
        raise ValueError(
            f"Summary JSON does not contain a valid run_info object: {source}"
        )

    return run_info


def _clearml_tags_from_run_info(*, run_info: dict, schedule: SbsRunMode) -> List[str]:
    model_tag = f"{run_info[FieldNames.RUN_INFO_PROVIDER_NAME]}:{run_info[FieldNames.RUN_INFO_MODEL_NAME]}"
    plugin_hash_tag = "plugin commit:" + run_info[FieldNames.RUN_INFO_PLUGIN_HASH]
    return [model_tag, plugin_hash_tag, *schedule.tracking_tags]


def merge_folds_and_publish(
    *,
    input_folder: str,
    output_folder: str,
    schedule: SbsRunMode,
    tracking_config: TrackingConfig,
) -> str:
    """Merge IDEA-dumps folds into a single folder and publish it to ClearML.

    Returns the merged run name (printed by CLI and used by CI).
    """

    input_folder_path = Path(input_folder)
    output_folder_path = Path(output_folder)

    if not input_folder_path.is_dir():
        raise FileNotFoundError(
            f"Input folder not found or not a directory: {input_folder_path}"
        )

    # Idempotency / convenience: already-merged dumps can be copied and published as-is.
    merged_summary_path = input_folder_path / MERGED_SUMMARY_JSON_NAME
    if merged_summary_path.is_file():
        LOG.info(
            "Detected a merged dumps folder (%s in the input root), so fold merging is unnecessary; only publishing.",
            merged_summary_path.name,
        )
        json_data = read_json(merged_summary_path)
        run_info = _require_run_info(json_data, source=merged_summary_path)

        extended_exp_name = run_task_name_from_run_info(run_info)
        clearml_tags = _clearml_tags_from_run_info(
            run_info=run_info,
            schedule=schedule,
        )

        publish_folder = input_folder_path
        if output_folder_path.resolve() != input_folder_path.resolve():
            LOG.info(
                "Input already looks merged; copying it to output_folder before publishing (input=%s, output=%s)",
                input_folder_path,
                output_folder_path,
            )
            shutil.copytree(input_folder_path, output_folder_path, dirs_exist_ok=True)
            publish_folder = output_folder_path

        publish_merged_folds(
            tracking_config=tracking_config,
            project_name=eval_project_name(tracking_config=tracking_config),
            task_name=extended_exp_name,
            artifact_name=IDEA_DUMPS_ARTIFACT_NAME,
            output_folder=publish_folder,
            publish_info=PublishInfo(
                tags=clearml_tags, comment=json.dumps(run_info, ensure_ascii=False)
            ),
        )

        return extended_exp_name

    fold_paths = [
        p for p in sorted(input_folder_path.iterdir(), key=lambda p: p.name) if p.is_dir()
    ]
    if any(input_folder_path.glob("summary*.json")):
        fold_paths = [input_folder_path]
    if not fold_paths:
        raise FileNotFoundError(f"No fold subdirectories found in: {input_folder_path}")

    dataset_hash_array = set()
    dataset_config_hash_array = set()
    projects_results = []
    plugin_hash, model_name, provider_name, experiment_name = None, None, None, None
    min_timestamp = None
    min_timestamp_str = None

    for fold_path in tqdm.tqdm(fold_paths):
        path = Path(get_last_summary(fold_path))
        json_data = read_json(path)
        run_info = _require_run_info(json_data, source=path)

        fold_name = fold_path.name
        if "-" in fold_name:
            default_language = fold_name.split("-")[0]
        else:
            default_language = "java"

        if (
            provider_name is not None
            and model_name is not None
            and plugin_hash is not None
        ):
            assert run_info[FieldNames.RUN_INFO_EXP_NAME] == experiment_name, (
                f"Incompatible logs, different exp name: {run_info[FieldNames.RUN_INFO_EXP_NAME]} vs {experiment_name}."
            )
            assert run_info[FieldNames.RUN_INFO_PLUGIN_HASH] == plugin_hash, (
                f"Incompatible logs, different plugin hash: {run_info[FieldNames.RUN_INFO_PLUGIN_HASH]} vs {plugin_hash}."
            )
            assert run_info[FieldNames.RUN_INFO_MODEL_NAME] == model_name, (
                f"Incompatible logs, different model name: {run_info[FieldNames.RUN_INFO_MODEL_NAME]} vs {model_name}."
            )
            assert run_info[FieldNames.RUN_INFO_PROVIDER_NAME] == provider_name, (
                f"Incompatible logs, different provider name: {run_info[FieldNames.RUN_INFO_PROVIDER_NAME]} vs {provider_name}."
            )
        else:
            plugin_hash, model_name, provider_name, experiment_name = (
                run_info[FieldNames.RUN_INFO_PLUGIN_HASH],
                run_info[FieldNames.RUN_INFO_MODEL_NAME],
                run_info[FieldNames.RUN_INFO_PROVIDER_NAME],
                run_info[FieldNames.RUN_INFO_EXP_NAME],
            )

        curr_timestamp_str = run_info[FieldNames.RUN_INFO_TIMESTAMP]
        curr_timestamp = dateutil.parser.isoparse(curr_timestamp_str)
        if min_timestamp is None or curr_timestamp < min_timestamp:
            min_timestamp = curr_timestamp
            min_timestamp_str = curr_timestamp_str

        dataset_hash_array.add(run_info["dataset_hash"])
        dataset_config_hash_array.add(run_info[FieldNames.RUN_INFO_DATASET_CONFIG_HASH])
        projects_results_part = json_data.get(FieldNames.PROJECTS_RESULTS, [])
        if not isinstance(projects_results_part, list):
            raise ValueError(f"Summary JSON projects_results is not a list: {path}")

        for result in projects_results_part:
            if FieldNames.LANGUAGE not in result:
                result[FieldNames.LANGUAGE] = default_language
        projects_results += projects_results_part

        if fold_path.resolve() != output_folder_path.resolve():
            shutil.copytree(fold_path, output_folder_path, dirs_exist_ok=True)

    merged_data = deepcopy(json_data)
    merged_run_info = _require_run_info(
        merged_data, source=Path(MERGED_SUMMARY_JSON_NAME)
    )

    # select min timestamp for merged dataset
    merged_run_info[FieldNames.RUN_INFO_TIMESTAMP] = min_timestamp_str
    extended_exp_name = run_task_name_from_run_info(merged_run_info)
    merged_run_info["dataset_hash"] = list(dataset_hash_array)
    merged_run_info[FieldNames.RUN_INFO_DATASET_CONFIG_HASH] = "+".join(
        sorted(dataset_config_hash_array)
    )
    merged_data[FieldNames.PROJECTS_RESULTS] = projects_results

    # Always write merged summary to disk (ClearML publishing is optional).
    write_json(output_folder_path / MERGED_SUMMARY_JSON_NAME, merged_data)

    clearml_tags = _clearml_tags_from_run_info(
        run_info=merged_run_info,
        schedule=schedule,
    )

    publish_merged_folds(
        tracking_config=tracking_config,
        project_name=eval_project_name(tracking_config=tracking_config),
        task_name=extended_exp_name,
        artifact_name=IDEA_DUMPS_ARTIFACT_NAME,
        output_folder=output_folder_path,
        publish_info=PublishInfo(
            tags=clearml_tags,
            comment=json.dumps(merged_run_info, ensure_ascii=False),
        ),
    )

    return extended_exp_name

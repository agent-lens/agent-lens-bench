"""ClearML download helpers for GitHub workflow CLIs."""

from pathlib import Path
from typing import Tuple

from agent_lens.eval.integrations.bench_constants import (
    EVAL_REPORT_ARTIFACT_NAME,
)
from agent_lens.eval.integrations.clearml.facade import (
    download_artifact,
    find_anchor_run_by_schedule,
)
from agent_lens.eval.integrations.sbs_schedule import SbsRunMode
from agent_lens.eval.integrations.tracking import TrackingConfig
from agent_lens.eval.integrations.tracking_projects import eval_project_name


def download_clearml_artifact(
    run_name: str, project_name: str, artifact_name: str, output_folder: str
) -> None:
    download_artifact(
        project_name=project_name,
        run_name=run_name,
        artifact_name=artifact_name,
        output_folder=Path(output_folder),
    )


def download_2_runs(
    *,
    tracking_config: TrackingConfig,
    anchor_run_name: str,
    current_run_name: str,
    output_dir: str,
    schedule: SbsRunMode,
) -> Tuple[str, str]:
    if current_run_name.strip() == "":
        raise ValueError("ClearML current run name is blank")

    project_name = eval_project_name(tracking_config=tracking_config)

    if schedule.is_scheduled:
        anchor_run_name = find_anchor_run_by_schedule(
            project_name=project_name,
            schedule=schedule,
            current_run_name=current_run_name,
        )
    elif anchor_run_name.strip() == "":
        raise ValueError("ClearML anchor run name is blank in manual mode.")

    if project_name.strip() == "":
        raise ValueError(
            "ClearML download requested but tracking_backend is none; set tracking_config.yaml: tracking_backend=clearml"
        )

    download_clearml_artifact(
        current_run_name, project_name, EVAL_REPORT_ARTIFACT_NAME, output_dir
    )
    download_clearml_artifact(
        anchor_run_name, project_name, EVAL_REPORT_ARTIFACT_NAME, output_dir
    )

    return anchor_run_name, current_run_name

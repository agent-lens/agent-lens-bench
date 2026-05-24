import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from anonymous.eval.integrations.sbs_schedule import SbsRunMode

from anonymous.eval.integrations.clearml.helpers import add_comment
from anonymous.eval.integrations.clearml.runtime import get_clearml
from anonymous.eval.integrations.github import get_current_github_action_link
from anonymous.eval.integrations.tracking import TrackingConfig

# Keep internal helpers private to this package; public API is re-exported from __init__.py.

if TYPE_CHECKING:
    from clearml import Task as ClearMLTask

LOG = logging.getLogger(__name__)

_CLEARML_ORDER_BY_MOST_RECENT = {"order_by": ["-created"]}
_NIGHTLY_PREFIX = "nightly-"


def _get_most_recent_task_by_name(
    *, clearml, project_name: str, task_name: str
) -> "ClearMLTask":
    tasks = clearml.Task.get_tasks(
        task_name=task_name,
        project_name=project_name,
        task_filter=_CLEARML_ORDER_BY_MOST_RECENT,
    )
    if len(tasks) == 0:
        raise RuntimeError(
            f"Could not find any ClearML tasks with name {task_name!r} in project {project_name!r}"
        )
    return tasks[0]


def _get_most_recent_tasks_by_tags(
    *, clearml, project_name: str, tags: list[str]
) -> list["ClearMLTask"]:
    return list(
        clearml.Task.get_tasks(
            project_name=project_name,
            tags=tags,
            task_filter=_CLEARML_ORDER_BY_MOST_RECENT,
        )
    )


def _require_task_id(task: "ClearMLTask") -> str:
    task_id = getattr(task, "task_id", None) or getattr(task, "id", None)
    if task_id is None or str(task_id).strip() == "":
        raise RuntimeError(
            "ClearML Task does not expose a task id (expected attribute .task_id or .id)."
        )
    return str(task_id)


def _create_testing_task(
    *, clearml, project_name: str, task_name: str, tags: list[str]
) -> "ClearMLTask":
    task = clearml.Task.create(
        project_name=project_name,
        task_type=clearml.TaskTypes.testing,
        task_name=task_name,
    )
    if tags:
        task.add_tags(tags)
    task.mark_started(force=True)
    return task


def _upload_and_complete(
    *,
    task: "ClearMLTask",
    artifact_name: str,
    artifact_object,
    tracking_config: TrackingConfig,
    comment: str | None,
    log_name: str | None,
) -> None:
    task_id = _require_task_id(task)
    task_name = log_name or getattr(task, "name", "")
    LOG.info(
        "\nUploading results to ClearML now (task_id=%s, task=%s, artifact=%s, dir=%s).",
        task_id,
        task_name,
        artifact_name,
        artifact_object,
    )
    task.upload_artifact(artifact_name, artifact_object=artifact_object)
    task.flush(wait_for_uploads=True)
    LOG.info("Upload finished; finalizing task...")

    if comment is not None and comment.strip() != "":
        comment = _add_github_run_url(comment, tracking_config)
        add_comment(task, comment)

    task.mark_completed()

def _add_github_run_url(comment: str, tracking_config: TrackingConfig) -> str:
    github_action_run_url = get_current_github_action_link(tracking_config)
    if github_action_run_url is not None:
        comment = f"Github run: {github_action_run_url}\n{comment}"
    return comment

def _get_task_by_id(*, clearml, task_id: str) -> "ClearMLTask":
    task = clearml.Task.get_task(task_id=task_id)
    if task is None:
        raise RuntimeError(f"Could not fetch ClearML task by id: {task_id!r}")
    return task


def start_eval_tracking(*, project_name: str, run_name: str) -> str:
    """Attach to an existing eval run task in ClearML (strict).

    Returns task_id.
    """

    clearml = get_clearml()

    task = _get_most_recent_task_by_name(
        clearml=clearml, project_name=project_name, task_name=run_name
    )
    task_id = _require_task_id(task)
    LOG.info(
        "Attaching to ClearML task (project=%s, task_name=%s, task_id=%s)",
        project_name,
        run_name,
        task_id,
    )
    task.mark_started(force=True)
    return task_id


def finish_eval_tracking(*, task_id: str, dump_dir: str, artifact_name: str, tracking_config: TrackingConfig) -> None:
    """Upload eval artifacts and close the ClearML task (strict)."""

    clearml = get_clearml()
    task = _get_task_by_id(clearml=clearml, task_id=task_id)

    _upload_and_complete(
        task=task,
        artifact_name=artifact_name,
        artifact_object=dump_dir,
        comment=None,
        log_name=None,
        tracking_config=tracking_config,
    )


def start_sbs_tracking(
    *,
    project_name: str,
    task_name: str,
    schedule: SbsRunMode,
) -> str:
    """Create a ClearML task for an SBS comparison (strict).

    Returns task_id.
    """

    clearml = get_clearml()

    tags = schedule.tracking_tags
    task = _create_testing_task(
        clearml=clearml,
        project_name=project_name,
        task_name=task_name,
        tags=tags,
    )
    task_id = _require_task_id(task)
    LOG.info(
        "Created ClearML task (project=%s, task_name=%s, task_id=%s, tags=%s)",
        project_name,
        task_name,
        task_id,
        tags,
    )

    return task_id


def finish_sbs_tracking(
    *,
    task_id: str,
    dump_dir: str,
    artifact_name: str,
    comment: str,
    log_name: str,
    tracking_config: TrackingConfig,
) -> None:
    clearml = get_clearml()
    task = _get_task_by_id(clearml=clearml, task_id=task_id)

    _upload_and_complete(
        task=task,
        artifact_name=artifact_name,
        artifact_object=dump_dir,
        comment=comment,
        log_name=log_name,
        tracking_config=tracking_config,
    )

    LOG.info("Finished comparison for all requested tags. Task name=%s", log_name)


def publish_merged_folds(
    *,
    project_name: str,
    task_name: str,
    tags: list[str],
    artifact_name: str,
    output_folder: Path,
    comment: str,
    tracking_config: TrackingConfig,
) -> None:
    """Publish merged IDEA dumps folder to ClearML (strict)."""

    clearml = get_clearml()

    task = _create_testing_task(
        clearml=clearml,
        project_name=project_name,
        task_name=task_name,
        tags=tags,
    )
    task_id = _require_task_id(task)
    LOG.info(
        "Created ClearML task for merged folds (project=%s, task_name=%s, task_id=%s, tags=%s)",
        project_name,
        task_name,
        task_id,
        tags,
    )

    _upload_and_complete(
        task=task,
        artifact_name=artifact_name,
        artifact_object=output_folder,
        comment=comment,
        log_name=task_name,
        tracking_config=tracking_config,
    )


def download_artifact(
    *, project_name: str, run_name: str, artifact_name: str, output_folder: Path
) -> None:
    """Download a ClearML artifact into output_folder."""

    clearml = get_clearml()
    task = _get_most_recent_task_by_name(
        clearml=clearml, project_name=project_name, task_name=run_name
    )

    task_id = _require_task_id(task)

    artifacts = getattr(task, "artifacts", None) or {}
    if artifact_name not in artifacts:
        raise RuntimeError(
            f"ClearML artifact missing: run_name={run_name!r}, task_id={task_id}, "
            f"artifact_name={artifact_name!r}, available_artifacts={sorted(artifacts.keys())}"
        )

    artifact_path = Path(str(artifacts[artifact_name].get()))

    try:
        shutil.copytree(artifact_path, output_folder, dirs_exist_ok=True)
    except FileNotFoundError as e:
        LOG.error(
            "ClearML artifact path not found; failing download: run_name=%r task_id=%s artifact_name=%s artifact_path=%s",
            run_name,
            task_id,
            artifact_name,
            artifact_path,
        )
        raise FileNotFoundError(
            "ClearML artifact path not found; likely artifact not uploaded. "
            f"run_name={run_name!r}, task_id={task_id}, artifact_name={artifact_name!r}, artifact_path={str(artifact_path)!r}"
        ) from e


def _extract_date_from_nightly_name(task_name: str) -> datetime:
    if not task_name.startswith(_NIGHTLY_PREFIX):
        raise ValueError(
            f"Task name {task_name!r} does not start with {_NIGHTLY_PREFIX!r}"
        )

    date_part = task_name[len(_NIGHTLY_PREFIX) :].split("T")[0]

    try:
        return datetime.strptime(date_part, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format in task name '{task_name}'")


def find_anchor_run_by_schedule(
    *, project_name: str, schedule: SbsRunMode, current_run_name: str
) -> str:
    """Find an anchor run name for a scheduled SBS comparison."""

    if not schedule.is_scheduled:
        raise ValueError("Anchor lookup by schedule requires a scheduled run mode")

    tags = schedule.tracking_tags
    tasks = _get_most_recent_tasks_by_tags(
        clearml=get_clearml(),
        project_name=project_name,
        tags=tags,
    )
    current_date = _extract_date_from_nightly_name(current_run_name)
    most_recent_previous_date = None
    anchor_task = None
    for task in tasks:
        task_date = _extract_date_from_nightly_name(task.name)
        if (current_date - task_date).days >= schedule.anchor_day_lag:
            if (
                most_recent_previous_date is None
                or task_date > most_recent_previous_date
            ):
                most_recent_previous_date = task_date
                anchor_task = task

    if anchor_task is None:
        raise RuntimeError(
            f"Could not find any {schedule} run older than {schedule.anchor_day_lag} days before {current_run_name}"
        )

    return anchor_task.name

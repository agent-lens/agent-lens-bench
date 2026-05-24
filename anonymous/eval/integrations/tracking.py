import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional, TypeAlias, TypedDict, cast

from anonymous.eval.integrations.sbs_schedule import SbsRunMode

LOG = logging.getLogger(__name__)


class ClearmlTrackingConfig(TypedDict, total=False):
    eval_project_name: str
    sbs_project_name: str
    task_url_template: str


class TrackingConfigDict(TypedDict, total=False):
    tracking_backend: str
    alerting_backend: str
    github_action_run_url: str
    clearml: ClearmlTrackingConfig


TrackingConfig: TypeAlias = TrackingConfigDict

BackendName = Literal["none", "clearml"]

_BACKEND_CLEARML: Literal["clearml"] = "clearml"
_BACKEND_NONE: Literal["none"] = "none"

_ALLOWED_BACKENDS: set[BackendName] = {_BACKEND_CLEARML, _BACKEND_NONE}
_DEFAULT_BACKEND: BackendName = _BACKEND_NONE


def resolve_backend(*, tracking_config: TrackingConfig) -> BackendName:
    """Resolve selected tracking backend from the provided config dict."""

    backend_raw = (tracking_config or {}).get("tracking_backend")
    if backend_raw is None or str(backend_raw).strip() == "":
        backend_raw = _DEFAULT_BACKEND

    backend = str(backend_raw).strip().lower()
    if backend not in _ALLOWED_BACKENDS:
        raise ValueError(
            f"Unknown tracking backend: {backend!r}. Allowed: {sorted(_ALLOWED_BACKENDS)}"
        )

    return cast(BackendName, backend)


@lru_cache(maxsize=1)
def _clearml_module():
    # Importing our integration package is safe: it doesn't import the ClearML SDK
    # until ClearML facade code calls get_clearml().
    from anonymous.eval.integrations import clearml

    return clearml


@dataclass(frozen=True)
class TrackingHandle:
    """Backend-neutral handle stored by pipelines and passed back to finish_*.

    Contains only plain data (no SDK objects).
    """

    backend: BackendName
    backend_run_id: Optional[str]


@dataclass(frozen=True)
class SbsFinishInfo:
    comment: Optional[str] = None
    task_name: Optional[str] = None


@dataclass(frozen=True)
class PublishInfo:
    tags: list[str]
    comment: Optional[str] = None


@dataclass(frozen=True)
class EvalFinishInfo:
    comment: Optional[str] = None


def _none_handle() -> TrackingHandle:
    return TrackingHandle(backend=_BACKEND_NONE, backend_run_id=None)


def _clearml_handle(*, task_id: str) -> TrackingHandle:
    return TrackingHandle(backend=_BACKEND_CLEARML, backend_run_id=task_id)


def _require_clearml_run_id(*, handle: TrackingHandle) -> str:
    if handle.backend != _BACKEND_CLEARML:
        raise RuntimeError(f"Expected ClearML handle; got backend={handle.backend!r}")
    if handle.backend_run_id is None:
        raise RuntimeError("ClearML handle has backend_run_id=None")
    return handle.backend_run_id


def start_eval_tracking(
    *, tracking_config: TrackingConfig, project_name: str, run_name: str
) -> TrackingHandle:
    backend = resolve_backend(tracking_config=tracking_config)
    if backend == _BACKEND_NONE:
        return _none_handle()
    elif backend == _BACKEND_CLEARML:
        task_id = _clearml_module().start_eval_tracking(
            project_name=project_name,
            run_name=run_name,
        )
        return _clearml_handle(task_id=task_id)
    else:
        raise RuntimeError(f"Unknown tracking backend: {backend!r}")


def finish_eval_tracking(
    *,
    handle: TrackingHandle,
    dump_dir: str,
    artifact_name: str,
    tracking_config: TrackingConfig,
    finish_info: Optional[EvalFinishInfo] = None,
) -> None:
    # Routing follows the handle to prevent config drift between start/finish.
    if handle.backend == _BACKEND_NONE:
        return

    task_id = _require_clearml_run_id(handle=handle)
    _clearml_module().finish_eval_tracking(
        task_id=task_id,
        dump_dir=dump_dir,
        artifact_name=artifact_name,
        tracking_config=tracking_config,
    )

    if finish_info is not None and finish_info.comment:
        LOG.info("Eval finish comment: %s", finish_info.comment)


def start_sbs_tracking(
    *,
    tracking_config: TrackingConfig,
    project_name: str,
    task_name: str,
    schedule: SbsRunMode = SbsRunMode.MANUAL,
) -> TrackingHandle:
    backend = resolve_backend(tracking_config=tracking_config)

    if backend == _BACKEND_NONE:
        return _none_handle()

    elif backend == _BACKEND_CLEARML:
        task_id = _clearml_module().start_sbs_tracking(
            project_name=project_name,
            task_name=task_name,
            schedule=schedule,
        )
        return _clearml_handle(task_id=task_id)

    else:
        raise RuntimeError(f"Unknown tracking backend: {backend!r}")


def finish_sbs_tracking(
    *,
    handle: TrackingHandle,
    dump_dir: str,
    artifact_name: str,
    tracking_config: TrackingConfig,
    finish_info: Optional[SbsFinishInfo] = None,
) -> None:
    if handle.backend == _BACKEND_NONE:
        return

    finish_info = finish_info or SbsFinishInfo()

    task_id = _require_clearml_run_id(handle=handle)
    _clearml_module().finish_sbs_tracking(
        task_id=task_id,
        dump_dir=dump_dir,
        artifact_name=artifact_name,
        comment=(finish_info.comment or ""),
        log_name=(finish_info.task_name or ""),
        tracking_config=tracking_config,
    )


def publish_merged_folds(
    *,
    tracking_config: TrackingConfig,
    project_name: str,
    task_name: str,
    artifact_name: str,
    output_folder: Path,
    publish_info: PublishInfo,
) -> None:
    backend = resolve_backend(tracking_config=tracking_config)
    if backend == _BACKEND_NONE:
        return

    _clearml_module().publish_merged_folds(
        project_name=project_name,
        task_name=task_name,
        tags=publish_info.tags,
        artifact_name=artifact_name,
        output_folder=output_folder,
        comment=publish_info.comment or "",
        tracking_config=tracking_config,
    )


def tracking_run_url(
    *, tracking_config: TrackingConfig, handle: TrackingHandle
) -> Optional[str]:
    """Return a human-friendly URL for a run/task."""

    if handle.backend != _BACKEND_CLEARML:
        return None
    if handle.backend_run_id is None:
        return None

    from anonymous.eval.integrations.clearml.config import (
        clearml_task_url_template,
    )

    template = clearml_task_url_template(tracking_config=tracking_config)
    if template.strip() == "":
        LOG.warning(
            "ClearML task_url_template is empty; Telegram alerts will be sent without a ClearML link. "
            "Set tracking_config.yaml: clearml.task_url_template"
        )
        return None

    try:
        # Local import keeps the integration boundary intact.
        from anonymous.eval.integrations.clearml.urls import task_url

        return task_url(
            task_id=handle.backend_run_id,
            task_url_template=template,
        )
    except Exception:  # noqa: BLE001 - best-effort for alerts
        LOG.exception(
            "Failed to compose ClearML task URL for backend_run_id=%r",
            handle.backend_run_id,
        )
        return None

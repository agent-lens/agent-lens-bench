from typing import Any

from agent_lens.eval.integrations.tracking import TrackingConfig


def _clearml_section(*, tracking_config: TrackingConfig) -> dict[str, Any]:
    section = (tracking_config or {}).get("clearml") or {}
    if not isinstance(section, dict):
        raise ValueError("tracking_config['clearml'] must be a mapping")
    return section


def clearml_task_url_template(*, tracking_config: TrackingConfig) -> str:
    return str(
        _clearml_section(tracking_config=tracking_config).get("task_url_template") or ""
    )


def clearml_eval_project_name(*, tracking_config: TrackingConfig) -> str:
    name = str(
        _clearml_section(tracking_config=tracking_config).get("eval_project_name") or ""
    ).strip()
    if name == "":
        raise ValueError("tracking_config.clearml.eval_project_name is blank")
    return name


def clearml_sbs_project_name(*, tracking_config: TrackingConfig) -> str:
    name = str(
        _clearml_section(tracking_config=tracking_config).get("sbs_project_name") or ""
    ).strip()
    if name == "":
        raise ValueError("tracking_config.clearml.sbs_project_name is blank")
    return name

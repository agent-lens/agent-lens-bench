from anonymous.eval.integrations.tracking import TrackingConfig, resolve_backend


def eval_project_name(*, tracking_config: TrackingConfig) -> str:
    backend = resolve_backend(tracking_config=tracking_config)
    if backend == "none":
        return ""

    from anonymous.eval.integrations.clearml.config import (
        clearml_eval_project_name,
    )

    return clearml_eval_project_name(tracking_config=tracking_config)


def sbs_project_name(*, tracking_config: TrackingConfig) -> str:
    backend = resolve_backend(tracking_config=tracking_config)
    if backend == "none":
        return ""

    from anonymous.eval.integrations.clearml.config import (
        clearml_sbs_project_name,
    )

    return clearml_sbs_project_name(tracking_config=tracking_config)

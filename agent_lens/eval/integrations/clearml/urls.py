def task_url(*, task_id: str, task_url_template: str) -> str:
    """Compose a human-friendly ClearML task URL.

    No hardcoded default on purpose: the URL depends on ClearML server/project.
    """

    if task_url_template is None or str(task_url_template).strip() == "":
        raise RuntimeError(
            "ClearML task URL template is not configured. "
            "Set tracking_config.yaml: clearml.task_url_template"
        )

    return str(task_url_template).format(task_id=task_id)

from typing import Any, Mapping

from agent_lens.eval.common.paths import sanitize_path_component
from agent_lens.eval.data_framework.field_names import FieldNames


def run_task_name_from_run_info(run_info: Mapping[str, Any]) -> str:
    """Stable unique run id used for both dumps folder naming and ClearML task naming."""

    experiment_name = str(run_info.get(FieldNames.RUN_INFO_EXP_NAME, "")).strip()
    timestamp = str(run_info.get(FieldNames.RUN_INFO_TIMESTAMP, "")).strip()

    if experiment_name == "":
        raise ValueError(f"run_info[{FieldNames.RUN_INFO_EXP_NAME!r}] is blank")
    if timestamp == "":
        raise ValueError(f"run_info[{FieldNames.RUN_INFO_TIMESTAMP!r}] is blank")

    exp_s = sanitize_path_component(experiment_name)
    ts_s = sanitize_path_component(timestamp)

    # Avoid double-appending if experiment_name already includes the timestamp.
    if exp_s.endswith(f"-{ts_s}"):
        return exp_s

    return f"{exp_s}-{ts_s}"

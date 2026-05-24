from typing import Any, Mapping

from anonymous.eval.data_framework.field_names import FieldNames


def get_point_id(summary_point: Mapping[str, Any]) -> str:
    return (
        f"{summary_point[FieldNames.AGENT_SCENARIO_NAME]}|"
        f"{summary_point[FieldNames.SIMULATOR_NAME]}"
    )

from typing import Any, Mapping

from agent_lens.eval.data_framework.field_names import FieldNames


MISSING_REVIEW_DESCRIPTION = "Unknown"


def get_judge_review(
    point: Mapping[str, Any],
    metric_name: str,
) -> str:
    metric_data = point.get(metric_name, {}) or {}
    return str(metric_data.get(FieldNames.JUDGE_REVIEW, MISSING_REVIEW_DESCRIPTION))


def get_judge_review_or_symmetric_stub(
    *,
    point: Mapping[str, Any],
    reference_point: Mapping[str, Any],
    metric_name: str,
) -> str:
    if get_judge_review(reference_point, metric_name) == MISSING_REVIEW_DESCRIPTION:
        return MISSING_REVIEW_DESCRIPTION
    return get_judge_review(point, metric_name)

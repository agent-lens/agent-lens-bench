"""Compute and persist a compact quality index for a benchmark run."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from anonymous.eval.common.json_io import write_json
from anonymous.eval.metrics.llm_judge.end_result import EndResultMetric
from anonymous.eval.metrics.llm_judge.instruction_compliance import (
    InstructionComplianceMetric,
)
from anonymous.eval.metrics.llm_judge.pitfalls import PitfallsMetric
from anonymous.eval.metrics.llm_judge.pleasantness import PleasantnessMetric
from anonymous.eval.metrics.llm_judge.tool_calls import ToolCallsMetric

PITFALLS_MULTIPLIER = 1.0
FORMAL_VERIFICATION_WARNING_THRESHOLD = 0.3
# Sum of 6 components, each in [0, 1]; scale to a 0..100 quality index.
QUALITY_INDEX_MAX_SUM = 6.0
QUALITY_INDEX_SCALE = 100.0

WARNING_MISSING_REPORT = "report is missing"
WARNING_LOW_FORMAL = "formal verification is lower than 0.3 (possible repo corruption)."
WARNING_UNPARSEABLE_AS_ZERO = "some values were unparseable and were treated as 0.0"


def _warning_missing_metrics(missing: List[str]) -> str:
    return f"missing metrics (treated as 0.0): {', '.join(sorted(missing))}"


# Hardcoded to keep scores comparable across runs; missing metrics are treated as 0.0 with a warning.
_EXPECTED_METRIC_NAMES = {
    EndResultMetric.get_name(),
    InstructionComplianceMetric.get_name(),
    PitfallsMetric.get_name(),
    PleasantnessMetric.get_name(),
    ToolCallsMetric.get_name(),
}


@dataclass(frozen=True)
class SplitIndexResult:
    index: float
    formal_verification_success_rate: float
    had_unparseable_values: bool
    missing_metrics: List[str] = field(default_factory=list)


def _try_float(value: Any) -> Tuple[Optional[float], bool]:
    """Parse float; returns (value, unparseable_flag).

    unparseable_flag is True only when the input was present (not None) but couldn't be parsed.
    """

    if value is None:
        return None, False

    if isinstance(value, (int, float)):
        return float(value), False

    if isinstance(value, str):
        try:
            return float(value), False
        except ValueError:
            return None, True

    return None, True


def _score_mean(report: Dict[str, Any], section_name: str) -> Tuple[float, bool]:
    """Return section["score mean"] as float and unparseable_flag.

    Missing section/field => (0.0, False)
    Present but unparseable => (0.0, True)
    """

    section = report.get(section_name)
    if not isinstance(section, dict):
        return 0.0, False

    value = section.get("score mean")
    parsed, bad = _try_float(value)
    if parsed is None:
        return 0.0, bad
    return parsed, bad


def compute_quality_index_for_report(split_report: Dict[str, Any]) -> SplitIndexResult:
    had_unparseable = False
    missing_metrics = [
        name for name in _EXPECTED_METRIC_NAMES if split_report.get(name) is None
    ]

    formal_raw = split_report.get("formal_verification_success_rate")
    formal, formal_bad = _try_float(formal_raw)
    had_unparseable |= formal_bad
    formal_val = formal or 0.0

    end_result_score_mean, bad1 = _score_mean(split_report, EndResultMetric.get_name())
    instruction_compliance_score_mean, bad2 = _score_mean(
        split_report, InstructionComplianceMetric.get_name()
    )
    pitfalls_score_mean, bad3 = _score_mean(split_report, PitfallsMetric.get_name())
    pleasantness_score_mean, bad4 = _score_mean(
        split_report, PleasantnessMetric.get_name()
    )
    toolcalls_score_mean, bad5 = _score_mean(split_report, ToolCallsMetric.get_name())
    had_unparseable |= bad1 or bad2 or bad3 or bad4 or bad5

    index_value = (
        formal_val
        + end_result_score_mean
        + instruction_compliance_score_mean
        + (pitfalls_score_mean * PITFALLS_MULTIPLIER)
        + pleasantness_score_mean
        + toolcalls_score_mean
    )

    return SplitIndexResult(
        index=index_value,
        formal_verification_success_rate=formal_val,
        had_unparseable_values=had_unparseable,
        missing_metrics=missing_metrics,
    )


def get_quality_index_section(
    *, workflows_report: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    warnings: List[str] = []

    workflows_result = (
        compute_quality_index_for_report(workflows_report)
        if workflows_report is not None
        else None
    )

    if workflows_result is None:
        warnings.append(WARNING_MISSING_REPORT)

    if (
        workflows_result is not None
        and workflows_result.formal_verification_success_rate
        < FORMAL_VERIFICATION_WARNING_THRESHOLD
    ):
        warnings.append(WARNING_LOW_FORMAL)

    if workflows_result is not None and workflows_result.had_unparseable_values:
        warnings.append(WARNING_UNPARSEABLE_AS_ZERO)

    if workflows_result is not None and workflows_result.missing_metrics:
        warnings.append(_warning_missing_metrics(workflows_result.missing_metrics))

    workflows_index = workflows_result.index if workflows_result is not None else None
    info = f"workflows={_fmt(workflows_index)}"
    total_index = workflows_index or 0.0

    return {
        "index": QUALITY_INDEX_SCALE * total_index / QUALITY_INDEX_MAX_SUM,
        "info": info,
        "WARNING": warnings,
    }


def _fmt(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.6f}"


def save_quality_index_json(
    *, run_dir: str, workflows_report: Optional[Dict[str, Any]]
) -> None:
    run_dir_path = Path(run_dir)
    out_path = run_dir_path / "quality_index.json"
    section = get_quality_index_section(workflows_report=workflows_report)
    write_json(out_path, section)

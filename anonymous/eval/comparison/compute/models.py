import abc
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from anonymous.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    ComparisonSummary,
)


def truncate_text(text: str, max_chars: int = 200) -> str:
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


@dataclass
class RunData:
    dataset1: Dict[str, Any]
    dataset2: Dict[str, Any]
    report1: Dict[str, Any]
    report2: Dict[str, Any]


@dataclass(kw_only=True)
class Comparison(abc.ABC):
    name: str
    alert_flag: bool = False
    warning_flag: bool = False

    def to_dict(self):
        return asdict(self)

    @abc.abstractmethod
    def get_text_presentation(self, minimize: bool):
        raise NotImplementedError("Abstract method")


@dataclass
class PairwiseScalarComparison(Comparison):
    p_value: Optional[float]
    metrics_value: float
    score_scale: str = "[-1..1]"

    def get_text_presentation(self, minimize: bool):
        return (
            f"{self.name}:\n    {self.metrics_value:.3f} "
            f"(p_value={(self.p_value if self.p_value is not None else float('nan')):.3f})"
        )


@dataclass
class ScalarMetricsComparison(Comparison):
    p_value: Optional[float]
    metrics_value1: float
    metrics_value2: float

    def get_text_presentation(self, minimize: bool):
        return (
            f"{self.name}:\n    {self.metrics_value1:.3f} vs {self.metrics_value2:.3f} "
            f"(p_value={(self.p_value if self.p_value is not None else float('nan')):.3f})"
        )


@dataclass
class ToolMetricsComparison(ScalarMetricsComparison):
    total_count1: int
    total_count2: int

    def get_text_presentation(self, minimize: bool):
        return (
            "Tool "
            + super().get_text_presentation(minimize)
            + f"\n  Number of calls:\n    {self.total_count1} vs {self.total_count2}"
        )


@dataclass
class JudgeMetricsComparison(Comparison):
    text_cmp: ComparisonSummary
    score_comparison: Comparison

    def get_text_presentation(self, minimize: bool):
        if minimize:
            return (
                f"{self.name}:"
                + "\n"
                + self.score_comparison.get_text_presentation(minimize)
            )

        review = truncate_text(self.text_cmp.review)
        return (
            f"{self.name}:"
            + f"\n    Comparison summary: {review}"
            + "\n"
            + self.score_comparison.get_text_presentation(minimize)
        )


@dataclass(kw_only=True)
class SetupComparison(Comparison):
    difference: str
    name: str = "setups"

    def get_text_presentation(self, minimize: bool):
        diff_message = truncate_text(self.difference) if len(self.difference) else "-"
        return f"Comparison of run setups:\n    {diff_message}"


@dataclass(kw_only=True)
class TerminationReasonsComparison(Comparison):
    common: Dict[str, int]
    diff1: Dict[str, int]
    diff2: Dict[str, int]

    def get_text_presentation(self, minimize: bool):
        common_reasons = self.get_problem_list_str(self.common)
        diff1_reasons = self.get_problem_list_str(self.diff1)
        diff2_reasons = self.get_problem_list_str(self.diff2)
        return (
            f"{self.name}:"
            + f"\nCommon reasons:\n    {common_reasons}"
            + f"\nUnique for run1:\n    {diff1_reasons}"
            + f"\nUnique for run2:\n    {diff2_reasons}"
        )

    @staticmethod
    def get_problem_list_str(problems: Dict[str, int]) -> str:
        if len(problems) == 0:
            return "None"
        return "\n    ".join(
            map(lambda x: f"({x[1]}) {truncate_text(x[0])}", problems.items())
        )


@dataclass
class AlertInfo:
    warnings: List[str]
    alerts: List[str]

from anonymous.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from anonymous.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    PairwiseLlmMetric,
)


class TestMaintainabilityMetric(LlmMetric, PairwiseLlmMetric):
    @staticmethod
    def get_name():
        return "TestMaintainability"

    @property
    def _focus_on_end_result(self) -> bool:
        return True

    @property
    def _pairwise_specific_instruction(self) -> str:
        return """\
Focus on the maintainability of the produced test (end result only).
Compare structure and readability: naming, organization, duplication vs helpers, comments, and overall cleanliness.
Prefer concrete evidence (e.g., repeated blocks, unclear assertions, brittle setup) and highlight the biggest maintainability pain points.
"""

    @property
    def _single_run_specific_instruction(self) -> str:
        return """\
Assess the maintainability of the produced test (end result only).
Consider structure and readability: naming, organization, duplication vs helpers, comments, and overall cleanliness.
Prefer concrete evidence (e.g., repeated blocks, unclear assertions, brittle setup) and highlight the biggest maintainability pain points.
"""

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return """\
Score should be a number from [0, 0.5, 1], where:
- 0 means hardly maintainable,
- 0.5 means tolerable,
- 1 means nicely structured and easily maintainable.
"""

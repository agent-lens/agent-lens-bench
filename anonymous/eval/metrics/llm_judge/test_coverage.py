from anonymous.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from anonymous.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    PairwiseLlmMetric,
)


class TestSemanticCoverageMetric(LlmMetric, PairwiseLlmMetric):
    @staticmethod
    def get_name():
        return "TestSemanticCoverage"

    @property
    def _focus_on_end_result(self) -> bool:
        return True

    @property
    def _pairwise_specific_instruction(self) -> str:
        return """\
Focus on semantic/exhaustive coverage of the produced test (end result only).
Compare whether the tests cover meaningful requirements and code paths: happy path + key edge cases, realistic scenarios, and important branches.
Call out missing critical cases or overly narrow/unrealistic coverage, and state which agent is better on exhaustiveness.
"""

    @property
    def _single_run_specific_instruction(self) -> str:
        return """\
Assess semantic/exhaustive coverage of the produced test (end result only).
Evaluate whether the test covers meaningful requirements and code paths: happy path + key edge cases, realistic scenarios, and important branches.
Call out missing critical cases or overly narrow/unrealistic coverage.
"""

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return """\
Score should be a number from [0, 0.5, 1], where:
- 0 means rather pointless (paths too narrow/unrealistic),
- 0.5 means covers most meaningful behavior but misses key edge cases,
- 1 means exhaustive.
"""

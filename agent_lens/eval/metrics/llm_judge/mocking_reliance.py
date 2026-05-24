from agent_lens.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from agent_lens.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    PairwiseLlmMetric,
)


class RelianceOnMockingMetric(LlmMetric, PairwiseLlmMetric):
    @staticmethod
    def get_name():
        return "RelianceOnMocking"

    @property
    def _focus_on_end_result(self) -> bool:
        return True

    @property
    def _pairwise_specific_instruction(self) -> str:
        return """\
Focus on reliance on mocking in the final produced test (end result only).
Compare whether each agent mocks wisely vs over-mocks: does the test still validate realistic behavior, or does it replace testable logic with mocks.
Be critical and specific: mention what is mocked and why it is (or isn't) justified, especially for internal logic vs external dependencies.
"""

    @property
    def _single_run_specific_instruction(self) -> str:
        return """\
Assess reliance on mocking in the final produced test (end result only).
Evaluate whether the test mocks wisely vs over-mocks: does it still validate realistic behavior, or does it replace testable logic with mocks.
Be critical and specific: mention what is mocked and why it is (or isn't) justified, especially for internal logic vs external dependencies.
"""

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return """\
Score should be a number from [0, 0.5, 1], where:
- 0 means the test over-mocks and does not really test real behaviors,
- 0.5 is intermediate,
- 1 means it mocks wisely (mostly external deps; avoids replacing internal logic).
"""

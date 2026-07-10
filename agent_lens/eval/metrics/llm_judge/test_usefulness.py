from agent_lens.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from agent_lens.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    PairwiseLlmMetric,
)

TEST_USEFULNESS_SINGLE_RUN_INSTRUCTION = """\
Assess usefulness/value of the produced test for a real developer (end result only).
Consider practical value: realistic behavior coverage, appropriate detail and assertions, reasonable style, maintainability, and sensible mocking.
Highlight concrete problems (weird elements, flaky/brittle setup, unclear assertions) and how directly usable the test is.
"""

TEST_USEFULNESS_SINGLE_RUN_SCORING_GUIDELINES = """\
Score should be a number from [0, 0.5, 1], where:
- 0 means rather useless (needs major refactoring / not maintainable / unrealistic behavior),
- 0.5 means useful but needs minor adjustments,
- 1 means has real value.
"""


class TestUsefulnessMetric(LlmMetric, PairwiseLlmMetric):
    @staticmethod
    def get_name():
        return "TestUsefulness"

    @property
    def _focus_on_end_result(self) -> bool:
        return True

    @property
    def _pairwise_specific_instruction(self) -> str:
        return """\
Focus on usefulness/value of the produced test for a real developer (end result only).
Compare practical value: does it test realistic behavior, have appropriate detail and assertions, reasonable style, maintainability, and sensible mocking.
Highlight concrete problems (weird elements, flaky/brittle setup, unclear assertions) and state which agent's test is more directly usable.
"""

    @property
    def _single_run_specific_instruction(self) -> str:
        return TEST_USEFULNESS_SINGLE_RUN_INSTRUCTION

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return TEST_USEFULNESS_SINGLE_RUN_SCORING_GUIDELINES

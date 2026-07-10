from agent_lens.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from agent_lens.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    PairwiseLlmMetric,
)

END_RESULT_SINGLE_RUN_INSTRUCTION = """\
Assess the quality of the end result produced by the agent in response to the user's request.
Focus on completeness and fitness for purpose; assess the end state, not the process.

Evaluate against the user's explicit request:
- Are all requirements met? If partially correct, name what is missing or wrong.
- If the final result introduces new problems (regressions, breaking changes, incorrect claims, contradictions), treat that as a quality issue.
- If the request is ambiguous, evaluate whether agent's assumptions are reasonable and whether they lead to a satisfactory end state (note the assumptions).

In your review, be specific and actionable: reference what works, what doesn't, and why.
"""

END_RESULT_SINGLE_RUN_SCORING_GUIDELINES = """\
Score should be a number from [0, 0.5, 1], where:
- 0 means the result is unsatisfactory (<50% of requirements met or major issues),
- 0.5 means partially satisfactory (50% to 90% met, or works but with notable issues),
- 1 means satisfactory (>90% met, fit for purpose).
"""


class EndResultMetric(LlmMetric, PairwiseLlmMetric):
    @staticmethod
    def get_name():
        return "EndResult"

    @property
    def _focus_on_end_result(self) -> bool:
        return True

    @property
    def _pairwise_specific_instruction(self) -> str:
        return """\
Focus on the end result only: compare the final outcome Agent 1 delivered vs Agent 2, regardless of their process.
Assess completeness and fitness for purpose w.r.t. the user's request (this can be code, an overview, an answer, a plan, a report, etc.).
"""

    @property
    def _single_run_specific_instruction(self) -> str:
        return END_RESULT_SINGLE_RUN_INSTRUCTION

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return END_RESULT_SINGLE_RUN_SCORING_GUIDELINES

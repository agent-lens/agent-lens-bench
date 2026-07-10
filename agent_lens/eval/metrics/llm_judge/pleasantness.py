from agent_lens.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from agent_lens.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    PairwiseLlmMetric,
)

PLEASANTNESS_SINGLE_RUN_INSTRUCTION = """\
Focus on pleasantness of the interaction only.
Assess clarity, accuracy, conciseness, helpfulness, and whether the interaction feels productive and non-disruptive.
Also assess communicative style and operational hygiene (e.g., unnecessary steps, confusing responses, ignoring user constraints) as they affect user experience.
"""

PLEASANTNESS_SINGLE_RUN_SCORING_GUIDELINES = """\
Score should be a number from [0, 0.5, 1], where:
- 0 means the interaction is rather unpleasant,
- 0.5 means tolerable,
- 1 means actually pleasant.
"""


class PleasantnessMetric(LlmMetric, PairwiseLlmMetric):
    @staticmethod
    def get_name():
        return "Pleasantness"

    @property
    def _pairwise_specific_instruction(self) -> str:
        return """\
Focus on pleasantness of the interaction only.
Compare Agent 1 vs Agent 2 on clarity, accuracy, conciseness, helpfulness, and whether the interaction feels productive and non-disruptive.
"""

    @property
    def _single_run_specific_instruction(self) -> str:
        return PLEASANTNESS_SINGLE_RUN_INSTRUCTION

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return PLEASANTNESS_SINGLE_RUN_SCORING_GUIDELINES

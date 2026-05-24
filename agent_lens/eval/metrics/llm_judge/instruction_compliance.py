from agent_lens.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from agent_lens.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    PairwiseLlmMetric,
)


class InstructionComplianceMetric(LlmMetric, PairwiseLlmMetric):
    @staticmethod
    def get_name():
        return "InstructionCompliance"

    @property
    def _pairwise_specific_instruction(self) -> str:
        return """\
Focus on operational compliance only (not end-result quality).
Extract the user's explicit rules, steps, and meta-instructions (e.g., "be concise", "don't use X", "do A then B").
Compare Agent 1 vs Agent 2 on each instruction: whether it was followed, skipped, misinterpreted, or done out of order.
"""

    @property
    def _single_run_specific_instruction(self) -> str:
        return """\
Assess the operational compliance of the agent with the steps requested by the user.
Extract every rule, step, and meta-instruction from the user. For each item, evaluate whether the agent followed it, skipped it, misinterpreted it, or did it out of order.
Focus on compliance only; do not assess end-result quality.

Examples:
1) If the user only said "fix the bug" and the agent attempted it, that can be compliant even if it fails.
2) If the user specified multiple steps and the agent skipped or reformatted one, report it.
3) If instructions contradict, report it and evaluate how the agent handled the conflict.
4) Meta-instructions include constraints like "be concise" or "don't use X".
"""

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return """\
Score should be a number from [0, 0.5, 1], where:
- 0 means non-compliant (<50% of required steps followed),
- 0.5 means partially compliant (50% to 90%),
- 1 means compliant (>90%).
"""

from agent_lens.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from agent_lens.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    PairwiseLlmMetric,
)


class ToolCallsMetric(LlmMetric, PairwiseLlmMetric):
    @staticmethod
    def get_name():
        return "ToolCalls"

    @property
    def _pairwise_specific_instruction(self) -> str:
        return """\
Focus on tool calling performance only.
Mainly emphasize concrete tool-call issues (technical difficulties, repeated errors, missing/incorrect args, pointless calls) and cite tool names and error messages from the trajectories. Mention tools that suffer from wrong calling or technical problems.
Mention specific errors with tools so that we can see and debug them easily.
"""

    @property
    def _single_run_specific_instruction(self) -> str:
        return """\
Assess the agent's tool calling performance.
Cover tool choice/decision to call, argument correctness, tool call success/failure, recovery from tool errors, and overall efficiency vs futile tool usage.

Emphasize concrete, harness-usable evidence:
- Cite tool names and error messages from the trajectory.
- If errors repeat, treat it as a pattern: describe the repeating failure mode and add a brief diagnosis of why the agent might fail this way (missing context, ambiguous API usage, confusing tool contract, etc.).
- Call out likely harness issues explicitly when evidence suggests it.
"""

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return """\
Score should be a number from [0, 0.5, 1], where:
- 0 means tool calling is ineffective,
- 0.5 means tolerable,
- 1 means actually good.
"""

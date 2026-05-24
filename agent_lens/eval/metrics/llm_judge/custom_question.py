from typing import Dict

from agent_lens.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric


class CustomQuestionMetric(LlmMetric):
    """A generic LLM-judge metric that asks a user-provided question."""

    def __init__(self, config_dict: Dict, **kwargs) -> None:
        super().__init__(config_dict, **kwargs)
        self._question: str = config_dict.get("custom_question", "")

    @staticmethod
    def get_name() -> str:
        return "CustomQuestion"

    @property
    def _single_run_aggregation_specific_instruction(self) -> str:
        return f"Here is a question directly from our end-user you should answer precisely:\n{self._question}"

    @property
    def _single_run_specific_instruction(self) -> str:
        return f"""\
Answer the following question based on the trajectory and supporting data:

Question:
{self._question}
"""

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return """\
Scoring policy:
- Score must be one of [0, 0.5, 1].
- 1 means the agent's behavior fully satisfies the question and is clearly correct.
- 0.5 means partially satisfactory or uncertain.
- 0 means unsatisfactory or clearly incorrect.
"""

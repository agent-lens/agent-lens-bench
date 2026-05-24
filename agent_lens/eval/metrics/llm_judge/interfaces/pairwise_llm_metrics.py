import abc
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from agent_lens.eval.metrics.llm_judge.interfaces.llm_api import LlmApi
from agent_lens.eval.metrics.llm_judge.parsing.tags import (
    extract_section,
    parse_alert_flag,
)
from agent_lens.eval.metrics.llm_judge.common.prompt_builders import (
    ALERT_FLAG_SEPARATOR,
    COMPARISON_SEPARATOR,
    PAIRWISE_SCORE_SEPARATOR,
    PROMPT_RESPONSE_SEPARATOR,
    build_pairwise_prompt,
    build_trajectory_comparisons_summary_prompt,
)


@dataclass
class TrajectoryBasedComparison:
    key: str
    comparison_text: str
    score: Optional[float]
    dialogue: str


@dataclass
class ComparisonSummary:
    review: str
    chats_reviewed: List[str]
    judge_alert: bool = False


class PairwiseLlmMetric(LlmApi, abc.ABC):
    """Base class for pairwise LLM metrics. Subclasses implement `_pairwise_specific_instruction`.

    Pass `ordered_keys` to the constructor, then call `compare(dataset1, dataset2)`.
    """

    def __init__(
        self, config_dict: Dict, api_key: str, ordered_keys: List[str] = (), **kwargs
    ) -> None:
        super().__init__(config_dict, api_key, **kwargs)
        self.ordered_keys = list(ordered_keys)

    @property
    @abc.abstractmethod
    def _pairwise_specific_instruction(self) -> str:
        """Metric-specific instruction inserted into the common pairwise prompt."""

    def compare(
        self, dataset1: Dict, dataset2: Dict
    ) -> Tuple[ComparisonSummary, str, List[TrajectoryBasedComparison], Dict[str, str]]:
        prompts: List[str] = []
        for key in self.ordered_keys:
            p1 = dataset1.get(key)
            p2 = dataset2.get(key)
            if p1 is None or p2 is None:
                raise KeyError(
                    f"Missing key '{key}' in dataset1/dataset2 (got: {p1 is not None}/{p2 is not None})"
                )
            prompts.append(
                build_pairwise_prompt(
                    point1=p1,
                    point2=p2,
                    metric_name=self.get_name(),
                    pairwise_specific_instruction=self._pairwise_specific_instruction,
                )
            )

        dialogues = self.get_llm_responses(prompts)
        per_task_dialogues: Dict[str, str] = {
            key: dialogue for key, dialogue in zip(self.ordered_keys, dialogues)
        }
        per_task_comparisons = [
            self._parse_per_task(dialogue, key)
            for key, dialogue in zip(self.ordered_keys, dialogues)
        ]

        comparisons_listing = self._build_comparisons_text(per_task_comparisons)
        summary_prompt = build_trajectory_comparisons_summary_prompt(
            comparisons_listing,
            self.get_name(),
            self.config_dict,
        )
        summary_dialogue = self.get_llm_response(summary_prompt)
        return (
            self._parse_summary(summary_dialogue),
            summary_dialogue,
            per_task_comparisons,
            per_task_dialogues,
        )

    @staticmethod
    def _build_comparisons_text(comps: List[TrajectoryBasedComparison]) -> str:
        lines: List[str] = []
        for i, c in enumerate(comps, start=1):
            lines.append(f"Comparison: C{i} ({c.key})")
            if c.comparison_text:
                lines.append(c.comparison_text)
            if c.score is not None:
                lines.append(f"Score given: {int(c.score * 5)}")
            lines.append("")
        return (
            "\n".join(lines).strip()
            + "\n\n(Negative score favours Agent 1, positive -- Agent 2. Scores are from -5 to 5.)"
        )

    @staticmethod
    def _parse_pairwise_score_int(content: str) -> Optional[int]:
        if content.count(PAIRWISE_SCORE_SEPARATOR) == 0:
            score_start = None
        elif content.count(PAIRWISE_SCORE_SEPARATOR) == 1:
            score_start = content.find(PAIRWISE_SCORE_SEPARATOR) + len(
                PAIRWISE_SCORE_SEPARATOR
            )
        elif content.count(f"\n{PAIRWISE_SCORE_SEPARATOR}") > 0:
            score_start = content.find(f"\n{PAIRWISE_SCORE_SEPARATOR}") + len(
                f"\n{PAIRWISE_SCORE_SEPARATOR}"
            )
        else:
            score_start = content.find(PAIRWISE_SCORE_SEPARATOR) + len(
                PAIRWISE_SCORE_SEPARATOR
            )

        if score_start is None:
            return None

        raw_after = content[score_start:].strip()
        if not raw_after:
            return None

        first_token = raw_after.split(None, 1)[0].split("<", 1)[0].strip()
        try:
            return int(first_token)
        except ValueError:
            return None

    def _parse_per_task(self, dialogue: str, key: str) -> TrajectoryBasedComparison:
        content = dialogue.split(PROMPT_RESPONSE_SEPARATOR)[-1]

        comp_start = None
        if COMPARISON_SEPARATOR in content:
            comp_start = content.find(COMPARISON_SEPARATOR) + len(COMPARISON_SEPARATOR)

        score_int = self._parse_pairwise_score_int(content)
        score_tag_start = content.find(PAIRWISE_SCORE_SEPARATOR)

        comparison_text = ""
        if comp_start is not None:
            comp_end = score_tag_start if score_tag_start != -1 else len(content)
            comparison_text = content[comp_start:comp_end].strip()

        score: Optional[float] = None
        if score_int is not None and -5 <= score_int <= 5:
            score = score_int / 5

        return TrajectoryBasedComparison(
            key=key,
            comparison_text=comparison_text,
            score=score,
            dialogue=dialogue,
        )

    def _parse_summary(self, response: str) -> ComparisonSummary:
        content = response.split(PROMPT_RESPONSE_SEPARATOR)[-1]
        review_text = extract_section(
            content, start_tag=COMPARISON_SEPARATOR, end_tag=ALERT_FLAG_SEPARATOR
        )
        judge_alert_flag = parse_alert_flag(content, ALERT_FLAG_SEPARATOR)
        return ComparisonSummary(
            review=review_text,
            chats_reviewed=[f"{i + 1}: {k}" for i, k in enumerate(self.ordered_keys)],
            judge_alert=judge_alert_flag,
        )

import abc
import logging
import random
import re
from typing import Any, Dict, Mapping, Optional, Tuple

from agent_lens.eval.metrics.llm_judge.common.prompt_builders import (
    PROMPT_RESPONSE_SEPARATOR,
    REVIEW_SEPARATOR,
    SCORE_SEPARATOR,
    build_single_run_prompt,
    build_single_run_summary_prompt,
)
from agent_lens.eval.data_framework.field_names import FieldNames
from agent_lens.eval.metrics.analytics.get_analytics import (
    get_basic_stats_chat_level,
)
from agent_lens.eval.metrics.llm_judge.interfaces.llm_api import LlmApi

LOG = logging.getLogger(__name__)
MAX_LLM_REVIEWED_POOL_SIZE = 50
SCORE_TOKEN_TO_VALUE = {
    "0": 0.0,
    "0.0": 0.0,
    "1": 1.0,
    "1.0": 1.0,
    "0.5": 0.5,
}
SCORE_TOKEN_RE = re.compile(r"(?<!\d)(?:0(?:\.0|\.5)?|1(?:\.0)?)(?!\d)")


class LlmMetric(LlmApi, abc.ABC):
    def __init__(self, config_dict: Dict, api_key: str, **kwargs) -> None:
        super().__init__(config_dict, api_key, **kwargs)
        self.data: Dict[str, Dict[str, Any]] = {}

    def select_points(self, dataset: Mapping[str, dict[str, Any]]) -> None:
        """Select a deterministic pseudo-random subset of points.

        Deterministic across runs: selection depends only on dataset keys + config.
        """

        keys = sorted(dataset.keys())
        rng = random.Random(42)
        rng.shuffle(keys)

        chosen = keys[: min(MAX_LLM_REVIEWED_POOL_SIZE, len(keys))]
        self.data = {k: dataset[k] for k in chosen}

    def compute_single_run_reviews(self) -> None:
        """Computes LLM metrics for a list of points.
        Adds result in-place.
        """
        prompts = {
            idx: build_single_run_prompt(
                point=point,
                metric_name=self.get_name(),
                focus_on_end_result=self._focus_on_end_result,
                single_run_specific_instruction=self._single_run_specific_instruction,
                single_run_scoring_guidelines=self._single_run_scoring_guidelines,
            )
            for idx, point in self.data.items()
        }
        prompt_ids, prompt_texts = list(prompts.keys()), list(prompts.values())
        dialogues = self.get_llm_responses([p for p in prompt_texts])
        for idx, dialogue in zip(prompt_ids, dialogues):
            review_text, score = self._parse_single_run_response(dialogue)
            self.data[idx][self.get_name()] = {
                FieldNames.JUDGE_SCORE: score,
                FieldNames.JUDGE_REVIEW: review_text,
                FieldNames.JUDGE_DIALOGUE: dialogue,
            }

    @property
    def _focus_on_end_result(self) -> bool:
        return False

    @property
    def _single_run_aggregation_specific_instruction(self) -> str:
        """Metric-specific instruction appended to the aggregation prompt."""
        return ""

    @property
    @abc.abstractmethod
    def _single_run_specific_instruction(self) -> str:
        """Metric-specific instruction inserted into the single-run prompt."""

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return """\
Score should be a number from [0, 0.5, 1], where:
- 0 means poor performance,
- 0.5 means tolerable performance,
- 1 means good performance.
"""

    @staticmethod
    def _parse_score_token(raw_score: str) -> Optional[float]:
        token_match = SCORE_TOKEN_RE.search(raw_score)
        if token_match is None:
            return None

        return SCORE_TOKEN_TO_VALUE.get(token_match.group(0))

    @classmethod
    def _parse_single_run_response(cls, dialogue: str) -> Tuple[str, Optional[float]]:
        response = dialogue.split(PROMPT_RESPONSE_SEPARATOR)[-1]

        review_idx = response.find(REVIEW_SEPARATOR)
        score_idx = response.rfind(SCORE_SEPARATOR)

        if score_idx == -1:
            excerpt = response.strip().replace("\n", " ")
            max_len = 500
            if len(excerpt) > max_len:
                excerpt = excerpt[:max_len] + "…"
            LOG.warning(
                "Could not parse LLM judge response (no <Score> tag); returning None score. Excerpt: %s",
                excerpt,
            )
            return response.strip(), None

        # Prefer the explicit <Review> tag, but tolerate malformed outputs.
        if 0 <= review_idx < score_idx:
            review_text = response[
                review_idx + len(REVIEW_SEPARATOR) : score_idx
            ].strip()
        else:
            review_text = response[:score_idx].strip()

        raw_score = response[score_idx + len(SCORE_SEPARATOR) :].strip()
        score = cls._parse_score_token(raw_score)
        if score is None:
            excerpt = raw_score.strip().replace("\n", " ")
            max_len = 200
            if len(excerpt) > max_len:
                excerpt = excerpt[:max_len] + "…"
            LOG.warning(
                "Could not parse LLM judge score token; returning None score. Raw: %s",
                excerpt,
            )

        return review_text, score

    def _compose_review_for_aggregation(self, p: Dict) -> str:
        return str(p[self.get_name()].get(FieldNames.JUDGE_REVIEW) or "")

    def single_run_aggregate(self) -> Dict:
        parsed_scores = [
            p[self.get_name()][FieldNames.JUDGE_SCORE]
            for p in self.data.values()
            if p[self.get_name()][FieldNames.JUDGE_SCORE] is not None
        ]
        reviews = [self._compose_review_for_aggregation(p) for p in self.data.values()]
        aggregation_prompt = build_single_run_summary_prompt(
            per_point_analysis=reviews,
            metric_name=self.get_name(),
            single_run_aggregation_specific_instruction=self._single_run_aggregation_specific_instruction,
            config_dict=self.config_dict,
        )
        llm_review = (
            self.get_llm_response(aggregation_prompt)
            .split(PROMPT_RESPONSE_SEPARATOR)[-1]
            .strip()
        )

        aggregated = {
            self.get_name(): {
                "score quantiles": get_basic_stats_chat_level(parsed_scores),
                "score mean": None
                if len(parsed_scores) == 0
                else round(sum(parsed_scores) / len(parsed_scores), 2),
                "llm review": llm_review,
                "chats reviewed": [
                    f"{i}: {idx}" for i, idx in enumerate(self.data, start=1)
                ],
            }
        }
        return aggregated

import logging
import re
from typing import Optional, Tuple

from agent_lens.eval.metrics.llm_judge.common.prompts.instructions import (
    ALERT_FLAG_SEPARATOR,
    COMPARISON_SEPARATOR,
    PAIRWISE_SCORE_SEPARATOR,
    PROMPT_RESPONSE_SEPARATOR,
    REVIEW_SEPARATOR,
    SCORE_SEPARATOR,
)
from agent_lens.eval.metrics.llm_judge.parsing.tags import (
    extract_section,
    parse_alert_flag,
)

LOG = logging.getLogger(__name__)

SCORE_TOKEN_TO_VALUE = {
    "0": 0.0,
    "0.0": 0.0,
    "1": 1.0,
    "1.0": 1.0,
    "0.5": 0.5,
}
SCORE_TOKEN_RE = re.compile(r"(?<!\d)(?:0(?:\.0|\.5)?|1(?:\.0)?)(?!\d)")


def parse_score_token(raw_score: str) -> Optional[float]:
    token_match = SCORE_TOKEN_RE.search(raw_score)
    if token_match is None:
        return None

    return SCORE_TOKEN_TO_VALUE.get(token_match.group(0))


def parse_single_run_response(dialogue: str) -> Tuple[str, Optional[float]]:
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
    score = parse_score_token(raw_score)
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


def parse_pairwise_score_int(content: str) -> Optional[int]:
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


def parse_comparison_summary(response: str) -> Tuple[str, bool]:
    content = response.split(PROMPT_RESPONSE_SEPARATOR)[-1]
    review_text = extract_section(
        content, start_tag=COMPARISON_SEPARATOR, end_tag=ALERT_FLAG_SEPARATOR
    )
    judge_alert_flag = parse_alert_flag(content, ALERT_FLAG_SEPARATOR)
    return review_text, judge_alert_flag

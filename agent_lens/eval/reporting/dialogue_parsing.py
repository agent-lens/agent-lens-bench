"""Helpers for extracting structured parts from LLM dialogues."""

from agent_lens.eval.metrics.llm_judge.common.prompts.instructions import (
    COMPARISON_SEPARATOR,
    PAIRWISE_SCORE_SEPARATOR,
    PROMPT_RESPONSE_SEPARATOR,
)


def extract_final_response(
    text: str, *, separator: str = PROMPT_RESPONSE_SEPARATOR
) -> str:
    if not text:
        return ""
    return text.split(separator)[-1].strip()


def extract_comparison_text(per_task_dialogue: str) -> str:
    """Extract `{COMPARISON_SEPARATOR}` section from a full per-task judge dialogue.

    If a `{PAIRWISE_SCORE_SEPARATOR}` section is present, also append a short
    "Judge's score: <int>" line at the end of the extracted comparison text.
    """

    if not per_task_dialogue:
        return ""

    content = extract_final_response(per_task_dialogue)
    if COMPARISON_SEPARATOR not in content:
        return content.strip()

    start = content.find(COMPARISON_SEPARATOR) + len(COMPARISON_SEPARATOR)
    score_tag_pos = content.find(PAIRWISE_SCORE_SEPARATOR, start)
    end = score_tag_pos if score_tag_pos != -1 else len(content)
    extracted = content[start:end].strip()

    if score_tag_pos == -1:
        return extracted

    after = content[score_tag_pos + len(PAIRWISE_SCORE_SEPARATOR) :].strip()
    token = after.split(None, 1)[0] if after else ""
    token = token.split("<", 1)[0].strip()  # tolerate optional closing tag

    try:
        score_int = int(token)
    except ValueError:
        return extracted

    return f"{extracted}\n\nJudge's score (from [-5, 5]): {score_int}"

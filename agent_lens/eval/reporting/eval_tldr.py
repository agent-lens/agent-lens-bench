import json
from typing import Any, Dict, Mapping

from agent_lens.eval.metrics.llm_judge.interfaces.llm_api import LlmApi
from agent_lens.eval.metrics.llm_judge.common.review_style_user import (
    get_answer_language_instruction,
    get_user_specific_prompt_instruction,
)
from agent_lens.eval.metrics.llm_judge.common.prompts.instructions import (
    PROMPT_RESPONSE_SEPARATOR,
    SYSTEM_PROMPT,
)


class EvalTldr(LlmApi):
    """LLM-based TLDR for a single-run eval report."""

    def __init__(self, config_dict: Dict, **kwargs) -> None:
        super().__init__(config_dict, **kwargs)

    @staticmethod
    def get_name() -> str:
        return "EvalTldr"

    def get_prompt(self, report: Mapping[str, Any]) -> str:
        pretty_payload = json.dumps(report, ensure_ascii=False, indent=2)
        answer_language_instruction = get_answer_language_instruction(self.config_dict)
        user_specific_instruction = get_user_specific_prompt_instruction(
            self.config_dict
        )

        return f"""
{SYSTEM_PROMPT}

We have run one IDE agent on our benchmark and computed aggregated metrics.

<Instruction>
You are writing a 3-sentence TL;DR for a busy CEO.
Use text reviews as the primary evidence: the main recurring issues, delivery risks, and strengths.
Use numbers only when they clarify an operational point (e.g., formal verification rate, frequent timeouts, clearly low tool success rates). Judge scores may appear in the data, but they are not inherently meaningful to the reader; prefer plain-language conclusions backed by review text.
Do not use internal benchmark jargon or raw report labels: no Rk references, no "high/medium/low case" wording, no "judge score", no section titles copied verbatim.
Abstract away from low-level implementation details (method/class/endpoint names). Name issues as categories: incomplete verification, contract/behavior mismatch, scope drift, repo left non-green, unstable tooling, etc..
Start directly with substance (no meta-intros).
</Instruction>

Here is the eval report:
{pretty_payload}

Write a 3-sentence TL;DR in a professional, calm tone that is analytically precise and well-calibrated. Write it for a busy CEO. Do not generalize, infer, add conclusions or make recommendations; only restructure the given report into the requested style.
{answer_language_instruction}
{user_specific_instruction}
"""

    def get_tldr(self, report: Mapping[str, Any]) -> str:
        prompt = self.get_prompt(report)
        response = self.get_llm_response(prompt)
        return response.split(PROMPT_RESPONSE_SEPARATOR)[-1].strip()

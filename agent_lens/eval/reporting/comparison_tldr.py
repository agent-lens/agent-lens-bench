from typing import Dict, List

from agent_lens.eval.comparison.compute.models import Comparison
from agent_lens.eval.metrics.llm_judge.interfaces.llm_api import LlmApi
from agent_lens.eval.metrics.llm_judge.common.review_style_user import (
    get_answer_language_instruction,
    get_user_specific_prompt_instruction,
)
from agent_lens.eval.metrics.llm_judge.common.prompts.instructions import (
    PROMPT_RESPONSE_SEPARATOR,
    SYSTEM_PROMPT,
)


class ComparisonTldr(LlmApi):
    def __init__(self, config_dict: Dict, **kwargs) -> None:
        super().__init__(config_dict, **kwargs)

    @staticmethod
    def get_name() -> str:
        return "Tldr"

    def get_prompt(self, comparisons: List[Comparison]) -> str:
        answer_language_instruction = get_answer_language_instruction(self.config_dict)
        user_specific_instruction = get_user_specific_prompt_instruction(
            self.config_dict
        )
        prompt = f"""
{SYSTEM_PROMPT}

We have run two IDE agents to compare them on our benchmark. Below you can see the resulting comparison for Agent 1 and Agent 2. I will explain some crucial instructions first and then provide the data itself.

<Instruction>
- formal_verification_result is a formal verification based on heuristics that roughly checks for basic evidence of correctness. It is important, but a bit inaccurate. Mention it.
- judge metrics typically consist of a text review and a score for each agent. You should analyze all nuances in these reviews. This is the most important part. It typically gives a nuanced sense of what's going on, and you should convey it in your response. Note: EndResult is a judge metric evaluating the outcome of agent's actions, it's not a "final judgement".
- tool success rates are usually interesting, but typically only a fraction of the whole data is of interest: see what's changed between runs and how it relates to judge reports and other metrics.
- inference metrics should be assessed as a whole and in relation to other metrics. No need to mention if they are similar for both agents.
- termination reasons might be interesting alongside the other metrics. E.g., if one agent sees the task through less often, generates fewer tokens and has five more timeouts, that probably points to issues with an inference server. No need to mention if they are similar for both agents.
- when you use phrases like 'Agent 2 is more prone to ...', you should be clear about the extent to which it happens. Anchor claims in recurrence, practical impact, and p-values when available; express severity in plain language rather than internal labels; avoid qualitative intensifiers without reference. Think: should we be concerned and go check what's wrong, or is it rather just a one-point statistical happenstance?
- do not use internal benchmark jargon or raw report labels: no Ck references, no "high/medium/low case" wording, no "judge score" wording, no section titles copied verbatim.
- when you say something like, 'Agent 1 key risk is X', keep in mind: to what extent is this issue exclusive for Agent 1? Should it meaningfully change how we think about Agent 1 — i.e., should we see him as “someone who does X”? Or is it just that Agent 1 is slightly more prone to this than Agent 2?
- do not say phrases like 'prefer Agent 1 when...' or 'prefer Agent 2 when...'.
</Instruction>

Here is the comparison:
{comparisons}

Please provide a short summary of the comparison, following the rules outlined in the <Instruction> section. It has to be 4 sentences long, professional calm tone, analytically precise and well-calibrated. Write it as if it is a version for our busy CEO.

Examples:
- Avoid vague phrasing like 'this seems noisy' when the data supports a more concrete operational characterization.
- Avoid weak endings like 'this appears more episodic from the reviews'; say what actually recurs and how strongly.
- Avoid low-level repo details that a busy reader does not need unless they are the operational issue itself.

Lead with the core operational risk difference in the first sentence. Avoid meta-introductions. Start directly with the substantive difference, without bureaucratic framing. Prefer concrete wording over abstract nouns.
{answer_language_instruction}
{user_specific_instruction}
"""
        return prompt

    def get_tldr(self, comparisons: List[Comparison]) -> str:
        prompt = self.get_prompt(comparisons)
        response = (
            self.get_llm_response(prompt).split(PROMPT_RESPONSE_SEPARATOR)[-1].strip()
        )
        return response.strip()

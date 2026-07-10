from typing import Any, Dict, List, Mapping

from agent_lens.eval.metrics.llm_judge.common.prompts.instructions import (
    END_OF_PROMPT,
    FOCUS_ON_END_RESULT,
    OUT_FORMAT_REVIEW_SCORE,
    build_data_aggregate_section,
    build_one_run_summary_instructions,
    build_pairwise_instructions,
    build_trajectory_comparisons_summary_instructions,
)
from agent_lens.eval.metrics.llm_judge.common.prompts.data_section import (
    build_pairwise_data_section,
    build_single_run_data_section,
)


def build_single_run_prompt(
    *,
    point: Dict,
    metric_name: str,
    focus_on_end_result: bool,
    single_run_specific_instruction: str,
    single_run_scoring_guidelines: str,
) -> str:
    """Build a prompt for direct single-run judging of one trajectory."""
    prompt = f"""\
{build_single_run_data_section(point)}

{FOCUS_ON_END_RESULT if focus_on_end_result else ""}

<Instructions>
Your task is to act as a precise and analytical judge of an agent-user interaction.
Judge the agent (not the simulator) on the performance dimension '{metric_name}' only.

{single_run_specific_instruction}
</Instructions>

<Scoring>
{single_run_scoring_guidelines}
</Scoring>

{OUT_FORMAT_REVIEW_SCORE}

{END_OF_PROMPT}"""
    return prompt


def build_single_run_summary_prompt(
    *,
    per_point_analysis: List[str],
    single_run_aggregation_specific_instruction: str,
    config_dict: Mapping[str, Any],
) -> str:
    """Build a prompt for aggregating single-run reviews into one summary."""
    prompt = f"""\
  {build_data_aggregate_section(per_point_analysis)}

  {build_one_run_summary_instructions(single_run_aggregation_specific_instruction, config_dict)}
  {END_OF_PROMPT}"""
    return prompt


def build_pairwise_prompt(
    *,
    point1: Dict,
    point2: Dict,
    metric_name: str,
    pairwise_specific_instruction: str,
) -> str:
    """Build a prompt for direct pairwise comparison of two trajectories."""
    prompt = f"""\
{build_pairwise_data_section(point1, point2, metric_name)}

{build_pairwise_instructions(metric_name, pairwise_specific_instruction)}"""
    return prompt


def build_trajectory_comparisons_summary_prompt(
    comparisons_text: str,
    dimension_name: str,
    config_dict: Mapping[str, Any],
) -> str:
    return f"""
<Comparisons>
{comparisons_text}
</Comparisons>

{build_trajectory_comparisons_summary_instructions(dimension_name, config_dict)}"""

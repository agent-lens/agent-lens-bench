from typing import Any, Mapping, Dict

from anonymous.eval.common.trajectory import get_last_simulator_request_messages
from anonymous.eval.data_framework.field_names import FieldNames
from anonymous.eval.metrics.llm_judge.common.judge_data import (
    get_judge_review_or_symmetric_stub,
)
from anonymous.eval.metrics.llm_judge.common.review_style_user import (
    get_answer_language_instruction,
    get_user_specific_prompt_instruction,
)

PROMPT_RESPONSE_SEPARATOR = "\n\n<SEPARATOR BETWEEN PROMPT AND JUDGE ASSESSMENT>\n\n"
REVIEW_SEPARATOR = "<Review>"
SCORE_SEPARATOR = "<Score>"
COMPARISON_SEPARATOR = "<Comparison>"
ALERT_FLAG_SEPARATOR = "<AlertFlag>"
PAIRWISE_SCORE_SEPARATOR = "<PairwiseScore>"

AGENT_ACTIONS_SUMMARY_TAG = "agent_actions_summary"


def build_one_run_summary_instructions(
    metrics_specific_instruction: str,
    config_dict: Mapping[str, Any],
) -> str:
    answer_language_instruction = get_answer_language_instruction(config_dict)
    user_specific_instruction = get_user_specific_prompt_instruction(config_dict)
    return f"""<Task>
Your task is to summarize the main findings from the above reviews into one comprehensive report. Support claims with citations or explicit references. Try to keep as much specifics as possible so that your summary is actionable and useful for debugging. Never hand-wave, be trivial or overgeneralize.

<Examples>
- A good Example, helpful sentence:
    'Recurring workflow failures included not verifying test discovery or execution and claiming success without evidence (e.g., “Test class not found,” missing Gradle output) [R1, R5, R6, R8].'
- A bad Example, verbose, trivial and unhelpful sentence:
    'Overall, outcomes were strongest when the agent grounded tests in actual types and signatures, followed existing test patterns, and applied targeted configuration fixes.'
</Examples>

{metrics_specific_instruction}

INPUT GUIDANCE:
Each Rk may contain structured lines of the form:
`Aspect: ... | Severity: low/medium/high | Evidence: ...`
Treat these Aspect-lines as the main guide for extraction and summarization.
Use the rest of each review as supporting context, especially when Aspect-lines are sparse or need clarification.

YOUR TASK (TWO-STAGE):
Stage 1 — Extract and regroup evidence:
1) Scan all Rk and extract the main findings, using Aspect-lines as the primary guide.
2) Normalize/group them by meaning; keep 1–8 groups total.
3) For each group, list supporting Rk items as proof entries in this format:
   `- [Rk] Severity=low/medium/high | Evidence="..."`
   Sort proof entries within a group by severity: high → medium → low.
4) If Aspect-lines are missing or insufficient, use the surrounding review text to recover the same kind of concrete findings.

Stage 2 — Write the concise summary:
- Write 2 to 6 sentences that summarize the main patterns from Stage 1.
- Do not use vague frequency markers. If you claim frequency, state counts like "in 7 of 15 Rk".
- Support important claims with Rk references.
- Do not propose fixes; characterize findings and recurring patterns.
- Do not refer to Stage 1 groups, proof tables, or internal analysis directly: the end user will only read the Stage 2 summary alone.

DEBUG USEFULNESS:
Make the summary useful for debugging regressions: name recurring failure patterns, likely harness-specific issues, and other concrete signals that would help explain a score.
If you mention a problem, describe it briefly or give an Rk reference right away.

When you refer to specific reviewed tasks, cite them as Rk tokens such as R3 or R10. Avoid the literal form 'Rk' with k; use specific references like R3 or R10 when possible.
Use common terminology and avoid local jargon that would be unclear to a reader outside the benchmark internals.
Use a neutral, third-person, objective tone.
Use line breaks after each sentence (or each semantic section).
{answer_language_instruction}
{user_specific_instruction}

Response consists of two parts:
- <Analysis>: proof regrouping from Stage 1.
- <Summary>: final user-facing summary from Stage 2 only, 2 to 6 sentences long.

OUTPUT FORMAT (STRICT):
<Analysis>
Proof:
AspectGroup: <name>
- [Rk] Severity=low/medium/high | Evidence="..."
...
</Analysis>

<Summary>
[2-6 sentences]
</Summary>
</Task>"""


def build_single_run_prompt(
    *,
    point: Dict,
    metric_name: str,
    focus_on_end_result: bool,
    single_run_specific_instruction: str,
    single_run_scoring_guidelines: str,
) -> str:
    """Build a prompt for direct single-run judging of one raw trajectory."""
    prompt = f"""\
{LlmJudgeInstructions.DATA_COMPUTE_SINGLE(point)}

{LlmJudgeInstructions.FOCUS_ON_END_RESULT if focus_on_end_result else ""}

<Instructions>
Your task is to act as a precise and analytical judge of an agent-user interaction.
Judge the agent (not the simulator) on the performance dimension '{metric_name}' only.

{single_run_specific_instruction}
</Instructions>

<Scoring>
{single_run_scoring_guidelines}
</Scoring>

{LlmJudgeInstructions.OUT_FORMAT_REVIEW_SCORE}

{LlmJudgeInstructions.END_OF_PROMPT}"""
    return prompt


def build_single_run_summary_prompt(
    *,
    per_point_analysis: list[str],
    metric_name: str,
    single_run_aggregation_specific_instruction: str,
    config_dict: Mapping[str, Any],
) -> str:
    """Build a prompt for aggregating single-run reviews into one summary."""
    prompt = f"""\
  {LlmJudgeInstructions.DATA_AGGREGATE(per_point_analysis)}

  {build_one_run_summary_instructions(single_run_aggregation_specific_instruction, config_dict)}
  The performance dimension that these reviews are focused on is named {metric_name}. Focus on that.
  {LlmJudgeInstructions.END_OF_PROMPT}"""
    return prompt


def build_pairwise_prompt(
    *,
    point1: Dict,
    point2: Dict,
    metric_name: str,
    pairwise_specific_instruction: str,
) -> str:
    """Build a prompt for direct pairwise comparison of two raw trajectories."""
    prompt = f"""\
{LlmJudgeInstructions.DATA_COMPUTE_PAIR(point1, point2, metric_name)}

<Instructions>
Your task is to compare Agent 1 and Agent 2 on the SAME task instance with respect to the performance dimension '{metric_name}'.
Use the precomputed reviews (<agent1_review>, <agent2_review>) as the primary input to your comparison to avoid positional bias.
Do NOT introduce new aspects beyond what is present in those reviews, and do NOT revise the individual assessments inside them.
You may consult the raw trajectories ONLY to verify concrete points mentioned in the reviews (e.g., a specific tool call, error message, or key claim), or get the general context.
Stay strictly on the performance dimension '{metric_name}'; ignore unrelated aspects.
Do not propose fixes; only characterize differences with a focus on issues.

Inside the {COMPARISON_SEPARATOR} section, end your text with a short structured breakdown (1-6 lines) so a summarizer can weigh severity:
`Aspect: <free text> | Winner: A1/A2/Tie | Severity (Significance * Degree of Divergence): low/medium/high | Evidence: <specific quote/tool/error>`
Start with aspects where Agent 2 is a winner.
Keep aspects specific to '{metric_name}', and keep evidence concrete and extra short. You should assess the severity of the observed differences accurately. Severity should be determined as the product of the aspect’s Significance and the Degree of Divergence between agents on that aspect. If both agents exhibit the same failure mode, severity should be low even if that failure is critical in absolute terms. Severity is about the delta between agents, not how bad the situation is in absolute terms. For instance, the significance of the aspect 'breaking the repo to a non-recoverable state' is critical. If both agents break the repo, but one breaks one module and another breaks two modules, the divergence is little. So the overall Severity of this difference is low.

The Metric-Specific Instructions are described below. When identifying aspects to compare, use <agent1_review> and <agent2_review> as your primary source. Other aspects are assessed by other judges, don't steal their work.
<Metric-Specific Instructions>
{pairwise_specific_instruction}
</Metric-Specific Instructions>

Scoring guidelines:
Reserve the |4–5| score range for stark contrasts: one agent remains stable and correct, while the other exhibits cascading errors that destabilize the repository, gets stuck, or leaves the result completely unverified. When differences are clear but non-critical, use lower scores. Below is an example specific for Pitfalls and ToolCalls dimension, where the difference is clear, but not critical:
    - Agent N made a clear tool-handling error: after list_dir, which dumped the output to a temporary file, it attempted to read a different path via read_file, receiving the warning “Virtual file does not exist,” which created unnecessary friction. Agent M handled the same “dumped to file” pattern correctly, read the proper path, and proceeded without errors.
    Aspects:
    Temp-file tool handling correctness | Winner: AM | Severity: low | Evidence: AN read_file → “Virtual file does not exist …” after list_dir
    Non-productive detour after tool error | Winner: AM | Severity: low | Evidence: AN made an additional search_file_by_name call after the failure
    Score given: 1 or -1 depending on who is N and M
Below is an example specific for Pitfalls and ToolCalls dimension, where both agents had issues, but "manual rollback" seemed more critical:
    - Agent N introduced a workflow-stopping repository break: multiple edit_file operations corrupted test code (e.g., turning an assignment into a stray queryConfig( line), causing cascaded compile/IDE errors (“Cannot resolve symbol…”, “';' expected”) and requiring manual recovery via git checkout -- .... Agent M made some incorrect assumptions and minor requirement drift, but did not corrupt files or require rollback, and kept changes localized.
    Aspects:
    Manual rollback needed to recover | Winner: AM | Severity: high | Evidence: AN git checkout -- ...ConfigControllerTest.java / ...ConfigFileControllerTest.java
    Cascading compile breakage from tool misuse | Winner: AM | Severity: medium | Evidence: AN widespread “Cannot resolve method 'queryConfig'” after edits
    File corruption via edits (repo inconsistent) | Winner: AM | Severity: medium | Evidence: AN ConfigControllerTest.java shows broken queryConfig( line; IDE errors “Cannot resolve symbol 'result'”, “';' expected”
    Misleading intermediate claim (corrected). | Winner: AN | Severity: medium | Evidence: AM premature call-site claim later corrected via .queryConfig( search
    Score given: 3 or -3 depending on who is N and M

Response consists of two parts:
- {COMPARISON_SEPARATOR}, 2 to 5 sentences PLUS the breakdown lines at the end. Avoid primacy and framing bias. Do not start the comparison with “Agent 1 …” or “Agent 2 …”. First describe the concrete difference in behavior in neutral, role-free terms (e.g., “One trajectory shows repeated edit failures due to missing required arguments, while the other applies edits without tool errors”).
Only after stating the difference, explicitly assign Winner: A1/A2/Tie in the structured breakdown. Keep the narrative symmetric and avoid framing one agent as the default reference point.
- {PAIRWISE_SCORE_SEPARATOR}, an integer in [-5, 5]. Use negative when Agent 1 is better, positive when Agent 2 is better.
  -5 means Agent 1 is MUCH better and the difference would feel very severe for the user. 0 means tie/indistinguishable. +5 means Agent 2 is MUCH better and the difference would feel very severe for the user. So the score is symmetric this way. When setting the score, mentally check the sign: negative for Agent 1 win, positive for Agent 2 win.

Template:
{COMPARISON_SEPARATOR}
[2-5 sentences comparison] + 
Aspect: ... | Winner: ... | Severity: ... | Evidence: ...
...

{PAIRWISE_SCORE_SEPARATOR}
[-5..5]
</Instructions>

{LlmJudgeInstructions.END_OF_PROMPT}"""
    return prompt


def build_trajectory_comparisons_summary_prompt(
    comparisons_text: str,
    dimension_name: str,
    config_dict: Mapping[str, Any],
) -> str:
    answer_language_instruction = get_answer_language_instruction(config_dict)
    user_specific_instruction = get_user_specific_prompt_instruction(config_dict)
    return f"""
<Comparisons>
{comparisons_text}
</Comparisons>

<Instructions>
Above you have a sequence of per-task pairwise comparisons between Agent 1 and Agent 2 for performance dimension '{dimension_name}'. Other dimensions are handled by other Judges, don't touch them. Each item is labeled as 'Comparison: Ck'.

POSITION-INVARIANCE (MANDATORY):
- The *order* of presentation must not affect your judgement.
- Keep identities consistent: A1 always means Agent 1, A2 always means Agent 2.
- Do not "paint" a side via rhetoric. Every claim in the final summary MUST be backed by a proof line you extracted.

INPUT CONTRACT (CRITICAL):
Each Ck contains several structured lines of the form:
`Aspect: ... | Winner: A1/A2/Tie | Severity: low/medium/high | Evidence: ...`
These lines are the ONLY trusted source of truth.
Ignore any other prose in Ck if it contradicts or is not supported by these Aspect-lines.

YOUR TASK (ALGORITHMIC, TWO-STAGE):
Stage 1 — Extract & regroup proofs (must be explicit):
1) Scan all Ck and extract ALL Aspect-lines.
2) Normalize/group them by Aspect meaning (merge obvious paraphrases; keep 3–8 groups total).
3) For each group, list the supporting Ck items as proof entries in this format:
   `- [Ck] Winner=A1/A2/Tie | Severity=low/medium/high | Evidence="..."`
   Sort proof entries within a group by severity: high → medium → low.
4) If you cannot find any Aspect-lines, output "No comparisons".

Stage 2 — Write the concise summary (derived only from Stage 1):
- Write 1 to 5 sentences that summarize ONLY what is in the proof groups.
- Do not use vague frequency markers. If you claim frequency, state counts like "in 7 of 15 Ck".
- Do not propose fixes; only characterize differences.

ALERT FLAG RULE (DETERMINISTIC):
Set AlertFlag=true iff there exists at least one Aspect-group where:
- the winning side is the same (A1 or A2, not Tie) in >=3 different Ck, AND
- at least one of those proof entries has Severity=high.
Otherwise AlertFlag=false.

In the Comparison section follow these rules:
- When you refer to Ck items, prefer specific references like C3 or C10 when possible.
- Prefer common terminology over local jargon. Ck references are fine though.
- When you refer to critical cases, describe them or give a reference right away. Never say "high-case" or "low-case" -- it's a local jargon. When you say 'aspect' -- make sure it's clear for an end-user what it means, or don't say it.
- When you say something like, 'Agent X is better at...', keep in mind: to what extent is this issue exclusive for Agent X? Should it meaningfully change how we think about Agent X — i.e., should we see him as “someone who does Z”? Or is it just that Agent X is slightly more prone to this than Agent Y?
- If you say that an agent did better on a given aspect in N cases, you should also say in how many cases they did worse. You should provide Ck items as references to the most significant ones.
- Use line breaks after each sentence (or each semantic section).

DEBUG USEFULNESS:
Another challenge is making your summary useful for debugging the agents. Examples:
- if there is a specific harness issue (e.g., edit tool always returns an error), it is very important to mention it.
- if one agent fails tests on every task, that may imply a benchmark-specific issue with repo checkout.
FYI, one of the main pipelines for us is to read your comparison summary to see if we have a regression. When we see there is a regression, we want to know why exactly. This way we can even map this degradation to a specific commit sometimes.

{answer_language_instruction}
{user_specific_instruction}

Response consists of three parts:
- <Analysis>: proof regrouping table from Stage 1 (NOT user-facing).
- {COMPARISON_SEPARATOR}: final user-facing summary from Stage 2 only.
- {ALERT_FLAG_SEPARATOR}: true|false.

OUTPUT FORMAT (STRICT):
1) <Analysis> MUST contain the proof table regrouping (Stage 1) in this exact format:
<Analysis>
Proof:
AspectGroup: <name>
- [Ck] Winner=A1/A2/Tie | Severity=low/medium/high | Evidence="..."
...
</Analysis>
(1–8 groups total)

2) {COMPARISON_SEPARATOR} MUST contain ONLY the final summary (Stage 2) of 1–5 sentences.

Template:
<Analysis>
Proof:
AspectGroup: <name>
- [Ck] Winner=... | Severity=... | Evidence="..."
...
</Analysis>

{COMPARISON_SEPARATOR}
[1-5 sentences]

{ALERT_FLAG_SEPARATOR}
[true|false]
</Instructions>
"""


class LlmJudgeInstructions:
    SYSTEM_PROMPT = """You are a coding expert and an objective critic. Your work will be checked and judged later on. Vagueness leads to your death."""

    OUT_FORMAT_REVIEW_SCORE = f"""\
Response consists of 2 parts:
- {REVIEW_SEPARATOR}, 2 to 5 sentences narrative focused on the metric. After the narrative, add 1 to 6 short structured evidence lines when applicable:
  `Aspect: <free text> | Severity: low/medium/high | Evidence: <short quote/tool/error>`
  Make Aspect-lines concrete and reusable: they are the main guide for later aggregation.
  Severity is absolute (not delta-based).
- {SCORE_SEPARATOR}, the sole final number. Must be one number and nothing else.

Template:
{REVIEW_SEPARATOR}
[2-5 sentences]
Aspect: ... | Severity: ... | Evidence: ...
...

{SCORE_SEPARATOR}
[0|0.5|1]"""

    DATA_COMPUTE_SINGLE = (
        lambda point: f"""
{get_last_simulator_request_messages(point)}

Above you have a history of interactions between a user simulator and an agent. This history contains additional system info and system messages that we have passed to the simulator during the conversation. Some parts were truncated to shorten your prompt and the user simulator’s prompt. For example, you might see "remaining characters are omitted only from the User Simulator’s prompt..." message. It means that an original transcript was truncated only after the task was completed.
Tool call responses might contain lists of errors that occurred during the tool call: if such a list is empty, it means that there were no errors (e.g., empty compilation_errors section for edit_file tool). The last user message might not be present in the history: either because the user decided to terminate the chat or because a time limit was reached; the reason is unknown.
Note that this interaction was collected in a benchmark environment, that differs from real life situations: for example, when the agent catches a timeout, it means that it has probably hit the benchmark time limit.
Your task is to judge the agent, not the simulator. So if the task is not achieved due to user simulator failures, it should not affect the score you give. Treat the simulator's actions as a given, even if they seem suboptimal, and judge the agent based on how well it responds within that context.
There might be an <{AGENT_ACTIONS_SUMMARY_TAG}> section in their chat. We append it to help the simulator understand what the agent did. As the simulator-agent conversation progresses, this info gets updated and appended to the last agent message sent to the simulator. All previous information gets dropped from the previous messages though, so you don't see them in the given history. This system info consists of:
 - a section with a list of compilation errors from IDE analysis (project errors); if empty, there are no compilation errors in the project;
 - all the code diffs made by the agent (maybe empty);
 - the most recent cmd calls (maybe empty).
Note that we use a simulator instead of a real user: it behaves based on character traits given to it.

Below we've gathered a final summary of the agent's actions and state of the project:
<{AGENT_ACTIONS_SUMMARY_TAG}>
{point[FieldNames.AGENT_TRACE_PROMPT]}
</{AGENT_ACTIONS_SUMMARY_TAG}>

The chat has terminated for the following reason:
<termination_reason>
{point[FieldNames.TERMINATION_REASON] if len(point[FieldNames.TERMINATION_REASON]) > 0 else "Unknown"}
</termination_reason>
"""
    )

    DATA_COMPUTE_PAIR = (
        lambda point1, point2, metric_name: f"""
<agent1_trajectory>
{get_last_simulator_request_messages(point1)}
</agent1_trajectory>

<agent2_trajectory>
{get_last_simulator_request_messages(point2)}
</agent2_trajectory>

Above are two chat transcripts (each between a user simulator and an agent) for the same task, one per agent, delimited by <agent1_trajectory> and <agent2_trajectory> tags. Some parts were truncated to shorten your prompt and the user simulator’s prompt. For example, you might see "remaining characters are omitted **only from the User Simulator’s prompt**..." message. It means that an original transcript was truncated only after the task was completed.

<agent1_review>
{
            get_judge_review_or_symmetric_stub(
                point=point1, reference_point=point2, metric_name=metric_name
            )
        }
</agent1_review>

<agent2_review>
{
            get_judge_review_or_symmetric_stub(
                point=point2, reference_point=point1, metric_name=metric_name
            )
        }
</agent2_review>

The two blocks above, delimited by the <agent1_review> and <agent2_review> tags, are precomputed single-trajectory reviews from another pipeline. They are for the same task instance, one per agent, both focused on the same performance dimension. They were computed independently from the raw transcripts.
The performance dimension name for these reviews is '{metric_name}'. 
"""
    )

    DATA_AGGREGATE = (
        lambda per_point_analysis: "Below you have a list of reviews with findings from individual data points.\n<Reviews>\n"
        + "\n\n".join(
            [f"Review: R{i + 1}\n" + e for i, e in enumerate(per_point_analysis)]
        )
        + "\n</Reviews>"
        if len(per_point_analysis) > 0
        else 'No Examples given! Respond with "No Examples Given"!'
    )

    END_OF_PROMPT = """Provide your response in the requested format:"""

    FOCUS_ON_END_RESULT = """<Focus>\nFor this task, focus on the **end result** solely: does not matter what the path to get there was. You might get a lot of irrelevant information from the user-agent dialogue. Extract what the end result looks like and evaluate it in isolation. E.g., if you need to evaluate code of some class, you should ignore all messages from the user-agent dialogue, as well as all the versions of that code which did not make it to the end and were revised.\n</Focus>"""

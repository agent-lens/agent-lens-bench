from typing import Dict

from agent_lens.eval.common.trajectory import get_last_simulator_request_messages
from agent_lens.eval.data_framework.field_names import FieldNames
from agent_lens.eval.metrics.llm_judge.common.judge_data import (
    get_judge_review_or_symmetric_stub,
)

AGENT_ACTIONS_SUMMARY_TAG = "agent_actions_summary"


def build_single_run_data_section(point: Dict) -> str:
    return f"""
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
Keep in mind that the agent may have had access to additional system information not shown here, such as open files or recent commit names, and may have acted based on it.

Below we've gathered a final summary of the agent's actions and state of the project:
<{AGENT_ACTIONS_SUMMARY_TAG}>
{point[FieldNames.AGENT_TRACE_PROMPT]}
</{AGENT_ACTIONS_SUMMARY_TAG}>

The chat has terminated for the following reason:
<termination_reason>
{point[FieldNames.TERMINATION_REASON] if len(point[FieldNames.TERMINATION_REASON]) > 0 else "Unknown"}
</termination_reason>
"""


def build_pairwise_data_section(
    point1: Dict,
    point2: Dict,
    metric_name: str,
) -> str:
    return f"""
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

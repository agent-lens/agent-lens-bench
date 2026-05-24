from agent_lens.eval.metrics.llm_judge.interfaces.llm_metrics import LlmMetric
from agent_lens.eval.metrics.llm_judge.interfaces.pairwise_llm_metrics import (
    PairwiseLlmMetric,
)


class PitfallsMetric(LlmMetric, PairwiseLlmMetric):
    @staticmethod
    def get_name():
        return "Pitfalls"

    @property
    def _pairwise_specific_instruction(self) -> str:
        return """\
Focus on identifying and diagnosing fixable failures in the agents' behavior that hinder the user (mostly harness/tooling/workflow issues). This is about instability patterns and self-sabotage dynamics, not outcome quality.

POSITION-INVARIANCE (MANDATORY):
- The *order* of presentation must not affect your judgement.
- However, you must keep identity consistent: any pitfall you list must be clearly attributed to Agent 1 or Agent 2 and must not "flip" mid-comparison.
- Write your analysis so that if the trajectories were swapped, the reasoning would stay the same and only the final score sign would flip.

EVALUATION PROTOCOL (follow in this order):
1) Extract pitfalls separately for Agent 2 and Agent 1 using the same rubric. For each pitfall provide: Category, Severity (low/medium/high), Frequency (once/repeated), and a short evidence quote (tool name + error text, or a brief message fragment).
2) Compute pitfall burden totals Total_1 and Total_2 (formula below).
3) Only after step (2), map (Total_1 vs Total_2) to a score using the deterministic rules below.

CATEGORIES (use consistent taxonomy):
- Logic/Code faults: demonstrable wrong code/logic or missing validation that risks wrong output.
- Tool/Harness faults: tool misuse, wrong args, inability to recover from tool errors, patching mistakes, broken edit_file usage, etc.
- Process/Interaction faults: misunderstanding requirements, non-productive loops, poor communication, premature "done", ignoring constraints.
- One behavioral cluster (e.g., a loop of identical tool calls) must be counted as at most one distinct pitfall. If the same tool or process error appears two or more times with the same root cause, it must be labeled as "repeated" and counted as a single pitfall with a frequency multiplier, not as multiple distinct pitfalls.

KEEP EXAMPLES CONCRETE:
(tool misuse, loops, missing validation, partial completion, placeholders, poor communication, self-contradiction, premature completion, failure to verify).
Emphasize causal mechanisms (why the failure happens), not just outcomes.

SCORING (SYMMETRIC, FORMULA-BASED):
Compute a pitfall burden score for each side and derive the pairwise score from the delta.

A) PITFALL BURDEN SCORING PER AGENT
For each distinct pitfall you listed in step (1), assign points:
- low = 1
- medium = 3
- high = 7
Frequency multiplier:
- once = x1
- repeated/looping/compounding = x2
So each pitfall contributes (severity_points * frequency_multiplier).
Sum to get totals: Total_1 (Agent 1), Total_2 (Agent 2).

B) DELTA (deterministic)
Delta = Total_2 - Total_1.
(Positive Delta means Agent 1 is better; negative Delta means Agent 2 is better.)

C) MAP DELTA TO FINAL SCORE (integer in [-5..5])
Use |Delta| only to choose the magnitude; the sign is determined solely by which agent is worse.
Magnitude table:
- |Delta| <= 3  -> 0
- 4..6          -> 1
- 7..10         -> 2
- 11..15        -> 3
- 16..22        -> 4
- >=23          -> 5
Sign rule (STRICT):
- If Delta > 0 (Agent 1 better): score MUST be negative.
- If Delta < 0 (Agent 2 better): score MUST be positive.
- If Delta == 0: score = 0.

OUTPUT REQUIREMENT (to enforce symmetry):
At the end of your narrative (before the structured Aspect lines), include a single line:
`Totals: A1=<Total_1>, A2=<Total_2>, Delta=A2-A1=<Delta> => Score=<score>`

CRITICAL:
- The final score MUST be computed ONLY from this Totals/Delta line using the mapping rules above.
- Never mix up agent identities: A1 refers to Agent 1 trajectory, A2 refers to Agent 2 trajectory.
- Do not use any other "overall impression". If your narrative suggests something else, adjust the pitfall list and totals until they match.
These numbers must be consistent with your pitfall list and with the mapping rules above.
"""

    @property
    def _single_run_specific_instruction(self) -> str:
        return """\
Identify and diagnose fixable pitfalls in the agent's behavior that hindered the user.
This is about instability patterns and self-sabotage dynamics (often harness/tooling/workflow), not end-result quality.

Extract pitfalls using this rubric. For each distinct pitfall, provide:
- Category: Logic/Code faults | Tool/Harness faults | Process/Interaction faults | Something else
- Severity: low/medium/high
- Frequency: once/repeated
- Evidence: a short quote (tool name + error text, or a brief message fragment)
- Mechanism: 1 short clause on why this happened (root cause)

Counting rule (mandatory):
- One behavioral cluster (e.g., a loop of identical tool calls) counts as at most one pitfall; if it repeats with the same root cause, mark it as Frequency=repeated.

Pitfall burden total (mandatory):
- severity points: low=1, medium=3, high=7
- frequency multiplier: once=x1, repeated=x2
- Total = sum(severity_points * frequency_multiplier) across distinct pitfalls

Write pitfalls as structured lines so they can be reused later:
`Pitfall: <free text> | Category: ... | Severity: ... | Frequency: ... | Evidence: ... | Mechanism: ...`
Also include one line: `BurdenTotal=<Total>`.
"""

    @property
    def _single_run_scoring_guidelines(self) -> str:
        return """\
Score should be a number from [0, 0.5, 1], where:
- 0 means miserable performance,
- 0.5 means tolerable,
- 1 means actually good.
"""

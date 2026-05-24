"""Comparison-specific constants for Markdown rendering."""

from typing import Any, Dict

from agent_lens.eval.data_framework.field_names import FieldNames

JsonDict = Dict[str, Any]

COMPARISONS_DIR_NAME = "comparisons"
RUN_REFERENCE_PREFIX = "R"
COMPARISON_REFERENCE_PREFIX = "C"
CHATS_REVIEWED_ENTRY_SEPARATOR = ":"

INFERENCE_METRIC_NAMES = {
    "price",
    "generation_tokens",
    "time",
    FieldNames.GEN_TOKENS_TO_SECONDS_RATIO,
    FieldNames.TOOL_CALL_COUNT_REPORT,
    "cache_hit_mean_ratio",
    FieldNames.TOOL_CALLS_IN_PARALLEL,
}

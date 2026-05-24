from itertools import chain
from typing import Any, Mapping
import numpy as np

from anonymous.eval.common.statistics import safe_mean
from anonymous.eval.data_framework.field_names import FieldNames
from anonymous.eval.metrics.analytics.testing_metrics import (
    add_test_metrics_aggregates,
)
from anonymous.eval.metrics.tag_names import TagNames


def get_basic_stats_response_level(
    nums: list[list[float]], qts: tuple[int, ...] | None = (10, 50, 80, 100)
) -> dict[str, float | str]:
    if qts is None:
        return {"total": sum(nums)}

    response_nums = sum(nums, [])
    response_quantiles = (
        np.percentile(response_nums, qts) if len(response_nums) > 0 else None
    )

    chat_nums = [sum(per_chat_nums) for per_chat_nums in nums]
    chat_quantiles = np.percentile(chat_nums, qts) if len(response_nums) > 0 else None

    return (
        {"total": sum(chat_nums)}
        | _make_qts_report("response", qts, response_quantiles)
        | _make_qts_report("chat", qts, chat_quantiles)
    )


def get_basic_stats_chat_level(
    nums: list[float],
    qts: tuple[int, ...] | None = (10, 50, 80, 100),
    agg_fun: str = "sum",
) -> dict[str, float | str]:
    if qts is None or len(nums) == 0:
        return {"total": sum(nums)}
    chat_quantiles = np.percentile(nums, qts) if len(nums) > 0 else None
    if agg_fun == "sum":
        agg = {"total": sum(nums)}
    elif agg_fun == "mean":
        agg = {"average": sum(nums) / len(nums)}
    else:
        raise RuntimeError(f"Unexpected aggregate function: {agg_fun}")
    return agg | _make_qts_report("chat", qts, chat_quantiles)


def _make_qts_report(
    qtl_level: str, qts: tuple[float, ...], qts_vals: tuple[float, ...] | None
) -> dict[str, str]:
    qtl_val = "null" if qts_vals is None else " / ".join(f"{v:.2f}" for v in qts_vals)
    qtl_label = " / ".join(str(q) for q in qts)
    return {f"{qtl_label} {qtl_level} level qtl": qtl_val}


def _get_total_per_point(point: Mapping[str, Any], field_name: str) -> float:
    values = point[field_name]
    if len(values) == 0:
        return 0.0
    if isinstance(values[0], list):
        return float(sum(sum(values, [])))
    return float(sum(values))


def _get_gen_tokens_to_seconds_ratio(dataset: Mapping[str, Mapping[str, Any]]) -> float:
    total_agent_time = sum(
        _get_total_per_point(point, FieldNames.AGENT_TIME_PER_INTERACTION)
        for point in dataset.values()
    )
    total_generation_tokens = sum(
        _get_total_per_point(point, FieldNames.AGENT_GENERATION_TOKENS)
        for point in dataset.values()
    )
    return round(total_generation_tokens / (total_agent_time + 1e-9), 2)


def get_basic_aggregates(
    dataset: Mapping[str, Mapping[str, Any]], bench_tag_name: str
) -> dict[str, Any]:
    report = {}
    for per_response_dim in [
        FieldNames.AGENT_PRICE_PER_INTERACTION,
        FieldNames.AGENT_TIME_PER_INTERACTION,
    ]:
        report[per_response_dim] = get_basic_stats_response_level(
            [v[per_response_dim] for v in dataset.values()]
        )
    for per_chat_dim in [
        FieldNames.FORMAL_VERIFICATION_RESULT,
    ]:
        report[per_chat_dim] = get_basic_stats_chat_level(
            [scenario[per_chat_dim] for k, scenario in dataset.items()], None
        )

    termination_counts = {}
    for point in dataset.values():
        termination_reason = point[FieldNames.TERMINATION_REASON]
        termination_counts[termination_reason] = (
            termination_counts.get(termination_reason, 0) + 1
        )
    report[FieldNames.TERMINATION_REASON] = termination_counts

    if bench_tag_name == TagNames.testing:
        report = add_test_metrics_aggregates(
            report,
            dataset,
            get_basic_stats_chat_level,
        )

    report[FieldNames.GEN_TOKENS_TO_SECONDS_RATIO] = _get_gen_tokens_to_seconds_ratio(
        dataset
    )
    report[FieldNames.NUM_CHATS] = len(dataset)
    report[FieldNames.NUM_AGENT_SCENARIOS] = len(
        set(d[FieldNames.AGENT_SCENARIO_NAME] for d in dataset.values())
    )
    report[FieldNames.FORMAL_VERIFICATION_SUCCESS_RATE] = (
        None
        if len(dataset) == 0
        else sum(
            point[FieldNames.FORMAL_VERIFICATION_RESULT] for point in dataset.values()
        )
        / len(dataset)
    )
    return report


def get_tool_success_stats(dataset: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    report = {}
    if dataset == {}:
        return {}

    # Gather per-message tool call groups (parallel calls) and per-chat flattened lists
    tools_per_tool_response = []  # list of lists, each inner list is calls made in parallel within a single message
    tools_per_chat = []  # list per chat, each item is a flat list of all tool calls in the chat

    for point in dataset.values():
        # Each value is a list of tool call dicts for that message number (parallel calls)
        per_msg = [lst for lst in point[FieldNames.TOOL_CALLS_DUMP].values()]

        tools_per_tool_response.extend(per_msg)
        tools_per_chat.append(list(chain.from_iterable(per_msg)))  # flatten per chat

    tools_per_chat_num = [len(tool_calls) for tool_calls in tools_per_chat]
    tools_response_list = list(chain.from_iterable(tools_per_tool_response))

    # Build (tool_name, success_bool) encounters
    tool_encounters = []
    for response in tools_response_list:
        if not isinstance(response, dict):
            continue
        name = response["name"]
        success = bool(response["success"])
        if name is None:
            continue
        tool_encounters.append((name, success))

    success_and_fail_counts = {}
    for encounter in tool_encounters:
        success_and_fail_counts[encounter] = (
            success_and_fail_counts.get(encounter, 0) + 1
        )

    # aggregate basic call stats
    report |= {
        FieldNames.TOOL_CALLS_IN_PARALLEL: round(
            safe_mean([len(calls) for calls in tools_per_tool_response], ret_val=0),
            3,
        ),
        FieldNames.TOOL_CALLS_PER_CHAT_MEAN: round(
            safe_mean(tools_per_chat_num, ret_val=0), 3
        ),
        FieldNames.TOOL_CALL_COUNT_REPORT: sum(tools_per_chat_num),
    }

    # build per-tool success/failure counts
    tools = list({name for name, _ in success_and_fail_counts.keys()})
    per_tool_counts = {}
    for tool in tools:
        successes = success_and_fail_counts.get((tool, True), 0)
        failures = success_and_fail_counts.get((tool, False), 0)
        per_tool_counts[tool] = {"successes": successes, "total": failures + successes}

    # sort tools for reporting by (failures + 1) / (total + 2) ascending (worst first). Tie-breaker: more total calls.
    def _get_sort_stat(tool_name: str):
        counts = per_tool_counts[tool_name]
        return -(counts["total"] - counts["successes"] + 1) / (
            counts["total"] + 2
        ), -counts["total"]

    # reorder per_tool_counts in-place by reinserting in the sorted order
    per_tool_counts = {
        tool: per_tool_counts[tool]
        for tool in sorted(per_tool_counts.keys(), key=_get_sort_stat)
    }

    report[FieldNames.TOOL_CALLS_SUCCESS_RATES] = {
        tool: f"{counts['successes']}/{counts['total']}"
        for tool, counts in per_tool_counts.items()
    }

    return report

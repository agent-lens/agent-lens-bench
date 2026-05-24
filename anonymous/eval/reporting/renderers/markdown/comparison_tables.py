"""Table renderers for comparison summary Markdown."""

from typing import List, Tuple

from anonymous.eval.reporting.renderers.markdown.comparison_constants import (
    JsonDict,
)
from anonymous.eval.reporting.renderers.markdown.comparison_formatting import (
    fmt_alert_cell,
    fmt_bool,
    fmt_val,
)


def render_inference_metrics_table(lines: List[str], objs: List[JsonDict]) -> None:
    if not objs:
        return

    lines.append("## Inference metrics")
    lines.append("")
    lines.append("| Metric | p-value | run 1 | run 2 | alert | warning |")
    lines.append("| --- | --- | --- | --- | --- | --- |")

    for obj in objs:
        raw_name = str(obj.get("name", ""))
        metric_name = raw_name.replace("_", " ") or raw_name

        alert = obj.get("alert_flag")
        warning = obj.get("warning_flag")
        p_value = obj.get("p_value")
        m1 = obj.get("metrics_value1")
        m2 = obj.get("metrics_value2")

        line = " | ".join(
            [
                metric_name,
                fmt_val(p_value),
                fmt_val(m1),
                fmt_val(m2),
                fmt_alert_cell(alert),
                fmt_bool(warning),
            ]
        )
        lines.append(f"| {line} |")

    lines.append("")


def _get_sort_success_rate_key(sort_tool_obj: JsonDict) -> Tuple[float, int]:
    rate1_raw = sort_tool_obj.get("metrics_value1")
    rate2_raw = sort_tool_obj.get("metrics_value2")
    total1 = sort_tool_obj.get("total_count1") or 0
    total2 = sort_tool_obj.get("total_count2") or 0

    try:
        rate1 = float(rate1_raw) if rate1_raw is not None else 0.0
    except (TypeError, ValueError):
        rate1 = 0.0
    try:
        rate2 = float(rate2_raw) if rate2_raw is not None else 0.0
    except (TypeError, ValueError):
        rate2 = 0.0

    ratio = (rate1 / rate2) if rate2 > 0.0 else (float("inf") if rate1 > 0.0 else 1.0)

    total_calls = int(total1) + int(total2)
    # Negate to sort in descending order for both ratio and total calls.
    return -ratio, -total_calls


def render_tool_success_rates_table(lines: List[str], objs: List[JsonDict]) -> None:
    if not objs:
        return

    lines.append("## Tool call success rates")
    lines.append("")
    lines.append(
        "| Tool | run 1 success | run 2 success | run 1 total | run 2 total | alert | warning |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")

    for entry in sorted(objs, key=_get_sort_success_rate_key):
        entry_raw_name = str(entry.get("name", ""))
        entry_tool_key = entry_raw_name.replace("_success_rates", "")
        entry_tool_name = entry_tool_key or entry_raw_name

        entry_alert = entry.get("alert_flag")
        entry_warning = entry.get("warning_flag")
        entry_succ_rate_run1 = entry.get("metrics_value1")
        entry_succ_rate_run2 = entry.get("metrics_value2")
        entry_total_run1 = entry.get("total_count1")
        entry_total_run2 = entry.get("total_count2")

        line = " | ".join(
            [
                entry_tool_name,
                fmt_val(entry_succ_rate_run1),
                fmt_val(entry_succ_rate_run2),
                fmt_val(entry_total_run1),
                fmt_val(entry_total_run2),
                fmt_alert_cell(entry_alert),
                fmt_bool(entry_warning),
            ]
        )
        lines.append(f"| {line} |")

    lines.append("")

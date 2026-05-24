"""Rendering of non-table sections for comparison summary Markdown."""

import logging
from typing import Any, List, Optional, Tuple

from anonymous.eval.data_framework.field_names import FieldNames
from anonymous.eval.reporting.renderers.markdown.citation_links import (
    link_review_citations,
    metric_dir_from_section_name,
)
from anonymous.eval.reporting.renderers.markdown.comparison_constants import (
    COMPARISONS_DIR_NAME,
    INFERENCE_METRIC_NAMES,
    JsonDict,
)
from anonymous.eval.reporting.renderers.markdown.comparison_formatting import (
    bool_flag,
)
from anonymous.eval.reporting.renderers.markdown.markdown_constants import (
    REVIEWS_DIR_NAME,
)
from anonymous.eval.reporting.renderers.markdown.markdown_utils import (
    render_json_value,
    render_kv_list,
)

LOG = logging.getLogger(__name__)


def split_report_objects(
    data: List[Any],
) -> Tuple[
    Optional[str],
    List[JsonDict],
    List[JsonDict],
    List[JsonDict],
    Optional[JsonDict],
    Optional[JsonDict],
    Optional[JsonDict],
]:
    """Split raw report JSON objects into buckets used by the renderer."""

    tldr_text: Optional[str] = None
    success_rate_objs: List[JsonDict] = []
    inference_objs: List[JsonDict] = []
    regular_objs: List[JsonDict] = []
    formal_verification_obj: Optional[JsonDict] = None
    termination_reason_obj: Optional[JsonDict] = None
    metadata_obj: Optional[JsonDict] = None

    for obj in data:
        if not isinstance(obj, dict):
            continue

        if "TLDR" in obj:
            raw = obj.get("TLDR")
            if raw is not None:
                tldr_text = str(raw)
            continue

        obj_name = str(obj.get("name", ""))

        if obj_name.lower() == "metadata":
            metadata_obj = obj
            continue
        if obj_name == FieldNames.FORMAL_VERIFICATION_RESULT:
            formal_verification_obj = obj
            continue
        if obj_name == FieldNames.TERMINATION_REASON:
            termination_reason_obj = obj
            continue
        if obj_name.endswith("success_rates"):
            success_rate_objs.append(obj)
        elif obj_name in INFERENCE_METRIC_NAMES:
            inference_objs.append(obj)
        else:
            regular_objs.append(obj)

    return (
        tldr_text,
        success_rate_objs,
        inference_objs,
        regular_objs,
        formal_verification_obj,
        termination_reason_obj,
        metadata_obj,
    )


def render_tldr(lines: List[str], tldr_text: Optional[str]) -> None:
    if not tldr_text:
        return
    lines.append("## TLDR")
    lines.append("")
    lines.append(tldr_text)
    lines.append("")


def _fmt_reasons(termination_data: JsonDict) -> str:
    if not termination_data:
        return "(none)"
    parts = [f"{reason} ({count})" for reason, count in termination_data.items()]
    return ", ".join(parts)


def render_termination_reasons(lines: List[str], obj: Optional[JsonDict]) -> None:
    if obj is None:
        return

    obj_name = obj.get("name", FieldNames.TERMINATION_REASON)
    lines.append(f"## {obj_name}")
    lines.append("")
    lines.append(bool_flag("alert", obj.get("alert_flag")))
    lines.append(bool_flag("warning", obj.get("warning_flag")))

    common = obj.get("common") or {}
    diff1 = obj.get("diff1") or {}
    diff2 = obj.get("diff2") or {}

    lines.append(f"- common: {_fmt_reasons(common)}")
    lines.append(f"- only_run1: {_fmt_reasons(diff1)}")
    lines.append(f"- only_run2: {_fmt_reasons(diff2)}")
    lines.append("")


def render_metadata(lines: List[str], metadata_obj: Optional[JsonDict]) -> None:
    if not metadata_obj:
        return

    lines.append("## Metadata")
    lines.append("")

    preferred_order = ["run1", "run2", "judge"]
    keys = [k for k in metadata_obj.keys() if k != "name"]

    ordered: List[str] = []
    for k in preferred_order:
        if k in keys:
            ordered.append(k)
    for k in sorted(keys):
        if k not in ordered:
            ordered.append(k)

    for key in ordered:
        value = metadata_obj.get(key)
        if value is None:
            continue

        lines.append(f"**{key}**")

        if isinstance(value, dict):
            render_kv_list(lines=lines, mapping=value, preferred_order=[])
            lines.append("")
        else:
            render_json_value(lines=lines, key="value", value=value)
            lines.append("")


def format_score_block(score: JsonDict) -> str:
    name = score.get("name", "score")
    p_value = score.get("p_value")

    m1 = score.get("metrics_value1")
    m2 = score.get("metrics_value2")

    pairwise_value = score.get("metrics_value")
    score_scale = score.get("score_scale")

    lines = [f"**{name}**"]
    if p_value is not None:
        lines.append(f"- p-value: `{p_value}`")

    if pairwise_value is not None:
        scale_suffix = f" (from {score_scale})" if score_scale else ""
        lines.append(f"- metrics_value{scale_suffix}: `{pairwise_value}`")
        return "\n".join(lines)

    if m1 is not None or m2 is not None:
        lines.append("- metrics:")
        lines.append("  - agent 1: `{}`".format(m1))
        lines.append("  - agent 2: `{}`".format(m2))

    return "\n".join(lines)


def format_simple_metrics(obj: JsonDict) -> Optional[str]:
    if any(k in obj for k in ("text_cmp", "score_comparison")):
        return None

    m1 = obj.get("metrics_value1")
    m2 = obj.get("metrics_value2")
    p_value = obj.get("p_value")
    difference = obj.get("difference")

    lines: List[str] = []
    if p_value is not None:
        lines.append(f"- p-value: `{p_value}`")
    if m1 is not None or m2 is not None:
        lines.append("- metrics:")
        lines.append("  - agent 1: `{}`".format(m1))
        lines.append("  - agent 2: `{}`".format(m2))
    if difference is not None:
        lines.append(f"- difference: `{difference}`")

    return "\n".join(lines) if lines else None


def render_named_section(lines: List[str], obj: JsonDict) -> None:
    obj_name = obj.get("name", "(unnamed)")
    alert = obj.get("alert_flag")
    warning = obj.get("warning_flag")

    lines.append(f"## {obj_name}")
    lines.append("")
    lines.append(bool_flag("alert", alert))
    lines.append(bool_flag("warning", warning))

    has_block_after_flags = False

    text_cmp = obj.get("text_cmp")
    if isinstance(text_cmp, dict):
        review = text_cmp.get("review")
        judge_alert = text_cmp.get("judge_alert")
        chats_reviewed = text_cmp.get("chats_reviewed")
        if review:
            metric_dir = metric_dir_from_section_name(str(obj_name))
            linked_review = link_review_citations(
                review=str(review),
                chats_reviewed=chats_reviewed,
                metric_dir=str(metric_dir),
                reviews_rel_dir=REVIEWS_DIR_NAME,
                comparisons_rel_dir=COMPARISONS_DIR_NAME,
                section_name=str(obj_name),
                log=LOG,
            )
            lines.append("")
            lines.append("**Review**:")
            lines.append("")
            lines.append(linked_review)
            has_block_after_flags = True

        if judge_alert is not None:
            lines.append(bool_flag("judge alert", judge_alert))
            has_block_after_flags = True

    score_cmp = obj.get("score_comparison")
    if isinstance(score_cmp, dict):
        lines.append("")
        lines.append(format_score_block(score_cmp))
        has_block_after_flags = True

    simple_metrics_block = format_simple_metrics(obj)
    if simple_metrics_block:
        if has_block_after_flags:
            lines.append("")
        lines.append(simple_metrics_block)

    lines.append("")


def infer_total_points(data: List[Any]) -> Optional[int]:
    termination_obj: Optional[JsonDict] = None
    for obj in data:
        if not isinstance(obj, dict):
            continue
        if obj.get("name") == FieldNames.TERMINATION_REASON:
            termination_obj = obj
            break

    if not termination_obj:
        return None

    common_block = termination_obj.get("common")
    diff1_block = termination_obj.get("diff1")
    if common_block is None or diff1_block is None:
        return None

    if not isinstance(common_block, dict) or not isinstance(diff1_block, dict):
        return None

    total = sum(int(v) for v in common_block.values()) + sum(
        int(v) for v in diff1_block.values()
    )
    return total

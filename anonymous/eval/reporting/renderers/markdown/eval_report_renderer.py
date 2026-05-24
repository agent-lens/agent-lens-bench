"""Render single-run (eval) report JSON into Markdown."""

import argparse
import logging
import re
from pathlib import Path
from typing import Any, Mapping

from anonymous.eval.common.json_io import read_json

from anonymous.eval.data_framework.field_names import FieldNames
from anonymous.eval.metrics.tag_to_metrics import AgentScenarioTags
from anonymous.eval.reporting.renderers.markdown.citation_links import (
    link_review_citations,
)
from anonymous.eval.reporting.renderers.markdown.markdown_constants import (
    FONT_WRAPPER_DIV,
    REVIEWS_DIR_NAME,
)
from anonymous.eval.reporting.renderers.markdown.markdown_utils import (
    json_code_block,
    ordered_unique,
    parse_fraction_string,
    render_kv_list,
)

LOG = logging.getLogger(__name__)

__all__ = ["json_eval_report_to_markdown", "convert_file", "render_report", "main"]


# Top-level report keys that are treated as metadata.
_DATASET_REL_PATH_KEY = "dataset rel path"
_TIME_OF_CREATION_KEY = "time of creation"
_SCENARIO_TAG_KEY = "scenario tag"
_RUN_NAME_KEY = "run name"
_DATASET_CONFIG_HASH_KEY = "dataset_config_hash"
_MODEL_INFO_KEY = "model_info"
_PLUGIN_HASH_KEY = "plugin_hash"
_LAUNCH_ARGS_KEY = "launch args"
_LANGUAGE_KEY = "language"
_JUDGE_KEY = "judge"
_EVALUATION_PRICE_KEY = "evaluation price"
_IDEA_DUMPS_PATH_KEY = "path to IDEA dumps"

_META_KEYS = {
    _DATASET_REL_PATH_KEY,
    _TIME_OF_CREATION_KEY,
    _SCENARIO_TAG_KEY,
    _RUN_NAME_KEY,
    _DATASET_CONFIG_HASH_KEY,
    _MODEL_INFO_KEY,
    _PLUGIN_HASH_KEY,
    _LAUNCH_ARGS_KEY,
    _LANGUAGE_KEY,
    _JUDGE_KEY,
    _EVALUATION_PRICE_KEY,
    _IDEA_DUMPS_PATH_KEY,
}


# Keys inside metric aggregated sections.
_SCORE_MEAN_KEY = "score mean"
_LLM_REVIEW_KEY = "llm review"
_CHATS_REVIEWED_KEY = "chats reviewed"


# Misc keys.
_TLDR_KEY = "TLDR"

_RESP_QTL_KEY = "10 / 50 / 80 / 100 response level qtl"
_CHAT_QTL_KEY = "10 / 50 / 80 / 100 chat level qtl"


_TOOL_CALLS_GENERAL_KEYS = [
    FieldNames.TOOL_CALL_COUNT_REPORT,
    FieldNames.TOOL_CALLS_PER_CHAT_MEAN,
    FieldNames.TOOL_CALLS_IN_PARALLEL,
]


_SUMMARY_BLOCK_RE = re.compile(
    r"<Summary>\s*(?P<summary>.*?)\s*</Summary>", re.DOTALL | re.IGNORECASE
)
_SUMMARY_OPEN_RE = re.compile(r"<Summary>\s*(?P<summary>.*)", re.DOTALL | re.IGNORECASE)
_ANALYSIS_BLOCK_RE = re.compile(
    r"<Analysis>.*?(?:</Analysis>|\Z)", re.DOTALL | re.IGNORECASE
)


def _extract_review_summary(review: str) -> str:
    """Return the Stage-2 `<Summary>` block.

    The judge prompt asks for `<Analysis>...</Analysis>` followed by
    `<Summary>...</Summary>`, but models occasionally drop the closing
    `</Summary>` tag or skip the `<Summary>` block entirely. This helper
    is tolerant of both cases so the rendered Markdown never falls back
    to the raw Stage-1 proof dump.
    """
    if not review:
        return ""

    match = _SUMMARY_BLOCK_RE.search(review)
    if match is not None:
        return match.group("summary").strip()

    open_match = _SUMMARY_OPEN_RE.search(review)
    if open_match is not None:
        # Closing tag missing: take everything after `<Summary>` to end,
        # stripping any stray closing analysis tag.
        tail = open_match.group("summary")
        tail = re.sub(r"</Analysis>\s*$", "", tail, flags=re.IGNORECASE).strip()
        return tail

    # No `<Summary>` at all: drop the Stage-1 `<Analysis>` block so we
    # don't render the raw proof table as the user-facing review.
    stripped = _ANALYSIS_BLOCK_RE.sub("", review).strip()
    return stripped or review.strip()


def _detect_metric_sections(report: Mapping[str, Any]) -> list[str]:
    """Return metric names that look like aggregated judge sections."""

    names: list[str] = []

    # Prefer known metrics order (stable across tags).
    known = [m.get_name() for m in AgentScenarioTags.get_all_llm_judge_metrics()]

    for name in known:
        if name in report and isinstance(report.get(name), Mapping):
            names.append(name)

    # Also include any other sections with an `llm review` key.
    for k, v in report.items():
        if k in names:
            continue
        if isinstance(v, Mapping) and _LLM_REVIEW_KEY in v and _CHATS_REVIEWED_KEY in v:
            names.append(str(k))

    return ordered_unique(names)


def _append_h2(lines: list[str], title: str, *, leading_blank: bool = True) -> None:
    if leading_blank:
        lines.append("")
    lines.append(f"## {title}")
    lines.append("")


def _render_tool_success_rates_table(
    lines: list[str], tool_rates: Mapping[str, Any]
) -> None:
    if not tool_rates:
        return

    _append_h2(lines, "Tool call success rates")
    lines.append("| Tool | successes/total | success rate |")
    lines.append("| --- | --- | --- |")

    for tool_name, raw in tool_rates.items():
        frac = parse_fraction_string(str(raw))
        if frac is None:
            lines.append(f"| {tool_name} | `{raw}` | -- |")
            continue

        succ, total = frac
        rate = (succ / total) if total > 0 else 0.0
        lines.append(f"| {tool_name} | `{succ}/{total}` | `{rate:.3f}` |")

    lines.append("")


def _append_tldr(lines: list[str], report: Mapping[str, Any]) -> None:
    _append_h2(lines, "TLDR", leading_blank=False)

    tldr_text = report.get(_TLDR_KEY)
    lines.append(str(tldr_text).strip() if tldr_text else "N/A")
    lines.append("")


def _append_number_of_points(lines: list[str], report: Mapping[str, Any]) -> None:
    chats_count = report.get(FieldNames.NUM_CHATS)
    scenarios_count = report.get(FieldNames.NUM_AGENT_SCENARIOS)
    if chats_count is None and scenarios_count is None:
        return

    _append_h2(lines, "number_of_points")

    if chats_count is not None:
        lines.append(f"- chats_count: `{chats_count}`")
    if scenarios_count is not None:
        lines.append(f"- agent_scenarios_count (tasks): `{scenarios_count}`")


def _append_formal_verification(lines: list[str], report: Mapping[str, Any]) -> None:
    fv = report.get(FieldNames.FORMAL_VERIFICATION_RESULT)
    fv_rate = report.get(FieldNames.FORMAL_VERIFICATION_SUCCESS_RATE)
    if fv is None and fv_rate is None:
        return

    _append_h2(lines, FieldNames.FORMAL_VERIFICATION_RESULT)

    fv_value = None
    if isinstance(fv, Mapping) and "total" in fv:
        fv_value = fv.get("total")
    elif fv is not None:
        fv_value = fv

    if fv_value is not None:
        lines.append(f"- value: `{fv_value}`")
    if fv_rate is not None:
        lines.append(f"- success rate: `{fv_rate}`")


def _append_termination_reason(lines: list[str], report: Mapping[str, Any]) -> None:
    term = report.get(FieldNames.TERMINATION_REASON)
    if not isinstance(term, Mapping) or not term:
        return

    _append_h2(lines, FieldNames.TERMINATION_REASON)

    for k, v in sorted(term.items(), key=lambda kv: (-int(kv[1]), str(kv[0]))):
        lines.append(f"- {k}: `{v}`")


def _split_remaining_sections(
    *, report: Mapping[str, Any], metric_names: list[str]
) -> tuple[dict[str, Any], dict[str, Any], Any, Any, Any]:
    """Return remaining sections + extracted blocks to show closer to the end."""

    remaining: dict[str, Any] = {}

    for k, v in report.items():
        if k in _META_KEYS:
            continue
        if k in metric_names:
            continue
        if k in {
            _TLDR_KEY,
            FieldNames.TERMINATION_REASON,
            FieldNames.TOOL_CALLS_SUCCESS_RATES,
            FieldNames.FORMAL_VERIFICATION_RESULT,
            FieldNames.FORMAL_VERIFICATION_SUCCESS_RATE,
            FieldNames.NUM_CHATS,
            FieldNames.NUM_AGENT_SCENARIOS,
        }:
            continue
        remaining[str(k)] = v

    tool_calls_general_stats = {
        k: remaining.pop(k) for k in _TOOL_CALLS_GENERAL_KEYS if k in remaining
    }

    agent_time = remaining.pop(FieldNames.AGENT_TIME_PER_INTERACTION, None)
    agent_price = remaining.pop(FieldNames.AGENT_PRICE_PER_INTERACTION, None)
    gen_tokens_to_seconds_ratio = remaining.pop(
        FieldNames.GEN_TOKENS_TO_SECONDS_RATIO, None
    )

    return (
        remaining,
        tool_calls_general_stats,
        agent_time,
        agent_price,
        gen_tokens_to_seconds_ratio,
    )


def _append_generic_sections(lines: list[str], sections: Mapping[str, Any]) -> None:
    for key in sorted(sections.keys()):
        value = sections.get(key)
        if value is None:
            continue

        _append_h2(lines, str(key))

        if isinstance(value, (dict, list)):
            lines.append("```json")
            lines.append(json_code_block(value))
            lines.append("```")
        else:
            lines.append(f"- value: `{value}`")


def _append_tools_call_general_stats(
    lines: list[str], stats: Mapping[str, Any]
) -> None:
    if not stats:
        return

    _append_h2(lines, "tools_call_general_stats")

    for k in _TOOL_CALLS_GENERAL_KEYS:
        if k in stats:
            lines.append(f"- {k}: `{stats[k]}`")


def _append_agent_time_price_section(lines: list[str], name: str, payload: Any) -> None:
    if not isinstance(payload, Mapping):
        return

    _append_h2(lines, name)

    lines.append(f"- total: `{payload.get('total')}`")

    resp_qtl = payload.get(_RESP_QTL_KEY)
    if resp_qtl is not None:
        lines.append(f"- response qtl (10/50/80/100): `{resp_qtl}`")

    chat_qtl = payload.get(_CHAT_QTL_KEY)
    if chat_qtl is not None:
        lines.append(f"- chat qtl (10/50/80/100): `{chat_qtl}`")


def _append_judge_metrics(
    *,
    lines: list[str],
    report: Mapping[str, Any],
    metric_names: list[str],
    reviews_rel_dir: str,
) -> None:
    for metric_name in metric_names:
        section = report.get(metric_name)
        if not isinstance(section, Mapping):
            continue

        _append_h2(lines, f"{metric_name}_Judge")

        score_mean = section.get(_SCORE_MEAN_KEY)
        if score_mean is not None:
            lines.append(f"- score mean: `{score_mean}`")
            lines.append("")

        llm_review = section.get(_LLM_REVIEW_KEY)
        if llm_review:
            chats_reviewed = section.get(_CHATS_REVIEWED_KEY)
            linked = link_review_citations(
                review=_extract_review_summary(str(llm_review)),
                chats_reviewed=chats_reviewed
                if isinstance(chats_reviewed, list)
                else None,
                metric_dir=str(metric_name),
                reviews_rel_dir=reviews_rel_dir,
                comparisons_rel_dir=None,
                section_name=str(metric_name),
                log=LOG,
            )
            lines.append("**Review**")
            lines.append("")
            lines.append(linked)


def _append_metadata(lines: list[str], report: Mapping[str, Any]) -> None:
    meta = {k: report.get(k) for k in _META_KEYS if report.get(k) is not None}
    if not meta:
        return

    _append_h2(lines, "Metadata")

    render_kv_list(
        lines=lines,
        mapping=meta,
        preferred_order=[
            _RUN_NAME_KEY,
            _SCENARIO_TAG_KEY,
            _LANGUAGE_KEY,
            _MODEL_INFO_KEY,
            _PLUGIN_HASH_KEY,
            _JUDGE_KEY,
            _EVALUATION_PRICE_KEY,
            _TIME_OF_CREATION_KEY,
            _DATASET_REL_PATH_KEY,
            _DATASET_CONFIG_HASH_KEY,
            _IDEA_DUMPS_PATH_KEY,
            _LAUNCH_ARGS_KEY,
        ],
    )


def json_eval_report_to_markdown(
    report: Mapping[str, Any],
    title: str,
    *,
    reviews_rel_dir: str = f"../{REVIEWS_DIR_NAME}",
) -> str:
    lines: list[str] = [FONT_WRAPPER_DIV, "", f"# {title}", ""]

    metric_names = _detect_metric_sections(report)

    _append_tldr(lines, report)
    _append_number_of_points(lines, report)
    _append_formal_verification(lines, report)
    _append_termination_reason(lines, report)

    (
        remaining,
        tool_calls_general_stats,
        agent_time,
        agent_price,
        gen_tokens_to_seconds_ratio,
    ) = _split_remaining_sections(report=report, metric_names=metric_names)

    _append_generic_sections(lines, remaining)

    tool_rates = report.get(FieldNames.TOOL_CALLS_SUCCESS_RATES)
    if isinstance(tool_rates, Mapping):
        _render_tool_success_rates_table(lines, tool_rates)

    _append_judge_metrics(
        lines=lines,
        report=report,
        metric_names=metric_names,
        reviews_rel_dir=reviews_rel_dir,
    )

    _append_h2(lines, FieldNames.GEN_TOKENS_TO_SECONDS_RATIO)
    lines.append(f"- value: `{gen_tokens_to_seconds_ratio}`")

    _append_tools_call_general_stats(lines, tool_calls_general_stats)
    _append_agent_time_price_section(
        lines, FieldNames.AGENT_TIME_PER_INTERACTION, agent_time
    )
    _append_agent_time_price_section(
        lines, FieldNames.AGENT_PRICE_PER_INTERACTION, agent_price
    )

    _append_metadata(lines, report)

    lines.append("</div>")
    return "\n".join(lines).rstrip() + "\n"


def render_report(
    *,
    report: Mapping[str, Any],
    title: str,
    out_path: Path,
    reviews_rel_dir: str,
) -> Path:
    md = json_eval_report_to_markdown(report, title, reviews_rel_dir=reviews_rel_dir)
    out_path.write_text(md, encoding="utf-8")
    return out_path


def convert_file(
    path: Path,
    *,
    out_path: Path | None = None,
    reviews_rel_dir: str = f"../{REVIEWS_DIR_NAME}",
) -> Path:
    data = read_json(path)

    if not isinstance(data, dict):
        raise ValueError("Expected top-level JSON object (dict) for eval report")

    scenario_tag = data.get(_SCENARIO_TAG_KEY)
    title = (
        str(scenario_tag).strip()
        if isinstance(scenario_tag, str) and scenario_tag.strip()
        else path.stem.replace("_", " ")
    )

    resolved_out_path = out_path or path.with_suffix(".md")
    return render_report(
        report=data,
        title=title,
        out_path=resolved_out_path,
        reviews_rel_dir=reviews_rel_dir,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert benchmark eval (single-run) JSON reports to Markdown."
    )
    parser.add_argument("paths", nargs="+", help="Report JSON files to convert")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    for raw in args.paths:
        p = Path(raw)
        if not p.is_file():
            LOG.warning("[skip] not a file: %s", p)
            continue
        try:
            out = convert_file(p)
            LOG.info("[ok] %s -> %s", p, out)
        except Exception as e:  # noqa: BLE001
            LOG.exception("[error] %s: %s", p, e)


if __name__ == "__main__":  # pragma: no cover
    main()

"""Convert benchmark *comparison summary* JSON reports into readable Markdown.

This is the public entrypoint module.
Implementation details live in sibling modules:
- `comparison_constants`
- `comparison_formatting`
- `comparison_sections`
- `comparison_tables`
"""

import argparse
import logging
from pathlib import Path
from typing import Any, List

from agent_lens.eval.common.json_io import read_json

from agent_lens.eval.reporting.renderers.markdown.comparison_constants import (
    COMPARISONS_DIR_NAME,
)
from agent_lens.eval.reporting.renderers.markdown.markdown_constants import (
    FONT_WRAPPER_DIV,
    safe_task_file_name,
)
from agent_lens.eval.reporting.renderers.markdown.comparison_sections import (
    infer_total_points,
    render_metadata,
    render_named_section,
    render_termination_reasons,
    render_tldr,
    split_report_objects,
)
from agent_lens.eval.reporting.renderers.markdown.comparison_tables import (
    render_inference_metrics_table,
    render_tool_success_rates_table,
)

LOG = logging.getLogger(__name__)

__all__ = [
    "FONT_WRAPPER_DIV",
    "COMPARISONS_DIR_NAME",
    "safe_task_file_name",
    "json_report_to_markdown",
    "convert_file",
    "main",
]


def json_report_to_markdown(data: Any, title: str) -> str:
    if not isinstance(data, list):
        raise ValueError("Expected top-level JSON array of objects")

    total_points = infer_total_points(data)
    total_points_text = str(total_points) if total_points is not None else "Unknown"

    (
        tldr_text,
        success_rate_objs,
        inference_objs,
        regular_objs,
        formal_verification_obj,
        termination_reason_obj,
        metadata_obj,
    ) = split_report_objects(data)

    lines: List[str] = [
        FONT_WRAPPER_DIV,
        "",
        f"# {title}",
        "",
    ]

    render_tldr(lines, tldr_text)
    lines.append(f"### Total number of points (chats): {total_points_text}")

    if formal_verification_obj is not None:
        render_named_section(lines, formal_verification_obj)

    render_termination_reasons(lines, termination_reason_obj)

    for obj in regular_objs:
        render_named_section(lines, obj)

    render_inference_metrics_table(lines, inference_objs)
    render_tool_success_rates_table(lines, success_rate_objs)
    render_metadata(lines, metadata_obj)

    lines.append("</div>")
    return "\n".join(lines).rstrip() + "\n"


def convert_file(path: Path) -> Path:
    data = read_json(path)

    title = path.stem.replace("_", " ")
    md = json_report_to_markdown(data, title)

    out_path = path.with_suffix(".md")
    with out_path.open("w", encoding="utf-8") as f:
        f.write(md)

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert benchmark comparison summary JSON reports to Markdown."
    )
    parser.add_argument("paths", nargs="+", help="JSON report files to convert")
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

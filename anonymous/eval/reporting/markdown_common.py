"""Shared helpers for Markdown generation.

Used by both eval and SBS Markdown dumpers.
"""

import json
from typing import Any, List, Mapping

from anonymous.eval.common.trajectory import get_last_simulator_request_messages
from anonymous.eval.reporting.renderers.markdown.markdown_utils import (
    render_untrusted_text,
)


def dump_full_trajectory(point: Mapping[str, Any]) -> str:
    msgs = get_last_simulator_request_messages(dict(point))
    return json.dumps(msgs, ensure_ascii=False, indent=2)


def append_details_block(*, lines: List[str], title: str, body: str) -> None:
    lines.append("<details>")
    lines.append(f"<summary><strong>{title}</strong></summary>")
    lines.append("")

    render_untrusted_text(lines=lines, text=body)

    lines.append("")
    lines.append("</details>")
    lines.append("")

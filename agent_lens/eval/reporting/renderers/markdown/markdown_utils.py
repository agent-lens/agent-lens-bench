"""Markdown rendering helpers for benchmark artifacts.

Judge text is treated as untrusted and rendered in a `<pre>` block.
Optional `<code_diffs>...</code_diffs>` sections are rendered as fenced code.
"""

import html
import json
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional

from agent_lens.eval.common.paths import sanitize_path_component

DEFAULT_FENCE = "```"
CODE_DIFFS_START_TAG = "<code_diffs>"
CODE_DIFFS_END_TAG = "</code_diffs>"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_metric_dir_name(metric_name: str) -> str:
    """Sanitize a metric name so it can be safely used as a directory name."""
    return sanitize_path_component(metric_name).strip() or "unnamed_metric"


def normalize_linebreaks_in_text_block(text: str) -> str:
    """Make long serialized text (with literal "\\n") more readable."""
    return text.replace("\\n", "\n").replace("\\n", "\n")


def choose_fence(content: str, base_fence: str = DEFAULT_FENCE) -> str:
    """Pick a backtick fence that cannot be closed by `content`."""

    longest = 0
    current = 0
    for ch in content:
        if ch == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    fence_len = max(len(base_fence), longest + 1)
    return "`" * fence_len


def render_fenced_code_block(*, lines: List[str], lang: str, content: str) -> None:
    fence = choose_fence(content)
    lines.append(f"{fence}{lang}")
    lines.extend(content.splitlines())
    lines.append(fence)


def append_pre_block(lines: List[str], text: str) -> None:
    escaped = html.escape(text)
    lines.append(
        '<pre style="white-space: pre-wrap; overflow-x: auto;">' + escaped + "</pre>"
    )


def render_untrusted_text(
    *,
    lines: List[str],
    text: str,
    code_diffs_lang: str = "diff",
) -> None:
    """Render text safely, with optional <code_diffs> blocks as fenced code."""

    if not text:
        lines.append("N/A")
        return

    norm = normalize_linebreaks_in_text_block(text)

    while CODE_DIFFS_START_TAG in norm and CODE_DIFFS_END_TAG in norm:
        before, rest = norm.split(CODE_DIFFS_START_TAG, 1)
        code_section, norm = rest.split(CODE_DIFFS_END_TAG, 1)

        if before.strip():
            append_pre_block(lines, before)
            lines.append("")

        lines.append(CODE_DIFFS_START_TAG)
        render_fenced_code_block(
            lines=lines,
            lang=code_diffs_lang,
            content=code_section.strip("\n"),
        )
        lines.append(CODE_DIFFS_END_TAG)
        lines.append("")

    if norm.strip():
        append_pre_block(lines, norm)


def json_code_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def parse_fraction_string(value: str) -> Optional[tuple[int, int]]:
    """Parse "<int>/<int>" into (num, den)."""

    if not isinstance(value, str) or "/" not in value:
        return None

    num_s, den_s = value.split("/", 1)
    try:
        return int(num_s.strip()), int(den_s.strip())
    except ValueError:
        return None


def ordered_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def render_json_value(*, lines: List[str], key: str, value: Any) -> None:
    if value is None:
        return

    if isinstance(value, (dict, list)):
        lines.append(f"- {key}:")
        lines.append("```json")
        lines.append(json_code_block(value))
        lines.append("```")
    else:
        lines.append(f"- {key}: `{value}`")


def render_kv_list(
    *, lines: List[str], mapping: Mapping[str, Any], preferred_order: list[str]
) -> None:
    keys = [k for k in mapping.keys()]

    ordered: list[str] = []
    for k in preferred_order:
        if k in mapping:
            ordered.append(k)

    for k in sorted(keys):
        if k not in ordered:
            ordered.append(k)

    for k in ordered:
        render_json_value(lines=lines, key=str(k), value=mapping.get(k))

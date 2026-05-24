from pathlib import Path
from typing import Any, Mapping

from agent_lens.eval.data_framework.field_names import FieldNames
from agent_lens.eval.data_framework.io.message_dumps import (
    iter_simulated_user_messages,
    read_agent_chat_dump,
    read_tool_calls_dump,
)


def augment_point_with_dumps(
    *,
    dump_root: Path,
    point: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach per-point dumps (messages, agent chat, tool calls) to the summary dict."""

    point_dict = dict(point)
    point_dir = dump_root / point_dict[FieldNames.MESSAGE_PATH]

    point_dict.update(
        {
            FieldNames.ALL_LLM_CALLS: iter_simulated_user_messages(point_dir),
            FieldNames.AGENT_CHAT_DUMP: read_agent_chat_dump(point_dir),
            FieldNames.TOOL_CALLS_DUMP: read_tool_calls_dump(point_dir),
        }
    )
    return point_dict

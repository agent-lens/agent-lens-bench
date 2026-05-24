import logging
from pathlib import Path
from typing import Any

from anonymous.eval.common.json_io import read_json
from anonymous.eval.data_framework.field_names import FieldNames

LOG = logging.getLogger(__name__)

SIMULATED_USER_MARKER = "simulated_user"
AGENT_CHAT_DUMP_NAME = "agent_chat_dump.json"
TOOL_CALLS_DUMP_NAME = "tool_calls_dump.json"


def iter_simulated_user_messages(point_dir: Path) -> list[dict[str, Any]]:
    """Read all `*simulated_user*.json` files under a point directory.

    Note: dataset points use `FieldNames.MESSAGE_PATH` for the *point directory*.
    Here we store per-message JSON file location under `FieldNames.MESSAGE_DUMP_PATH`.
    """

    if not point_dir.exists():
        LOG.debug("Point dir not found: %s", point_dir)
        return []

    message_dumps: list[dict[str, Any]] = []
    for msg_path in sorted(point_dir.glob("*.json")):
        if SIMULATED_USER_MARKER not in msg_path.name:
            continue

        try:
            msg = read_json(msg_path)
        except ValueError:
            LOG.error("Failed to parse %s", msg_path)
            continue

        if not isinstance(msg, dict):
            LOG.error("Message dump is not an object: %s", msg_path)
            continue

        msg_with_path = dict(msg)
        msg_with_path[FieldNames.MESSAGE_DUMP_PATH] = str(msg_path)
        message_dumps.append(msg_with_path)

    return message_dumps


def _read_optional_json_dict(path: Path, *, log_name: str) -> dict[str, Any]:
    try:
        data = read_json(path)
    except FileNotFoundError:
        LOG.debug("%s not found at %s; using empty dict", log_name, path.parent)
        return {}
    except ValueError:
        LOG.error("Failed to parse %s; using empty dict", path)
        return {}

    if not isinstance(data, dict):
        LOG.error("%s is not a JSON object at %s; using empty dict", log_name, path)
        return {}

    return data


def read_agent_chat_dump(point_dir: Path) -> dict[str, Any]:
    return _read_optional_json_dict(
        point_dir / AGENT_CHAT_DUMP_NAME, log_name=AGENT_CHAT_DUMP_NAME
    )


def read_tool_calls_dump(point_dir: Path) -> dict[str, Any]:
    return _read_optional_json_dict(
        point_dir / TOOL_CALLS_DUMP_NAME, log_name=TOOL_CALLS_DUMP_NAME
    )

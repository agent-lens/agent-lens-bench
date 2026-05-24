from typing import Any, Optional

from anonymous.eval.data_framework.field_names import FieldNames


def get_last_simulator_call(point: dict[str, Any]) -> Optional[dict[str, Any]]:
    calls = point.get(FieldNames.ALL_LLM_CALLS)
    if not isinstance(calls, list) or not calls:
        return None

    for call in reversed(calls):
        if call.get(FieldNames.RESPONSE_ROLE) == FieldNames.SIMULATOR_RESPONSE_TYPE:
            return call
    return None


def get_last_simulator_request_messages(
    point: dict[str, Any], *, drop_system: bool = True
) -> list[dict[str, Any]]:
    """Return the full transcript list (role/content dicts) used in judge prompts.

    Strict: raises if the dataset point has no simulator call / request.
    Also fails fast if MESSAGE_PATH is missing.
    """

    message_path = point[FieldNames.MESSAGE_PATH]

    call = get_last_simulator_call(point)
    assert call is not None, f"No simulator call found for point at {message_path}"

    req = call.get("request")

    msgs: list[dict[str, Any]] = []
    for m in req:
        if (
            drop_system
            and m.get(FieldNames.MESSAGE_ROLE) == FieldNames.SYSTEM_MESSAGE_TYPE
        ):
            continue
        msgs.append(m)

    return msgs

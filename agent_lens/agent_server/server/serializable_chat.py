from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID, uuid4

from .models import Message, MessageKind, ToolCall, ToolResponse

_USER_MESSAGE_TYPE = (
    "UserMessage"
)
_AGENT_TURN_TYPE = "AgentTurn"
_TOOL_MESSAGE_TYPE = "ToolMessage"


def build_serializable_chat(
    session_id: UUID, messages: Iterable[Message], agent_config: str
) -> dict[str, Any]:
    serialized_messages = serialize_messages(messages)

    return {
        "chatUuid": str(session_id),
        "agentConfig": agent_config,
        "messages": serialized_messages,
    }


def build_serializable_chat_from_claude_raw(
    session_id: UUID, raw_dumps: Iterable[tuple[object, datetime]], agent_config: str
) -> dict[str, Any]:
    serialized_messages = serialize_claude_raw_messages(raw_dumps)

    return {
        "chatUuid": str(session_id),
        "agentConfig": agent_config,
        "messages": serialized_messages,
    }


def serialize_messages(messages: Iterable[Message]) -> list[dict[str, Any]]:
    default_ts = datetime.now(timezone.utc)
    serialized: list[dict[str, Any]] = []
    for message in messages:
        serialized.extend(_serialize_message(message, default_ts))
    return serialized


def serialize_claude_raw_messages(
    raw_dumps: Iterable[tuple[object, datetime]]
) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for payload, created_at in raw_dumps:
        serialized.extend(_serialize_claude_payload(payload, created_at))
    return serialized


def _serialize_message(
    message: Message, default_ts: datetime
) -> list[dict[str, Any]]:
    created_at = _format_timestamp(message.timestamp, default_ts)

    if message.kind == MessageKind.USER:
        return [
            {
                "type": _USER_MESSAGE_TYPE,
                "uuid": str(message.id),
                "createdAt": created_at,
                "prompt": message.content,
                "attachments": [],
            }
        ]

    if message.kind == MessageKind.ASSISTANT:
        return [
            {
                "type": _AGENT_TURN_TYPE,
                "uuid": str(message.id),
                "createdAt": created_at,
                "response": message.content,
                "reasoning": message.reasoning or "",
                "toolCalls": _serialize_tool_calls(
                    message.toolCalls, message.toolResponses, created_at
                ),
                "properties": None,
            }
        ]

    if message.kind == MessageKind.TOOL:
        return _serialize_tool_message(message, created_at)

    return [
        {
            "type": _AGENT_TURN_TYPE,
            "uuid": str(message.id),
            "createdAt": created_at,
            "response": message.content,
            "reasoning": message.reasoning or "",
            "toolCalls": _serialize_tool_calls(
                message.toolCalls, message.toolResponses, created_at
            ),
            "properties": {"system": "true"},
        }
    ]


def _serialize_claude_payload(
    payload: object, created_at: datetime
) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return _serialize_claude_dict(payload, created_at)
    if isinstance(payload, list):
        return _serialize_claude_list(payload, created_at)
    return []


def _serialize_claude_dict(payload: dict, created_at: datetime) -> list[dict[str, Any]]:
    result = payload.get("result")
    if not isinstance(result, str):
        return []
    return [
        {
            "type": _AGENT_TURN_TYPE,
            "uuid": str(uuid4()),
            "createdAt": _format_datetime(created_at),
            "response": result,
            "reasoning": "",
            "toolCalls": [],
            "properties": None,
        }
    ]


def _serialize_claude_list(
    payload: list[object], created_at: datetime
) -> list[dict[str, Any]]:
    created_at_str = _format_datetime(created_at)
    messages: list[dict[str, Any]] = []

    for item in payload:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "system":
            messages.append(
                {
                    "type": _AGENT_TURN_TYPE,
                    "uuid": str(_parse_uuid(item.get("uuid"))),
                    "createdAt": created_at_str,
                    "response": _json_dumps(item),
                    "reasoning": "",
                    "toolCalls": [],
                    "properties": {"system": "true"},
                }
            )
            continue
        if item_type == "assistant":
            messages.append(_serialize_claude_assistant(item, created_at_str))
            continue
        if item_type == "user":
            messages.extend(_serialize_claude_user(item, created_at_str))
            continue

    return messages


def _serialize_claude_assistant(item: dict, created_at: str) -> dict[str, Any]:
    message = item.get("message")
    content_parts = message.get("content") if isinstance(message, dict) else None
    text_chunks: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    if isinstance(content_parts, list):
        for part in content_parts:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str) and text:
                    text_chunks.append(text)
            elif part.get("type") == "tool_use":
                tool_use_id = part.get("id")
                if not isinstance(tool_use_id, str) or not tool_use_id:
                    tool_use_id = uuid4().hex
                tool_calls.append(
                    {
                        "uuid": tool_use_id,
                        "createdAt": created_at,
                        "toolCall": {
                            "id": tool_use_id,
                            "name": part.get("name"),
                            "input": part.get("input"),
                        },
                        "toolResponse": None,
                    }
                )

    return {
        "type": _AGENT_TURN_TYPE,
        "uuid": str(_parse_uuid(item.get("uuid"))),
        "createdAt": created_at,
        "response": "\n".join(text_chunks),
        "reasoning": "",
        "toolCalls": tool_calls,
        "properties": None,
    }


def _serialize_claude_user(item: dict, created_at: str) -> list[dict[str, Any]]:
    message = item.get("message")
    content_parts = message.get("content") if isinstance(message, dict) else None
    text_chunks: list[str] = []
    tool_messages: list[dict[str, Any]] = []

    if isinstance(content_parts, list):
        for part in content_parts:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type == "text":
                text = part.get("text")
                if isinstance(text, str) and text:
                    text_chunks.append(text)
            elif part_type == "tool_result":
                tool_messages.append(
                    _serialize_claude_tool_result(item, part, created_at)
                )

    messages: list[dict[str, Any]] = []
    if text_chunks:
        messages.append(
            {
                "type": _USER_MESSAGE_TYPE,
                "uuid": str(_parse_uuid(item.get("uuid"))),
                "createdAt": created_at,
                "prompt": "\n".join(text_chunks),
                "attachments": [],
            }
        )

    messages.extend(tool_messages)
    return messages


def _serialize_claude_tool_result(
    item: dict, part: dict, created_at: str
) -> dict[str, Any]:
    tool_use_id = part.get("tool_use_id")
    if not isinstance(tool_use_id, str) or not tool_use_id:
        tool_use_id = uuid4().hex
    tool_call = {"id": tool_use_id, "name": part.get("name")}
    tool_response = {
        "content": part.get("content"),
        "tool_use_result": item.get("tool_use_result"),
        "success": not bool(part.get("is_error", False)),
    }
    return {
        "type": _TOOL_MESSAGE_TYPE,
        "uuid": tool_use_id,
        "createdAt": created_at,
        "toolCall": tool_call,
        "toolResponse": tool_response,
    }


def _serialize_tool_message(
    message: Message, created_at: str
) -> list[dict[str, Any]]:
    if message.toolResponses:
        return [
            _tool_message_from_response(response, created_at)
            for response in message.toolResponses
        ]

    parsed_content = _parse_json_or_text(message.content)
    return [
        {
            "type": _TOOL_MESSAGE_TYPE,
            "uuid": str(message.id),
            "createdAt": created_at,
            "toolCall": {"content": parsed_content},
            "toolResponse": {"content": parsed_content},
        }
    ]


def _tool_message_from_response(
    response: ToolResponse, created_at: str
) -> dict[str, Any]:
    return {
        "type": _TOOL_MESSAGE_TYPE,
        "uuid": response.id,
        "createdAt": created_at,
        "toolCall": {"id": response.id, "name": response.name},
        "toolResponse": {"content": _parse_json_or_text(response.content)},
    }


def _serialize_tool_calls(
    tool_calls: list[ToolCall],
    tool_responses: list[ToolResponse],
    created_at: str,
) -> list[dict[str, Any]]:
    response_map = {response.id: response for response in tool_responses}
    serialized: list[dict[str, Any]] = []
    for call in tool_calls:
        response = response_map.get(call.id)
        serialized.append(
            {
                "uuid": call.id,
                "createdAt": created_at,
                "toolCall": {
                    "name": call.name,
                    "args": _parse_json_or_text(call.args),
                },
                "toolResponse": _serialize_tool_response(response),
            }
        )
    return serialized


def _serialize_tool_response(response: ToolResponse | None) -> dict[str, Any] | None:
    if response is None:
        return None
    return {
        "name": response.name,
        "content": _parse_json_or_text(response.content),
    }


def _format_timestamp(timestamp: int | None, default_ts: datetime) -> str:
    if timestamp is None:
        dt = default_ts
    else:
        dt = _timestamp_to_datetime(timestamp)
    return dt.isoformat().replace("+00:00", "Z")


def _format_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_to_datetime(timestamp: int) -> datetime:
    if timestamp >= 1_000_000_000_000:
        seconds = timestamp / 1000.0
    else:
        seconds = float(timestamp)
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def _parse_json_or_text(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _parse_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            pass
    return uuid4()


def _json_dumps(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=True)
    except (TypeError, ValueError):
        return str(value)

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException

from .models import McpServer, Message, MessageKind, ToolCall, ToolResponse

CLAUDE_LOG_TAG = "[CLAUDE-CLI]"
CLAUDE_DUMPS_DIR_ENV = "CLAUDE_DUMPS_DIR"
MAX_CLI_ERROR_TEXT = 4000


def extract_claude_messages(payload: object) -> tuple[list[Message], str]:
    if isinstance(payload, dict):
        return _extract_from_dict(payload)

    if isinstance(payload, list):
        return _extract_from_list(payload)

    raise HTTPException(status_code=500, detail="Claude CLI response invalid format")


def extract_total_cost_usd(payload: object) -> Optional[float]:
    if not isinstance(payload, list) or not payload:
        return None

    last = payload[-1]
    if not isinstance(last, dict):
        return None

    value = last.get("total_cost_usd")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _extract_from_dict(payload: dict) -> tuple[list[Message], str]:
    result_text = payload.get("result")
    session_id = payload.get("session_id")
    if not isinstance(result_text, str) or not isinstance(session_id, str):
        raise HTTPException(
            status_code=500, detail="Claude CLI response missing fields"
        )
    message = Message(
        id=uuid4(),
        timestamp=None,
        kind=MessageKind.ASSISTANT,
        content=result_text,
        reasoning=None,
        toolCalls=[],
        toolResponses=[],
    )
    return [message], session_id


def _extract_from_list(payload: list[object]) -> tuple[list[Message], str]:
    messages: list[Message] = []
    session_id: Optional[str] = None
    result_text: Optional[str] = None
    tool_use_names: dict[str, str] = {}

    for item in payload:
        if not isinstance(item, dict):
            continue

        if session_id is None:
            value = item.get("session_id")
            if isinstance(value, str):
                session_id = value

        item_type = item.get("type")
        if item_type == "result":
            value = item.get("result")
            if isinstance(value, str):
                result_text = value
            continue

        message_id = _parse_message_id(item.get("uuid"))
        if item_type == "system":
            messages.append(
                Message(
                    id=message_id,
                    timestamp=None,
                    kind=MessageKind.SYSTEM,
                    content=json.dumps(item, ensure_ascii=True),
                    reasoning=None,
                    toolCalls=[],
                    toolResponses=[],
                )
            )
            continue

        if item_type == "assistant":
            assistant_message, tool_names = _parse_assistant_message(message_id, item)
            # Claude may emit reasoning-only assistant events with no text/tool calls.
            # Skip them so getMessages returns only meaningful assistant outputs.
            if assistant_message.content.strip() or assistant_message.toolCalls:
                messages.append(assistant_message)
            tool_use_names.update(tool_names)
            continue

        if item_type == "user":
            messages.extend(_parse_user_message(message_id, item, tool_use_names))
            continue

    if session_id is None:
        raise HTTPException(
            status_code=500, detail="Claude CLI response missing session id"
        )

    if not messages and result_text is not None:
        messages.append(
            Message(
                id=uuid4(),
                timestamp=None,
                kind=MessageKind.ASSISTANT,
                content=result_text,
                reasoning=None,
                toolCalls=[],
                toolResponses=[],
            )
        )

    if not messages:
        raise HTTPException(
            status_code=500, detail="Claude CLI response missing messages"
        )

    return messages, session_id


def _parse_message_id(value: object) -> UUID:
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            pass
    return uuid4()


def _parse_assistant_message(
    message_id: UUID, item: dict
) -> tuple[Message, dict[str, str]]:
    message = item.get("message")
    content_parts = message.get("content") if isinstance(message, dict) else None
    text_chunks: list[str] = []
    tool_calls: list[ToolCall] = []
    tool_use_names: dict[str, str] = {}

    if isinstance(content_parts, list):
        for part in content_parts:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str) and text:
                    text_chunks.append(text)
            elif part.get("type") == "tool_use":
                tool_name = part.get("name")
                if not isinstance(tool_name, str) or not tool_name:
                    continue
                tool_use_id = part.get("id")
                if not isinstance(tool_use_id, str) or not tool_use_id:
                    tool_use_id = uuid4().hex
                tool_payload = {
                    "tool_use_id": tool_use_id,
                    "input": part.get("input"),
                }
                tool_calls.append(
                    ToolCall(
                        id=tool_use_id,
                        name=tool_name,
                        args=json.dumps(tool_payload, ensure_ascii=True),
                    )
                )
                tool_use_names[tool_use_id] = tool_name

    content = "\n".join(text_chunks)
    return (
        Message(
            id=message_id,
            timestamp=None,
            kind=MessageKind.ASSISTANT,
            content=content,
            reasoning=None,
            toolCalls=tool_calls,
            toolResponses=[],
        ),
        tool_use_names,
    )


def _parse_user_message(
    message_id: UUID, item: dict, tool_use_names: dict[str, str]
) -> list[Message]:
    message = item.get("message")
    content_parts = message.get("content") if isinstance(message, dict) else None
    text_chunks: list[str] = []
    tool_results: list[dict] = []
    tool_responses: list[ToolResponse] = []

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
                tool_results.append(part)
                tool_use_id = part.get("tool_use_id")
                if not isinstance(tool_use_id, str) or not tool_use_id:
                    tool_use_id = uuid4().hex
                tool_name = part.get("name")
                if not isinstance(tool_name, str) or not tool_name:
                    tool_name = tool_use_names.get(tool_use_id, "unknown")
                content = part.get("content")
                if isinstance(content, str):
                    tool_content = content
                else:
                    tool_content = json.dumps(content, ensure_ascii=True)
                success = not bool(part.get("is_error", False))
                tool_responses.append(
                    ToolResponse(
                        id=tool_use_id,
                        name=tool_name,
                        content=tool_content,
                        success=success,
                    )
                )

    messages: list[Message] = []
    if tool_results:
        content = json.dumps(
            tool_results if len(tool_results) > 1 else tool_results[0],
            ensure_ascii=True,
        )
        messages.append(
            Message(
                id=message_id,
                timestamp=None,
                kind=MessageKind.TOOL,
                content=content,
                reasoning=None,
                toolCalls=[],
                toolResponses=tool_responses,
            )
        )

    if text_chunks:
        messages.append(
            Message(
                id=message_id if not tool_results else uuid4(),
                timestamp=None,
                kind=MessageKind.USER,
                content="\n".join(text_chunks),
                reasoning=None,
                toolCalls=[],
                toolResponses=[],
            )
        )

    return messages


def run_claude(
    prompt: str,
    project_path: str,
    model_name: str,
    session_id: Optional[str],
    mcp_servers: dict[str, McpServer],
    timeout_millis: Optional[int],
) -> tuple[object, datetime, Path | None]:
    args = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--verbose",
        "--dangerously-skip-permissions",
    ]
    if model_name:
        args.extend(["--model", model_name])
    if session_id:
        args.extend(["--resume", session_id])
    if mcp_servers:
        mcp_config = {
            "mcpServers": {
                name: {
                    "type": server.type,
                    "url": server.url,
                    "headers": dict(server.headers),
                }
                for name, server in mcp_servers.items()
            }
        }
        args.extend(["--mcp-config", json.dumps(mcp_config, ensure_ascii=True)])

    timeout_seconds = None
    if timeout_millis is not None:
        timeout_seconds = max(timeout_millis / 1000.0, 0.001)

    try:
        result = subprocess.run(
            args,
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500, detail=f"Claude CLI not found: {exc}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise exc

    if result.returncode != 0:
        detail = _extract_cli_error_text(result)
        raise HTTPException(status_code=500, detail=detail)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raw = result.stdout.strip()
        suffix = ""
        if raw:
            preview = raw[:500]
            suffix = f"; raw output: {preview}"
        raise HTTPException(
            status_code=500, detail=f"Claude CLI returned invalid JSON{suffix}"
        ) from exc

    created_at, log_path = _persist_claude_output(payload)
    return payload, created_at, log_path


def _persist_claude_output(payload: object) -> tuple[datetime, Path | None]:
    log_dir = _resolve_dump_dir()
    created_at = datetime.now(timezone.utc)
    if log_dir is None:
        return created_at, None

    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = created_at.strftime("%Y%m%dT%H%M%SZ")
    filename = f"claude-{timestamp}-{uuid4().hex}.json"
    path = log_dir / filename
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
    return created_at, path


def _resolve_dump_dir() -> Path | None:
    configured = os.getenv(CLAUDE_DUMPS_DIR_ENV)
    if configured is None:
        return None

    configured = configured.strip()
    if not configured:
        return None

    return Path(configured)


def _extract_cli_error_text(result: subprocess.CompletedProcess[str]) -> str:
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    candidate = stderr or stdout
    if not candidate:
        return f"Claude CLI failed with exit code {result.returncode}"
    if len(candidate) > MAX_CLI_ERROR_TEXT:
        candidate = f"{candidate[:MAX_CLI_ERROR_TEXT]}... (truncated)"
    return f"Claude CLI failed with exit code {result.returncode}: {candidate}"

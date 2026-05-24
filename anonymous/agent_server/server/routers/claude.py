from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException

from ..claude_client import extract_claude_messages, extract_total_cost_usd, run_claude
from ..models import (
    ClaudeRawDump,
    ClaudeSessionData,
    GetMessagesRequest,
    GetChatDumpRequest,
    GetSessionInfoRequest,
    Message,
    MessageKind,
    NewSessionRequest,
    NewSessionResponse,
    SessionInfo,
    SessionState,
    SubmitUserMessageRequest,
    SubmitUserMessageResponse,
)
from ..storage import get_claude_session, slice_messages, store_claude_session
from ..serializable_chat import serialize_claude_raw_messages, serialize_messages

router = APIRouter()
logger = logging.getLogger(__name__)
CLAUDE_HEALTH_MODEL = os.getenv("CLAUDE_HEALTH_MODEL", "claude-sonnet-4-6")
CLAUDE_HEALTH_PROMPT = "say pong"
CLAUDE_HEALTH_TIMEOUT_MILLIS = 15000


def _utc_now_millis() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


async def _run_claude_and_update(
    session_id: UUID,
    prompt: str,
    timeout_millis: int | None,
    request_message_id: UUID,
) -> None:
    session = get_claude_session(session_id)
    try:
        response, created_at, log_path = await asyncio.to_thread(
            run_claude,
            prompt=prompt,
            project_path=session.project_path,
            model_name=session.model_name,
            session_id=session.claude_session_id,
            mcp_servers=session.mcp_servers,
            timeout_millis=timeout_millis,
        )
    except subprocess.TimeoutExpired:
        session.info.state = SessionState.READY
        session.info.timeout = True
        session.info.error = None
        session.info.errorTimestamp = None
        return
    except HTTPException as exc:
        session.info.state = SessionState.READY
        session.info.timeout = False
        session.info.error = str(exc.detail)
        session.info.errorTimestamp = _utc_now_millis()
        logger.exception("Claude CLI failed for session %s", session_id)
        return
    except Exception as exc:
        session.info.state = SessionState.READY
        session.info.timeout = False
        session.info.error = str(exc)
        session.info.errorTimestamp = _utc_now_millis()
        logger.exception("Unexpected error while running Claude CLI for %s", session_id)
        return

    session.raw_dumps.append(
        ClaudeRawDump(
            payload=response,
            createdAt=created_at,
            logPath=str(log_path) if log_path is not None else None,
            requestMessageId=request_message_id,
        )
    )

    request_cost_usd = extract_total_cost_usd(response)
    session.info.lastTurnCostUsd = request_cost_usd

    try:
        messages, claude_session_id = extract_claude_messages(response)
    except HTTPException as exc:
        session.info.state = SessionState.READY
        session.info.timeout = False
        session.info.error = str(exc.detail)
        session.info.errorTimestamp = _utc_now_millis()
        logger.exception("Claude CLI response invalid for session %s", session_id)
        return

    session.messages = messages
    session.claude_session_id = claude_session_id
    session.info.lastMessageId = messages[-1].id if messages else None
    session.info.state = SessionState.READY
    session.info.timeout = False
    session.info.error = None
    session.info.errorTimestamp = None


@router.get("/health")
async def claude_health() -> dict[str, str]:
    try:
        payload, _, _ = await asyncio.to_thread(
            run_claude,
            prompt=CLAUDE_HEALTH_PROMPT,
            project_path=str(Path.cwd()),
            model_name=CLAUDE_HEALTH_MODEL,
            session_id=None,
            mcp_servers={},
            timeout_millis=CLAUDE_HEALTH_TIMEOUT_MILLIS,
        )
        messages, _ = extract_claude_messages(payload)
    except HTTPException as exc:
        logger.exception(
            "Claude health check failed with HTTPException: status=%s detail=%s",
            exc.status_code,
            exc.detail,
        )
        raise HTTPException(status_code=503, detail="Claude CLI health check failed") from exc
    except subprocess.TimeoutExpired as exc:
        logger.exception(
            "Claude health check timed out after %sms",
            CLAUDE_HEALTH_TIMEOUT_MILLIS,
        )
        raise HTTPException(status_code=503, detail="Claude CLI health check failed") from exc
    except Exception:
        logger.exception("Unexpected Claude health check error")
        raise HTTPException(status_code=503, detail="Claude CLI health check failed")

    answer = next(
        (
            message.content.strip()
            for message in reversed(messages)
            if message.kind == MessageKind.ASSISTANT and message.content.strip()
        ),
        None,
    )
    if answer is None:
        raise HTTPException(status_code=503, detail="Claude CLI health check returned empty response")

    return {"status": "ok", "answer": answer}


@router.post("/newSession", response_model=NewSessionResponse)
async def claude_new_session(req: NewSessionRequest) -> SessionInfo:
    session_id = uuid4()
    last_message_id = req.initialHistory[-1].id if req.initialHistory else None
    info = SessionInfo(
        id=session_id,
        state=SessionState.READY,
        lastMessageId=last_message_id,
        lastTurnCostUsd=None,
        timeout=False,
        error=None,
        errorTimestamp=None,
    )
    store_claude_session(
        session_id,
        ClaudeSessionData(
            info=info,
            messages=list(req.initialHistory),
            project_path=req.projectPath,
            model_name=req.agentSettings.modelName,
            mcp_servers=dict(req.agentSettings.mcpServers),
            initial_history=list(req.initialHistory),
            submitted_messages=[],
            raw_dumps=[],
        ),
    )
    return info


@router.post("/getSessionInfo", response_model=SessionInfo)
async def claude_get_session_info(req: GetSessionInfoRequest) -> SessionInfo:
    return get_claude_session(req.id).info


@router.post("/getMessages", response_model=list[Message])
async def claude_get_messages(req: GetMessagesRequest) -> list[Message]:
    session = get_claude_session(req.sessionId)
    return slice_messages(session.messages, req.fromExcl, req.toIncl)


@router.post("/getChatDump")
async def claude_get_chat_dump(req: GetChatDumpRequest) -> dict:
    session = get_claude_session(req.sessionId)
    serialized_messages: list[dict] = []
    serialized_messages.extend(serialize_messages(session.initial_history))

    raw_by_request: dict[UUID, list[tuple[object, datetime]]] = {}
    unmatched_raw: list[tuple[object, datetime]] = []
    for dump in session.raw_dumps:
        if dump.requestMessageId is None:
            unmatched_raw.append((dump.payload, dump.createdAt))
            continue
        raw_by_request.setdefault(dump.requestMessageId, []).append(
            (dump.payload, dump.createdAt)
        )

    for user_message in session.submitted_messages:
        serialized_messages.extend(serialize_messages([user_message]))
        raw_entries = raw_by_request.get(user_message.id, [])
        raw_entries.sort(key=lambda item: item[1])
        serialized_messages.extend(serialize_claude_raw_messages(raw_entries))

    if unmatched_raw:
        unmatched_raw.sort(key=lambda item: item[1])
        serialized_messages.extend(serialize_claude_raw_messages(unmatched_raw))

    return {
        "chatUuid": str(req.sessionId),
        "agentConfig": "claude",
        "messages": serialized_messages,
    }


@router.post("/submitUserMessage", response_model=SubmitUserMessageResponse)
async def claude_submit_user_message(
    req: SubmitUserMessageRequest,
) -> SubmitUserMessageResponse:
    session = get_claude_session(req.sessionId)

    if session.info.state != SessionState.READY:
        raise HTTPException(status_code=409, detail="Session not ready")

    session.info.state = SessionState.BUSY
    session.info.timeout = False
    session.info.error = None
    session.info.errorTimestamp = None

    now = datetime.now(timezone.utc)
    user_message = Message(
        id=uuid4(),
        timestamp=int(now.timestamp() * 1000),
        kind=MessageKind.USER,
        content=req.content,
        reasoning=None,
        toolCalls=[],
        toolResponses=[],
    )
    session.submitted_messages.append(user_message)
    session.messages.append(user_message)
    session.info.lastMessageId = user_message.id

    asyncio.create_task(
        _run_claude_and_update(
            session_id=req.sessionId,
            prompt=req.content,
            timeout_millis=req.timeoutMillis,
            request_message_id=user_message.id,
        )
    )
    return SubmitUserMessageResponse(sessionInfo=session.info)

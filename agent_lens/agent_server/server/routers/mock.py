from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from ..models import (
    GetMessagesRequest,
    GetChatDumpRequest,
    GetSessionInfoRequest,
    Message,
    MessageKind,
    NewSessionRequest,
    NewSessionResponse,
    SessionData,
    SessionInfo,
    SessionState,
    SubmitUserMessageRequest,
    SubmitUserMessageResponse,
)
from ..storage import get_session, slice_messages, store_session
from ..serializable_chat import build_serializable_chat

router = APIRouter()


@router.post("/newSession", response_model=NewSessionResponse)
async def new_session(req: NewSessionRequest) -> SessionInfo:
    session_id = uuid4()
    last_message_id = req.initialHistory[-1].id if req.initialHistory else None
    info = SessionInfo(
        id=session_id,
        state=SessionState.READY,
        lastMessageId=last_message_id,
        timeout=False,
        error=None,
        errorTimestamp=None,
    )
    store_session(session_id, SessionData(info=info, messages=list(req.initialHistory)))
    return info


@router.post("/getSessionInfo", response_model=SessionInfo)
async def get_session_info(req: GetSessionInfoRequest) -> SessionInfo:
    return get_session(req.id).info


@router.post("/getMessages", response_model=list[Message])
async def get_messages(req: GetMessagesRequest) -> list[Message]:
    session = get_session(req.sessionId)
    return slice_messages(session.messages, req.fromExcl, req.toIncl)


@router.post("/getChatDump")
async def get_chat_dump(req: GetChatDumpRequest) -> dict:
    session = get_session(req.sessionId)
    return build_serializable_chat(req.sessionId, session.messages, agent_config="mock")


@router.post("/submitUserMessage", response_model=SubmitUserMessageResponse)
async def submit_user_message(
    req: SubmitUserMessageRequest,
) -> SubmitUserMessageResponse:
    session = get_session(req.sessionId)

    if session.info.state != SessionState.READY:
        raise HTTPException(status_code=409, detail="Session not ready")

    session.info.state = SessionState.BUSY
    session.info.timeout = False
    session.info.error = None
    session.info.errorTimestamp = None

    message = Message(
        id=uuid4(),
        timestamp=None,
        kind=MessageKind.USER,
        content=req.content,
        reasoning=None,
        toolCalls=[],
        toolResponses=[],
    )
    session.messages.append(message)

    assistant_message = Message(
        id=uuid4(),
        timestamp=None,
        kind=MessageKind.ASSISTANT,
        content="Maybe later?",
        reasoning=None,
        toolCalls=[],
        toolResponses=[],
    )
    session.messages.append(assistant_message)

    session.info.lastMessageId = assistant_message.id
    session.info.state = SessionState.READY
    session.info.timeout = False
    session.info.error = None
    session.info.errorTimestamp = None

    return SubmitUserMessageResponse(sessionInfo=session.info)

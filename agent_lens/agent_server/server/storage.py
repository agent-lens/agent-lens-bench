from __future__ import annotations

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException

from .models import ClaudeSessionData, Message, SessionData

_sessions: Dict[UUID, SessionData] = {}
_claude_sessions: Dict[UUID, ClaudeSessionData] = {}


def get_session(session_id: UUID) -> SessionData:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def get_claude_session(session_id: UUID) -> ClaudeSessionData:
    session = _claude_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def store_session(session_id: UUID, session: SessionData) -> None:
    _sessions[session_id] = session


def store_claude_session(session_id: UUID, session: ClaudeSessionData) -> None:
    _claude_sessions[session_id] = session


def slice_messages(
    messages: List[Message], from_excl: Optional[UUID], to_incl: Optional[UUID]
) -> List[Message]:
    if not messages:
        return []

    start_index = 0
    if from_excl is not None:
        for i, msg in enumerate(messages):
            if msg.id == from_excl:
                start_index = i + 1
                break

    end_index = len(messages)
    if to_incl is not None:
        for i, msg in enumerate(messages):
            if msg.id == to_incl:
                end_index = i + 1
                break

    if start_index >= end_index:
        return []

    return messages[start_index:end_index]

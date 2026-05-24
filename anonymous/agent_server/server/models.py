from __future__ import annotations

from enum import Enum
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SessionState(str, Enum):
    UNINITIALIZED = "UNINITIALIZED"
    READY = "READY"
    BUSY = "BUSY"


class McpServer(BaseModel):
    type: str
    url: str
    headers: dict[str, str] = Field(default_factory=dict)


class AgentSettings(BaseModel):
    modelName: str
    mcpServers: dict[str, McpServer] = Field(default_factory=dict)


class MessageKind(str, Enum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"


class ToolCall(BaseModel):
    id: str
    name: str
    args: str


class ToolResponse(BaseModel):
    id: str
    name: str
    content: str
    success: bool = True


class Message(BaseModel):
    id: UUID
    timestamp: Optional[int] = None
    kind: MessageKind
    content: str
    reasoning: Optional[str] = None
    toolCalls: List[ToolCall] = Field(default_factory=list)
    toolResponses: List[ToolResponse] = Field(default_factory=list)


class SessionInfo(BaseModel):
    id: UUID
    state: SessionState
    lastMessageId: Optional[UUID] = None
    lastTurnCostUsd: Optional[float] = None
    timeout: bool
    error: Optional[str] = None
    errorTimestamp: Optional[int] = None


class NewSessionRequest(BaseModel):
    agentSettings: AgentSettings
    projectPath: str
    initialHistory: List[Message] = Field(default_factory=list)


class NewSessionResponse(SessionInfo):
    pass


class GetSessionInfoRequest(BaseModel):
    id: UUID


class GetMessagesRequest(BaseModel):
    sessionId: UUID
    fromExcl: Optional[UUID] = None
    toIncl: Optional[UUID] = None


class GetChatDumpRequest(BaseModel):
    sessionId: UUID


class SubmitUserMessageRequest(BaseModel):
    sessionId: UUID
    content: str
    timeoutMillis: Optional[int] = None


class SubmitUserMessageResponse(BaseModel):
    sessionInfo: SessionInfo


class SessionData(BaseModel):
    info: SessionInfo
    messages: List[Message] = Field(default_factory=list)


class ClaudeRawDump(BaseModel):
    payload: object
    createdAt: datetime
    logPath: Optional[str] = None
    requestMessageId: Optional[UUID] = None


class ClaudeSessionData(BaseModel):
    info: SessionInfo
    messages: List[Message] = Field(default_factory=list)
    claude_session_id: Optional[str] = None
    project_path: str
    model_name: str
    mcp_servers: dict[str, McpServer] = Field(default_factory=dict)
    initial_history: List[Message] = Field(default_factory=list)
    submitted_messages: List[Message] = Field(default_factory=list)
    raw_dumps: List[ClaudeRawDump] = Field(default_factory=list)

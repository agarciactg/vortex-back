from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any
from app.models.ai_conversation import MessageRole


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None


class ToolCallOut(BaseModel):
    tool_name: str
    input: dict[str, Any]
    result: str


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    actions: list[ToolCallOut] = []


class MessageOut(BaseModel):
    id: str
    role: MessageRole
    content: str | None
    tool_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryOut(BaseModel):
    items: list[MessageOut]
    total: int
    conversation_id: str

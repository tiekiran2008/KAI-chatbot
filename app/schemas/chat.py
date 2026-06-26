import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from app.models.chat import MessageRole


# ─── Message Schemas ────────────────────────────────────────────────────────

class MessageRead(BaseModel):
    """Serialized representation of a single message turn."""
    id: uuid.UUID
    chat_id: uuid.UUID
    role: MessageRole
    content: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    citations: Optional[List[dict]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Chat Schemas ────────────────────────────────────────────────────────────

class ChatCreate(BaseModel):
    """Request body for starting a new chat session."""
    system_prompt: Optional[str] = Field(
        None,
        description="Optional system-level instruction to shape the assistant's behavior"
    )

class ChatRead(BaseModel):
    """Serialized lightweight representation of a chat (no messages)."""
    id: uuid.UUID
    title: Optional[str]
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None

    class Config:
        from_attributes = True


class ChatDetail(ChatRead):
    """Full chat object including all message history."""
    messages: List[MessageRead] = []
    system_prompt: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Send Message Schema ─────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    """Request body for sending a new message in an existing chat."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="The user's message content"
    )

    @field_validator("message")
    @classmethod
    def sanitize_input(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty")
        if "<script" in cleaned.lower() or "javascript:" in cleaned.lower():
            raise ValueError("Potentially malicious input detected")
        return cleaned


class SendMessageResponse(BaseModel):
    """Response body after the assistant replies."""
    chat_id: uuid.UUID
    user_message: MessageRead
    assistant_message: MessageRead


class ChatRename(BaseModel):
    """Request body for renaming an existing chat session."""
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="The new title for the chat thread"
    )

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Title cannot be empty")
        if "<" in cleaned or ">" in cleaned:
            raise ValueError("Title cannot contain HTML characters")
        return cleaned

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    kb_id: str
    created_at: datetime
    updated_at: datetime


class CitationOut(BaseModel):
    index: int
    chunk_id: str
    document_title: str
    page_number: int | None
    excerpt: str
    score: float | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    citations: list[CitationOut] = []
    created_at: datetime


class MessageList(BaseModel):
    items: list[MessageOut]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class ChatResponse(BaseModel):
    message_id: str
    answer: str
    citations: list[CitationOut]
    latency_ms: int

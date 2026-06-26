from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    store_id: int | None = None


class ChatResponse(BaseModel):
    reply: str


class AssistantIntro(BaseModel):
    greeting: str
    suggestions: list[str]
    enabled: bool

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    conversation_id: Optional[int] = Field(None, description="ID of existing conversation, or null to start a new chat")
    prompt: str = Field(..., min_length=1, max_length=4000, description="User's operational query")


class AIMessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime
    metadata_json: Optional[str] = None

    class Config:
        from_attributes = True


class AIConversationListItem(BaseModel):
    id: int
    project_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message_preview: Optional[str] = None

    class Config:
        from_attributes = True


class AIConversationResponse(BaseModel):
    id: int
    project_id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[AIMessageResponse] = []

    class Config:
        from_attributes = True


class AIChatResponse(BaseModel):
    conversation_id: int
    conversation_title: str
    user_message: AIMessageResponse
    assistant_message: AIMessageResponse
    sources: List[Dict[str, Any]] = []

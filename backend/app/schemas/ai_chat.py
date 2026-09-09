from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    conversation_id: Optional[int] = Field(None, description="ID of existing conversation, or null to start a new chat")
    prompt: str = Field(..., min_length=1, max_length=4000, description="User's operational query")


class ExecutionReportDraftResponse(BaseModel):
    id: int
    project_id: int
    reported_by_id: int
    conversation_id: Optional[int] = None
    original_text: str
    intent: str
    update_type: str
    reported_date: Any  # date or str
    progress_percentage: Optional[float] = None
    remarks: Optional[str] = None
    matched_activity_id: Optional[int] = None
    matched_activity_code: Optional[str] = None
    matched_activity_name: Optional[str] = None
    matched_discipline: Optional[str] = None
    current_status: Optional[str] = None
    current_progress: Optional[float] = None
    proposed_status: Optional[str] = None
    proposed_progress: Optional[float] = None
    match_confidence: Optional[float] = None
    match_status: str
    status: str
    error_message: Optional[str] = None
    alternatives: List[Dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AIMessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime
    metadata_json: Optional[str] = None
    draft: Optional[ExecutionReportDraftResponse] = None

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


class SelectActivityRequest(BaseModel):
    activity_id: int


class AIChatResponse(BaseModel):
    conversation_id: int
    conversation_title: str
    user_message: AIMessageResponse
    assistant_message: AIMessageResponse
    sources: List[Dict[str, Any]] = []
    response_type: str = "MESSAGE"  # MESSAGE or PROGRESS_DRAFT
    draft: Optional[ExecutionReportDraftResponse] = None

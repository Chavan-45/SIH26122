from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class PlannerReviewCaseSummary(BaseModel):
    needs_review: int = 0
    low_confidence: int = 0
    unmatched: int = 0
    resolved: int = 0
    unplanned: int = 0
    rejected: int = 0
    applied: int = 0
    total: int = 0

    model_config = ConfigDict(from_attributes=True)


class PlannerReviewCandidateItem(BaseModel):
    activity_id: int
    activity_code: str
    activity_name: str
    discipline: str
    confidence: float
    exec_status: str

    model_config = ConfigDict(from_attributes=True)


class PlannerReviewCaseListItem(BaseModel):
    id: int
    project_id: int
    source_type: str  # "AI_REPORT", "PROGRESS_REPORT"
    source_id: int
    original_text: str
    reporter_name: Optional[str] = None
    reported_date: Optional[date] = None
    discipline: Optional[str] = None
    extracted_update_type: Optional[str] = None
    extracted_progress_percentage: Optional[float] = None
    remarks: Optional[str] = None

    original_activity_id: Optional[int] = None
    original_activity_code: Optional[str] = None
    original_activity_name: Optional[str] = None
    original_confidence: Optional[float] = None
    match_status: str = "UNMATCHED"

    selected_activity_id: Optional[int] = None
    selected_activity_code: Optional[str] = None
    selected_activity_name: Optional[str] = None

    decision: str = "NEEDS_REVIEW"  # "NEEDS_REVIEW", "RESOLVED", "REJECTED", "UNPLANNED", "APPLIED"
    review_reason: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlannerReviewCaseDetail(PlannerReviewCaseListItem):
    candidates: List[PlannerReviewCandidateItem] = []
    validation_status: str = "VALID"  # "VALID" or "INVALID"
    validation_error: Optional[str] = None

    current_execution_status: Optional[str] = None
    current_progress_percentage: Optional[float] = None
    proposed_execution_status: Optional[str] = None
    proposed_progress_percentage: Optional[float] = None


class PlannerReviewCaseListResponse(BaseModel):
    items: List[PlannerReviewCaseListItem]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class SelectActivityRequest(BaseModel):
    activity_id: int
    review_reason: Optional[str] = None


class RejectCaseRequest(BaseModel):
    review_reason: str = Field(min_length=3, description="Mandatory reason for rejecting update")


class MarkUnplannedRequest(BaseModel):
    review_reason: str = Field(min_length=3, description="Mandatory reason for classifying as unplanned work")

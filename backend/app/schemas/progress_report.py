from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class TextReportImportRequest(BaseModel):
    raw_text: str


class ColumnMappingRequest(BaseModel):
    mapping: Dict[str, Optional[str]]


class SelectReportItemActivityRequest(BaseModel):
    activity_id: int


class ReviewReportItemRequest(BaseModel):
    action: str  # APPROVE, REJECT


class ProgressReportItemResponse(BaseModel):
    id: int
    report_id: int
    project_id: int
    raw_description: str
    reported_date: Optional[date] = None
    extracted_update_type: Optional[str] = None
    extracted_progress_percentage: Optional[float] = None
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
    review_status: str
    validation_status: str  # VALID, INVALID
    error_message: Optional[str] = None
    alternatives: List[Dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProgressReportImportResponse(BaseModel):
    id: int
    project_id: int
    uploaded_by_id: int
    uploaded_by_name: str
    source_type: str
    original_filename: Optional[str] = None
    raw_text: Optional[str] = None
    status: str
    total_items: int
    pending_items: int
    approved_items: int
    applied_items: int
    rejected_items: int
    invalid_items: int
    items: List[ProgressReportItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProgressReportImportListItem(BaseModel):
    id: int
    project_id: int
    uploaded_by_id: int
    uploaded_by_name: str
    source_type: str
    original_filename: Optional[str] = None
    status: str
    total_items: int
    pending_items: int
    approved_items: int
    applied_items: int
    invalid_items: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

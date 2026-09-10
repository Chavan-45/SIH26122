from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MemoryUserRef(BaseModel):
    id: Optional[int] = None
    name: str = "System"
    role: Optional[str] = None


class MemoryProvenance(BaseModel):
    filename: Optional[str] = None
    page: Optional[int] = None
    report_import_id: Optional[int] = None
    source_type: Optional[str] = None
    review_case_id: Optional[int] = None


class MemoryEvent(BaseModel):
    event_id: str
    event_type: str  # EXECUTION_UPDATE, REVIEW_DECISION, REPORT_SUBMISSION, SCHEDULE_IMPORT
    project_id: int

    activity_id: Optional[int] = None
    activity_code: Optional[str] = None
    activity_name: Optional[str] = None
    discipline: Optional[str] = None

    event_date: Optional[str] = None  # YYYY-MM-DD
    created_at: str  # ISO string

    title: str
    description: Optional[str] = None

    update_type: Optional[str] = None  # START, PROGRESS, COMPLETE, ON_HOLD, RESUME, RESOLVED, REJECTED, UNPLANNED, etc.
    progress_percentage: Optional[float] = None

    reported_by: Optional[MemoryUserRef] = None
    source: str = "MANUAL"  # MANUAL, AI_CHAT, REPORT_IMPORT, SPREADSHEET, REVIEW_CENTER, SCHEDULE_IMPORT

    remarks: Optional[str] = None
    provenance: Optional[MemoryProvenance] = None


class MemorySummary(BaseModel):
    total_execution_updates: int
    activities_with_history: int
    total_review_decisions: int
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    scope: str = "Project-wide"


class ActivityScheduleContext(BaseModel):
    activity_id: int
    activity_code: str
    activity_name: str
    discipline: str
    wbs_code: Optional[str] = None
    planned_start: Optional[str] = None
    planned_finish: Optional[str] = None
    planned_duration: Optional[float] = None
    actual_start: Optional[str] = None
    actual_finish: Optional[str] = None
    current_progress: float = 0.0
    current_status: str = "NOT_STARTED"


class ActivityDelayAnalysis(BaseModel):
    state: str  # ON_TIME, CURRENTLY_OVERDUE, COMPLETED_LATE, NO_PLANNED_FINISH
    late_days: int
    planned_finish: Optional[str] = None
    actual_finish: Optional[str] = None
    current_status: str
    current_progress: float
    summary: str
    relevant_events: List[MemoryEvent] = []
    recorded_notes: List[str] = []


class ActivityTimelineResponse(BaseModel):
    activity: ActivityScheduleContext
    delay_analysis: ActivityDelayAnalysis
    events: List[MemoryEvent] = []
    total_events: int


class MemoryEventListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    events: List[MemoryEvent] = []

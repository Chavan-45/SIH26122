from enum import Enum
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class UpdateTypeEnum(str, Enum):
    START = "START"
    PROGRESS = "PROGRESS"
    COMPLETE = "COMPLETE"
    ON_HOLD = "ON_HOLD"
    RESUME = "RESUME"


class ExecutionStatusEnum(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"


class SourceTypeEnum(str, Enum):
    MANUAL = "MANUAL"
    AI_CHAT = "AI_CHAT"
    VOICE = "VOICE"
    SPREADSHEET = "SPREADSHEET"
    DAILY_REPORT = "DAILY_REPORT"


class ProgressReportRequest(BaseModel):
    update_type: UpdateTypeEnum = Field(..., description="Action type: START, PROGRESS, COMPLETE, ON_HOLD, RESUME")
    reported_date: date = Field(..., description="Date of the actual execution event")
    progress_percentage: Optional[float] = Field(None, ge=0.0, le=100.0, description="Progress percentage (1-99 for PROGRESS update, 100 for COMPLETE)")
    remarks: Optional[str] = Field(None, max_length=1000, description="Field remarks or notes")


class ActivityExecutionResponse(BaseModel):
    id: Optional[int] = None
    project_id: int
    activity_id: int
    activity_code: str
    activity_name: str
    discipline: str
    planned_start: date
    planned_finish: date
    actual_start: Optional[date] = None
    actual_finish: Optional[date] = None
    progress_percentage: float = 0.0
    execution_status: str = "NOT_STARTED"
    last_updated_at: Optional[datetime] = None
    last_updated_by_name: Optional[str] = None
    finish_variance_days: Optional[int] = None
    current_overdue_days: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ProgressUpdateResponse(BaseModel):
    id: int
    project_id: int
    activity_id: int
    reported_by_id: int
    reported_by_name: Optional[str] = None
    update_type: str
    reported_date: date
    progress_percentage: Optional[float] = None
    remarks: Optional[str] = None
    source_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecutionSummaryResponse(BaseModel):
    project_id: int
    total_activities: int
    not_started: int
    in_progress: int
    on_hold: int
    completed: int
    overdue: int
    average_progress: float

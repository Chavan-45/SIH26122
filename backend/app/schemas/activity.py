from enum import Enum
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class DisciplineEnum(str, Enum):
    CIVIL = "CIVIL"
    PIPING = "PIPING"
    ELECTRICAL = "ELECTRICAL"
    MECHANICAL = "MECHANICAL"
    INSTRUMENTATION = "INSTRUMENTATION"
    HSE = "HSE"
    OTHER = "OTHER"
    UNASSIGNED = "UNASSIGNED"


class ActivityResponse(BaseModel):
    id: int
    project_id: int
    activity_code: str
    activity_name: str
    wbs_code: Optional[str] = None
    wbs_name: Optional[str] = None
    schedule_level: Optional[str] = None
    discipline: str
    planned_start: date
    planned_finish: date
    planned_duration: Optional[float] = None
    predecessors: Optional[str] = None
    # Execution tracking fields
    actual_start: Optional[date] = None
    actual_finish: Optional[date] = None
    progress_percentage: float = 0.0
    execution_status: str = "NOT_STARTED"
    last_updated_at: Optional[datetime] = None
    last_updated_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ActivityListResponse(BaseModel):
    items: List[ActivityResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ScheduleImportResponse(BaseModel):
    id: int
    project_id: int
    original_filename: str
    file_type: str
    imported_by_id: int
    imported_by_name: Optional[str] = None
    total_rows: int
    imported_rows: int
    status: str
    imported_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleStatusResponse(BaseModel):
    has_schedule: bool
    total_activities: int
    latest_import: Optional[ScheduleImportResponse] = None
    earliest_planned_start: Optional[date] = None
    latest_planned_finish: Optional[date] = None
    discipline_counts: Dict[str, int] = Field(default_factory=dict)
    level_counts: Dict[str, int] = Field(default_factory=dict)


class SchedulePreviewResponse(BaseModel):
    filename: str
    row_count: int
    headers: List[str]
    detected_mapping: Dict[str, Optional[str]]
    preview_rows: List[Dict[str, Any]]
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

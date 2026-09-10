from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ScheduleSyncSummaryResponse(BaseModel):
    """100% database-derived KPI metrics for the Schedule Sync top summary cards."""
    total_activities: int
    activities_with_actuals: int
    changed_since_last_export: int
    has_previous_export: bool
    last_export_at: Optional[datetime] = None
    last_export_format: Optional[str] = None
    last_export_mode: Optional[str] = None
    last_export_id: Optional[int] = None

    model_config = {"from_attributes": True}


class ScheduleSyncPreviewItem(BaseModel):
    """Canonical actuals row with comparison metadata for export preview."""
    project_code: str
    project_name: str
    activity_code: str
    activity_name: str
    wbs_code: Optional[str] = None
    wbs_name: Optional[str] = None
    schedule_level: Optional[str] = None
    discipline: str
    planned_start: str
    planned_finish: str
    actual_start: Optional[str] = None
    actual_finish: Optional[str] = None
    progress_percentage: float
    execution_status: str
    start_variance_days: Optional[int] = None
    finish_variance_days: Optional[int] = None
    overdue_days: int = 0
    last_updated_at: Optional[str] = None
    last_updated_by: Optional[str] = None
    last_update_source: Optional[str] = None
    change_flags: List[str] = []
    is_changed: bool = False


class ScheduleSyncPreviewResponse(BaseModel):
    """Read-only preview response before generating an export snapshot."""
    export_mode: str
    total_activities: int
    rows_to_export: int
    changed_activity_count: int
    has_previous_export: bool
    previous_export_at: Optional[datetime] = None
    items: List[ScheduleSyncPreviewItem]


class CreateScheduleExportRequest(BaseModel):
    """Request payload to generate a persistent export snapshot."""
    export_mode: str = Field(..., description="FULL_SNAPSHOT or CHANGES_ONLY")
    file_format: str = Field("XLSX", description="CSV or XLSX")


class ScheduleExportListItemResponse(BaseModel):
    """Summary item for the export history table."""
    id: int
    project_id: int
    export_mode: str
    file_format: str
    status: str
    row_count: int
    changed_activity_count: int
    file_name: Optional[str] = None
    exported_by_id: int
    exported_by_name: Optional[str] = None
    generated_at: datetime
    created_at: datetime
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class ScheduleExportDetailResponse(BaseModel):
    """Detailed view of an individual export record."""
    id: int
    project_id: int
    project_code: str
    project_name: str
    export_mode: str
    file_format: str
    status: str
    row_count: int
    changed_activity_count: int
    file_name: Optional[str] = None
    exported_by_id: int
    exported_by_name: Optional[str] = None
    generated_at: datetime
    created_at: datetime
    error_message: Optional[str] = None
    items: List[ScheduleSyncPreviewItem] = []

    model_config = {"from_attributes": True}

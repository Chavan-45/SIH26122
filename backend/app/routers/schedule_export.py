from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.core.dependencies import require_planner
from app.services.project_service import verify_project_planner_owner
from app.schemas.schedule_export import (
    ScheduleSyncSummaryResponse,
    ScheduleSyncPreviewResponse,
    CreateScheduleExportRequest,
    ScheduleExportListItemResponse,
    ScheduleExportDetailResponse,
)
from app.services.schedule_export_service import (
    get_schedule_sync_summary,
    get_schedule_sync_preview,
    create_schedule_export,
    get_export_history,
    get_export_detail,
    download_export_snapshot,
)

router = APIRouter(prefix="/projects", tags=["Schedule Sync & Export"])


@router.get(
    "/{project_id}/schedule-sync/summary",
    response_model=ScheduleSyncSummaryResponse,
    summary="Get summary KPI metrics for Schedule Sync & Export (Planner only)",
)
def get_sync_summary(
    project_id: int,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Returns database summary counts for total, with actuals, and changed activities."""
    verify_project_planner_owner(project_id, current_user, db)
    return get_schedule_sync_summary(db, project_id)


@router.get(
    "/{project_id}/schedule-sync/preview",
    response_model=ScheduleSyncPreviewResponse,
    summary="Preview canonical schedule actuals before export (Planner only)",
)
def preview_schedule_sync(
    project_id: int,
    mode: str = Query("FULL_SNAPSHOT", description="Export scope: FULL_SNAPSHOT or CHANGES_ONLY"),
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Generates a read-only preview of the actuals dataset without modifying or creating export records."""
    verify_project_planner_owner(project_id, current_user, db)
    return get_schedule_sync_preview(db, project_id, mode)


@router.post(
    "/{project_id}/schedule-sync/exports",
    response_model=ScheduleExportDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a persistent schedule actuals export snapshot (Planner only)",
)
def create_export(
    project_id: int,
    req: CreateScheduleExportRequest,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Generates and persists an immutable schedule export snapshot for the project."""
    verify_project_planner_owner(project_id, current_user, db)
    return create_schedule_export(
        db=db,
        project_id=project_id,
        planner_user=current_user,
        export_mode=req.export_mode,
        file_format=req.file_format,
    )


@router.get(
    "/{project_id}/schedule-sync/exports",
    response_model=List[ScheduleExportListItemResponse],
    summary="List all past schedule exports for a project (Planner only)",
)
def list_exports(
    project_id: int,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Returns audit history of all generated schedule exports for this project."""
    verify_project_planner_owner(project_id, current_user, db)
    return get_export_history(db, project_id)


@router.get(
    "/{project_id}/schedule-sync/exports/{export_id}",
    response_model=ScheduleExportDetailResponse,
    summary="Get details of a specific historical export snapshot (Planner only)",
)
def get_export(
    project_id: int,
    export_id: int,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Retrieves snapshot items and metadata for an individual export."""
    verify_project_planner_owner(project_id, current_user, db)
    return get_export_detail(db, project_id, export_id)


@router.get(
    "/{project_id}/schedule-sync/exports/{export_id}/download",
    summary="Download historical CSV or XLSX export file (Planner only)",
)
def download_export(
    project_id: int,
    export_id: int,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Generates download file dynamically from the persisted export snapshot items."""
    verify_project_planner_owner(project_id, current_user, db)
    file_bytes_io, media_type, file_name = download_export_snapshot(db, project_id, export_id)

    return StreamingResponse(
        file_bytes_io,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )

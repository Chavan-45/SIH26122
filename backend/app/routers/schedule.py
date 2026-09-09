import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database.database import get_db
from app.models.user import User
from app.models.activity import Activity
from app.models.schedule_import import ScheduleImport
from app.schemas.activity import (
    ActivityResponse,
    ActivityListResponse,
    ScheduleStatusResponse,
    SchedulePreviewResponse,
    ScheduleImportResponse,
)
from app.core.dependencies import get_current_user, require_planner
from app.services.project_service import (
    verify_project_planner_owner,
    verify_project_access,
)
from app.services.schedule_service import (
    read_uploaded_file,
    process_schedule_preview,
    execute_schedule_import,
)

router = APIRouter(prefix="/projects", tags=["Schedule & Activities"])


@router.post(
    "/{project_id}/schedule/preview",
    response_model=SchedulePreviewResponse,
    summary="Upload and preview schedule baseline file (Planner owner only)",
)
async def preview_schedule(
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """
    Parse uploaded CSV/XLSX schedule file, auto-detect column header mappings,
    validate row structure and dates without saving any database records.
    """
    verify_project_planner_owner(project_id, current_user, db)

    df, _ = await read_uploaded_file(file)
    preview_data = process_schedule_preview(df, file.filename or "uploaded_schedule")
    return preview_data


@router.post(
    "/{project_id}/schedule/import",
    summary="Confirm and commit baseline schedule import (Planner owner only)",
)
async def import_schedule(
    project_id: int,
    file: UploadFile = File(...),
    mapping: str = Form(...),
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """
    Re-parse uploaded CSV/XLSX file server-side using confirmed column header mapping,
    run full row validation, and save activities into database in a single transaction.
    """
    verify_project_planner_owner(project_id, current_user, db)

    try:
        column_mapping: Dict[str, Optional[str]] = json.loads(mapping)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid mapping JSON format supplied.",
        )

    df, ext = await read_uploaded_file(file)

    result = execute_schedule_import(
        db=db,
        project_id=project_id,
        user=current_user,
        df=df,
        filename=file.filename or "uploaded_schedule",
        file_type=ext,
        mapping=column_mapping,
    )
    return result


@router.get(
    "/{project_id}/schedule",
    response_model=ScheduleStatusResponse,
    summary="Get project baseline schedule status and metadata (Authorized users)",
)
def get_schedule_status(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve schedule status, latest import log, date range, and discipline/level distributions."""
    verify_project_access(project_id, current_user, db)

    total_activities = db.query(func.count(Activity.id)).filter(Activity.project_id == project_id).scalar() or 0
    has_schedule = total_activities > 0

    latest_import = (
        db.query(ScheduleImport)
        .filter(ScheduleImport.project_id == project_id)
        .order_by(ScheduleImport.imported_at.desc())
        .first()
    )

    latest_import_res = None
    if latest_import:
        latest_import_res = ScheduleImportResponse(
            id=latest_import.id,
            project_id=latest_import.project_id,
            original_filename=latest_import.original_filename,
            file_type=latest_import.file_type,
            imported_by_id=latest_import.imported_by_id,
            imported_by_name=latest_import.imported_by.full_name if latest_import.imported_by else None,
            total_rows=latest_import.total_rows,
            imported_rows=latest_import.imported_rows,
            status=latest_import.status,
            imported_at=latest_import.imported_at,
        )

    earliest_start = None
    latest_finish = None
    discipline_counts = {}
    level_counts = {}

    if has_schedule:
        date_range = db.query(
            func.min(Activity.planned_start),
            func.max(Activity.planned_finish),
        ).filter(Activity.project_id == project_id).first()

        if date_range:
            earliest_start = date_range[0]
            latest_finish = date_range[1]

        # Discipline breakdown
        disc_results = (
            db.query(Activity.discipline, func.count(Activity.id))
            .filter(Activity.project_id == project_id)
            .group_by(Activity.discipline)
            .all()
        )
        discipline_counts = {disc: cnt for disc, cnt in disc_results if disc}

        # Schedule Level breakdown
        lvl_results = (
            db.query(Activity.schedule_level, func.count(Activity.id))
            .filter(Activity.project_id == project_id)
            .group_by(Activity.schedule_level)
            .all()
        )
        level_counts = {lvl or "UNSPECIFIED": cnt for lvl, cnt in lvl_results}

    return ScheduleStatusResponse(
        has_schedule=has_schedule,
        total_activities=total_activities,
        latest_import=latest_import_res,
        earliest_planned_start=earliest_start,
        latest_planned_finish=latest_finish,
        discipline_counts=discipline_counts,
        level_counts=level_counts,
    )


@router.get(
    "/{project_id}/activities",
    response_model=ActivityListResponse,
    summary="List project baseline activities with search and filters (Authorized users)",
)
def list_activities(
    project_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    search: Optional[str] = Query(None, description="Search activity code, name, or WBS"),
    discipline: Optional[str] = Query(None, description="Filter by discipline"),
    schedule_level: Optional[str] = Query(None, description="Filter by schedule level (e.g. L5, L6)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Paginated list of baseline activities for an authorized project with filtering."""
    verify_project_access(project_id, current_user, db)

    query = db.query(Activity).filter(Activity.project_id == project_id)

    # Search filter
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Activity.activity_code.ilike(search_term),
                Activity.activity_name.ilike(search_term),
                Activity.wbs_code.ilike(search_term),
                Activity.wbs_name.ilike(search_term),
            )
        )

    # Discipline filter
    if discipline and discipline.upper() != "ALL":
        query = query.filter(Activity.discipline == discipline.upper())

    # Level filter
    if schedule_level and schedule_level.upper() != "ALL":
        query = query.filter(Activity.schedule_level == schedule_level.upper())

    total = query.count()
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    activities = (
        query.order_by(Activity.planned_start.asc(), Activity.activity_code.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [ActivityResponse.model_validate(act) for act in activities]

    return ActivityListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{project_id}/activities/{activity_id}",
    response_model=ActivityResponse,
    summary="Get detailed information for a single activity (Authorized users)",
)
def get_activity_detail(
    project_id: int,
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve full metadata for a specific activity within an authorized project."""
    verify_project_access(project_id, current_user, db)

    activity = (
        db.query(Activity)
        .filter(Activity.project_id == project_id, Activity.id == activity_id)
        .first()
    )

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity with ID {activity_id} not found in this project.",
        )

    return ActivityResponse.model_validate(activity)

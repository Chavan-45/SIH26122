from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_user
from app.services.project_service import verify_project_access
from app.services.project_memory_service import ProjectMemoryService
from app.schemas.project_memory import (
    MemorySummary,
    MemoryEventListResponse,
    ActivityTimelineResponse,
    ActivityDelayAnalysis,
)

router = APIRouter(prefix="/projects", tags=["Project Institutional Memory"])


@router.get(
    "/{project_id}/memory/summary",
    response_model=MemorySummary,
    summary="Get project historical memory summary metrics",
)
def get_project_memory_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves high-level historical execution update and audit metrics.
    Planner receives full project metrics; Supervisor receives discipline-scoped metrics.
    """
    project, assigned_discipline = verify_project_access(project_id, current_user, db)
    return ProjectMemoryService.get_memory_summary(
        db=db,
        project_id=project_id,
        user_role=current_user.role,
        user_discipline=assigned_discipline,
    )


@router.get(
    "/{project_id}/memory/events",
    response_model=MemoryEventListResponse,
    summary="Get paginated, filtered historical memory events",
)
def get_project_memory_events(
    project_id: int,
    q: Optional[str] = Query(None, description="Free text search on activity code, name, remarks"),
    activity_id: Optional[int] = Query(None, description="Filter by activity ID"),
    activity_code: Optional[str] = Query(None, description="Filter by activity code"),
    discipline: Optional[str] = Query(None, description="Filter by discipline (Planner only)"),
    event_type: Optional[str] = Query(None, description="Filter by event type (EXECUTION_UPDATE, REVIEW_DECISION)"),
    source: Optional[str] = Query(None, description="Filter by source type (MANUAL, AI_CHAT, REPORT_IMPORT)"),
    date_from: Optional[date] = Query(None, description="Filter events on or after this date"),
    date_to: Optional[date] = Query(None, description="Filter events on or before this date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves normalized historical memory events with multi-field search and filtering.
    Discipline scoping is strictly enforced at backend query layer for Supervisors.
    """
    project, assigned_discipline = verify_project_access(project_id, current_user, db)
    return ProjectMemoryService.get_project_events(
        db=db,
        project_id=project_id,
        user_role=current_user.role,
        user_discipline=assigned_discipline,
        q=q,
        activity_id=activity_id,
        activity_code=activity_code,
        discipline=discipline,
        event_type=event_type,
        source=source,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{project_id}/memory/activities/{activity_id}/timeline",
    response_model=ActivityTimelineResponse,
    summary="Get chronological activity memory timeline and schedule context",
)
def get_activity_memory_timeline(
    project_id: int,
    activity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves chronological execution update history for a single activity (oldest -> newest),
    including planned baseline vs actual execution context and deterministic delay analysis.
    """
    project, assigned_discipline = verify_project_access(project_id, current_user, db)
    return ProjectMemoryService.get_activity_timeline(
        db=db,
        project_id=project_id,
        activity_id_or_code=activity_id,
        user_role=current_user.role,
        user_discipline=assigned_discipline,
    )


@router.get(
    "/{project_id}/memory/activities/{activity_id}/delay-analysis",
    response_model=ActivityDelayAnalysis,
    summary="Get deterministic activity delay classification and recorded notes",
)
def get_activity_delay_analysis_endpoint(
    project_id: int,
    activity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns factual deterministic delay classification (ON_TIME, CURRENTLY_OVERDUE, COMPLETED_LATE)
    and any recorded project notes. Guaranteed zero hallucinated delay causes.
    """
    project, assigned_discipline = verify_project_access(project_id, current_user, db)
    return ProjectMemoryService.get_activity_delay_analysis(
        db=db,
        project_id=project_id,
        activity_id_or_code=activity_id,
        user_role=current_user.role,
        user_discipline=assigned_discipline,
    )

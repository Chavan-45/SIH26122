from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.schemas.execution import (
    ProgressReportRequest,
    ActivityExecutionResponse,
    ProgressUpdateResponse,
    ExecutionSummaryResponse,
)
from app.core.dependencies import get_current_user
from app.services.project_service import get_project_or_404, verify_project_access
from app.services.execution_service import (
    process_progress_update,
    get_execution_response_data,
    calculate_execution_summary,
)

router = APIRouter(prefix="/projects", tags=["Actual Progress Tracking"])


@router.post(
    "/{project_id}/activities/{activity_id}/progress",
    response_model=ActivityExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Report actual execution progress event (START, PROGRESS, COMPLETE, ON_HOLD, RESUME)",
)
def report_progress(
    project_id: int,
    activity_id: int,
    report_req: ProgressReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submits an actual site progress report.
    Enforces discipline-based supervisor authorization and execution state machine rules.
    Original baseline planned dates remain untouched.
    """
    execution, _ = process_progress_update(
        db=db,
        project_id=project_id,
        activity_id=activity_id,
        user=current_user,
        report_req=report_req,
    )

    activity = (
        db.query(Activity)
        .filter(Activity.project_id == project_id, Activity.id == activity_id)
        .first()
    )
    return get_execution_response_data(activity, execution)


@router.get(
    "/{project_id}/activities/{activity_id}/execution",
    response_model=ActivityExecutionResponse,
    summary="Get current actual execution state for an activity (Authorized users)",
)
def get_activity_execution(
    project_id: int,
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve actual start/finish, progress %, and execution status for an activity."""
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

    execution = (
        db.query(ActivityExecution)
        .filter(ActivityExecution.activity_id == activity_id)
        .first()
    )
    return get_execution_response_data(activity, execution)


@router.get(
    "/{project_id}/activities/{activity_id}/progress-history",
    response_model=List[ProgressUpdateResponse],
    summary="Get chronological progress update audit history (Authorized users)",
)
def get_progress_history(
    project_id: int,
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve historical audit log of all execution reports submitted for an activity."""
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

    updates = (
        db.query(ProgressUpdate)
        .filter(ProgressUpdate.activity_id == activity_id)
        .order_by(ProgressUpdate.created_at.desc())
        .all()
    )

    results = []
    for u in updates:
        results.append(
            ProgressUpdateResponse(
                id=u.id,
                project_id=u.project_id,
                activity_id=u.activity_id,
                reported_by_id=u.reported_by_id,
                reported_by_name=u.reported_by.full_name if u.reported_by else None,
                update_type=u.update_type,
                reported_date=u.reported_date,
                progress_percentage=u.progress_percentage,
                remarks=u.remarks,
                source_type=u.source_type,
                created_at=u.created_at,
            )
        )
    return results


@router.get(
    "/{project_id}/execution-summary",
    response_model=ExecutionSummaryResponse,
    summary="Get overall project execution summary statistics (Authorized users)",
)
def get_project_execution_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve execution progress breakdown, status counts, overdue count, and average progress."""
    verify_project_access(project_id, current_user, db)
    return calculate_execution_summary(db, project_id)

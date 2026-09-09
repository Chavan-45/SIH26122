from datetime import datetime, timezone, date
from typing import List, Dict, Any, Tuple, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.schemas.execution import ProgressReportRequest, ExecutionSummaryResponse, ActivityExecutionResponse
from app.services.project_service import get_project_or_404, verify_project_access


def verify_supervisor_discipline_authorization(
    user: User,
    activity: Activity,
    project: Project,
    db: Session,
):
    """
    Enforce discipline-based RBAC.
    Supervisors can ONLY update progress for activities matching their assigned engineering discipline.
    Planners who own the project can update any activity in their project.
    """
    if user.role == "PLANNER":
        if project.created_by_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not own this project.",
            )
        return

    if user.role == "SUPERVISOR":
        membership = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == user.id,
            )
            .first()
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You are not assigned to this project.",
            )

        supervisor_discipline = membership.discipline.upper()
        activity_discipline = (activity.discipline or "UNASSIGNED").upper()

        if activity_discipline == "UNASSIGNED" or supervisor_discipline != activity_discipline:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: As a {supervisor_discipline} supervisor, you can only report progress on {supervisor_discipline} activities. Activity '{activity.activity_code}' has discipline '{activity_discipline}'.",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access forbidden: Role not authorized for progress updates.",
    )


def process_progress_update(
    db: Session,
    project_id: int,
    activity_id: int,
    user: User,
    report_req: ProgressReportRequest,
) -> Tuple[ActivityExecution, ProgressUpdate]:
    """
    Validates and applies an execution progress update in a single transaction.
    Protects baseline planned data while updating ActivityExecution and creating a ProgressUpdate audit log.
    """
    project = get_project_or_404(project_id, db)
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

    # Security check: discipline authorization
    verify_supervisor_discipline_authorization(user, activity, project, db)

    # Retrieve or create ActivityExecution record
    execution = (
        db.query(ActivityExecution)
        .filter(ActivityExecution.activity_id == activity_id)
        .first()
    )

    if not execution:
        execution = ActivityExecution(
            project_id=project_id,
            activity_id=activity_id,
            progress_percentage=0.0,
            execution_status="NOT_STARTED",
        )
        db.add(execution)

    current_status = execution.execution_status
    current_progress = execution.progress_percentage
    actual_start = execution.actual_start
    actual_finish = execution.actual_finish

    action = report_req.update_type.value
    rep_date = report_req.reported_date

    # Validate action rules
    if action == "START":
        if current_status == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot start activity: Activity is already COMPLETED.",
            )
        if actual_start is not None and user.role != "PLANNER":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Activity '{activity.activity_code}' has already been started on {actual_start}.",
            )

        execution.actual_start = rep_date
        execution.execution_status = "IN_PROGRESS"
        if report_req.progress_percentage is not None and report_req.progress_percentage > 0:
            execution.progress_percentage = report_req.progress_percentage

    elif action == "PROGRESS":
        if actual_start is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity must be started before progress can be reported.",
            )
        if current_status == "ON_HOLD":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity is currently ON_HOLD. You must RESUME the activity before updating progress.",
            )
        if current_status == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity is already COMPLETED. No further progress updates permitted.",
            )
        if rep_date < actual_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report date ({rep_date}) cannot be earlier than actual start date ({actual_start}).",
            )
        if report_req.progress_percentage is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Progress percentage is required for PROGRESS updates.",
            )
        if report_req.progress_percentage <= 0 or report_req.progress_percentage >= 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Progress percentage must be between 1% and 99% for incremental updates.",
            )
        if report_req.progress_percentage <= current_progress and user.role != "PLANNER":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Progress percentage cannot regress or stay the same (Current progress: {current_progress:.0f}%, Requested: {report_req.progress_percentage:.0f}%).",
            )

        execution.progress_percentage = report_req.progress_percentage
        execution.execution_status = "IN_PROGRESS"

    elif action == "COMPLETE":
        if actual_start is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity must be started before it can be completed.",
            )
        if current_status == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity is already completed.",
            )
        if rep_date < actual_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Actual finish date ({rep_date}) cannot be earlier than actual start date ({actual_start}).",
            )

        execution.actual_finish = rep_date
        execution.progress_percentage = 100.0
        execution.execution_status = "COMPLETED"

    elif action == "ON_HOLD":
        if actual_start is None or current_status != "IN_PROGRESS":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only IN_PROGRESS activities can be put ON_HOLD.",
            )
        if rep_date < actual_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"On-hold date ({rep_date}) cannot be earlier than actual start date ({actual_start}).",
            )

        execution.execution_status = "ON_HOLD"

    elif action == "RESUME":
        if current_status != "ON_HOLD":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only ON_HOLD activities can be resumed.",
            )
        if actual_start and rep_date < actual_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Resume date ({rep_date}) cannot be earlier than actual start date ({actual_start}).",
            )

        execution.execution_status = "IN_PROGRESS"

    execution.last_updated_by_id = user.id
    execution.last_updated_at = datetime.now(timezone.utc)

    # Append-only audit trail
    update_log = ProgressUpdate(
        project_id=project_id,
        activity_id=activity_id,
        reported_by_id=user.id,
        update_type=action,
        reported_date=rep_date,
        progress_percentage=execution.progress_percentage,
        remarks=report_req.remarks.strip() if report_req.remarks else None,
        source_type="MANUAL",
    )
    db.add(update_log)

    db.commit()
    db.refresh(execution)
    db.refresh(update_log)

    return execution, update_log


def get_execution_response_data(
    activity: Activity,
    execution: Optional[ActivityExecution],
) -> ActivityExecutionResponse:
    """Build response data structure including variance calculations."""
    act_start = execution.actual_start if execution else None
    act_finish = execution.actual_finish if execution else None
    prog = execution.progress_percentage if execution else 0.0
    exec_status = execution.execution_status if execution else "NOT_STARTED"
    updated_at = execution.last_updated_at if execution else None
    updated_by = execution.last_updated_by.full_name if execution and execution.last_updated_by else None

    # Calculate finish variance for COMPLETED activities
    finish_variance = None
    if act_finish and activity.planned_finish:
        finish_variance = (act_finish - activity.planned_finish).days

    # Calculate overdue days for incomplete activities
    current_overdue = None
    today = date.today()
    if exec_status != "COMPLETED" and activity.planned_finish and today > activity.planned_finish:
        current_overdue = (today - activity.planned_finish).days

    return ActivityExecutionResponse(
        id=execution.id if execution else None,
        project_id=activity.project_id,
        activity_id=activity.id,
        activity_code=activity.activity_code,
        activity_name=activity.activity_name,
        discipline=activity.discipline,
        planned_start=activity.planned_start,
        planned_finish=activity.planned_finish,
        actual_start=act_start,
        actual_finish=act_finish,
        progress_percentage=prog,
        execution_status=exec_status,
        last_updated_at=updated_at,
        last_updated_by_name=updated_by,
        finish_variance_days=finish_variance,
        current_overdue_days=current_overdue,
    )


def calculate_execution_summary(db: Session, project_id: int) -> ExecutionSummaryResponse:
    """
    Computes overall project execution summary statistics and count-weighted average progress.
    """
    activities = db.query(Activity).filter(Activity.project_id == project_id).all()
    total_activities = len(activities)

    if total_activities == 0:
        return ExecutionSummaryResponse(
            project_id=project_id,
            total_activities=0,
            not_started=0,
            in_progress=0,
            on_hold=0,
            completed=0,
            overdue=0,
            average_progress=0.0,
        )

    executions = (
        db.query(ActivityExecution)
        .filter(ActivityExecution.project_id == project_id)
        .all()
    )
    exec_map = {e.activity_id: e for e in executions}

    not_started = 0
    in_progress = 0
    on_hold = 0
    completed = 0
    overdue = 0
    total_progress_sum = 0.0

    today = date.today()

    for act in activities:
        e = exec_map.get(act.id)
        status_val = e.execution_status if e else "NOT_STARTED"
        prog_val = e.progress_percentage if e else 0.0
        total_progress_sum += prog_val

        if status_val == "NOT_STARTED":
            not_started += 1
        elif status_val == "IN_PROGRESS":
            in_progress += 1
        elif status_val == "ON_HOLD":
            on_hold += 1
        elif status_val == "COMPLETED":
            completed += 1

        if status_val != "COMPLETED" and act.planned_finish and today > act.planned_finish:
            overdue += 1

    avg_progress = round(total_progress_sum / total_activities, 2)

    return ExecutionSummaryResponse(
        project_id=project_id,
        total_activities=total_activities,
        not_started=not_started,
        in_progress=in_progress,
        on_hold=on_hold,
        completed=completed,
        overdue=overdue,
        average_progress=avg_progress,
    )

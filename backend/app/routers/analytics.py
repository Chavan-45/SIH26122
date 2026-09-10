from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_user
from app.services.project_service import verify_project_access
from app.services.analytics_service import (
    get_analytics_summary_data,
    get_progress_trend_data,
    get_discipline_analytics_data,
    get_schedule_risks_data,
    get_activity_forecasts_data,
    get_completed_performance_data,
)
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    ProgressTrendResponse,
    DisciplineAnalyticsResponse,
    ScheduleRiskResponse,
    ActivityForecastsResponse,
    CompletedPerformanceResponse,
)

router = APIRouter(prefix="/projects", tags=["Project Analytics & Forecasting"])


@router.get(
    "/{project_id}/analytics/summary",
    response_model=AnalyticsSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project analytics KPI summary and indicative completion metrics",
)
def get_analytics_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project, assigned_discipline = verify_project_access(project_id, current_user, db)
    return get_analytics_summary_data(
        db=db, project=project, user=current_user, assigned_discipline=assigned_discipline
    )


@router.get(
    "/{project_id}/analytics/progress-trend",
    response_model=ProgressTrendResponse,
    status_code=status.HTTP_200_OK,
    summary="Get historical actual vs expected progress trend series",
)
def get_progress_trend(
    project_id: int,
    range: str = Query("30d", pattern="^(7d|30d|90d|all)$", description="Trend horizon: 7d, 30d, 90d, all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project, assigned_discipline = verify_project_access(project_id, current_user, db)
    return get_progress_trend_data(
        db=db,
        project=project,
        user=current_user,
        assigned_discipline=assigned_discipline,
        range_key=range,
    )


@router.get(
    "/{project_id}/analytics/disciplines",
    response_model=DisciplineAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get discipline performance comparison metrics",
)
def get_discipline_analytics(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project, assigned_discipline = verify_project_access(project_id, current_user, db)
    return get_discipline_analytics_data(
        db=db, project=project, user=current_user, assigned_discipline=assigned_discipline
    )


@router.get(
    "/{project_id}/analytics/risks",
    response_model=ScheduleRiskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get rule-based schedule risk classification items",
)
def get_schedule_risks(
    project_id: int,
    level: Optional[str] = Query(None, description="Risk level filter: ALL, HIGH, MEDIUM, LOW"),
    discipline: Optional[str] = Query(None, description="Discipline filter (Planner only)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project, assigned_discipline = verify_project_access(project_id, current_user, db)

    # Supervisor discipline security enforcement
    if assigned_discipline:
        if discipline and discipline.upper() != "ALL" and discipline.upper() != assigned_discipline.upper():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Supervisors cannot query analytics outside their assigned discipline.",
            )
        discipline = assigned_discipline

    return get_schedule_risks_data(
        db=db,
        project=project,
        user=current_user,
        assigned_discipline=assigned_discipline,
        level_filter=level,
        discipline_filter=discipline,
    )


@router.get(
    "/{project_id}/analytics/forecast",
    response_model=ActivityForecastsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get deterministic activity finish forecasts and project coverage",
)
def get_activity_forecasts(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project, assigned_discipline = verify_project_access(project_id, current_user, db)
    return get_activity_forecasts_data(
        db=db, project=project, user=current_user, assigned_discipline=assigned_discipline
    )


@router.get(
    "/{project_id}/analytics/completed-performance",
    response_model=CompletedPerformanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get completed activity schedule performance variance",
)
def get_completed_performance(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project, assigned_discipline = verify_project_access(project_id, current_user, db)
    return get_completed_performance_data(
        db=db, project=project, user=current_user, assigned_discipline=assigned_discipline
    )

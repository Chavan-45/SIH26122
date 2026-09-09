from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.schemas.dashboard import ProjectDashboardResponse
from app.core.dependencies import get_current_user
from app.services.project_service import verify_project_access
from app.services.dashboard_service import get_project_dashboard_data

router = APIRouter(prefix="/projects", tags=["Project Dashboard"])


@router.get(
    "/{project_id}/dashboard",
    response_model=ProjectDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get 100% real database-derived project control dashboard metrics",
)
def get_project_dashboard(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns real-time project dashboard data:
    - Activity-weighted physical progress
    - Schedule health & status distribution
    - Discipline breakdown
    - Scheduled work today
    - Overdue carryover activities
    - 7-day upcoming deadlines
    - Recent site progress update feed
    - Baseline vs actual execution adherence
    - Supervisor-specific discipline operational summary (if applicable)
    """
    project, assigned_discipline = verify_project_access(project_id, current_user, db)
    return get_project_dashboard_data(
        db=db, project=project, user=current_user, assigned_discipline=assigned_discipline
    )

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.schemas.project import SupervisorSummary
from app.core.dependencies import require_planner

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/supervisors",
    response_model=List[SupervisorSummary],
    summary="List or search registered supervisors (Planner only)",
)
def search_supervisors(
    search: Optional[str] = Query(None, description="Filter by name or email"),
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Retrieve registered supervisors for project assignment."""
    query = db.query(User).filter(User.role == "SUPERVISOR", User.is_active == True)

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            (User.full_name.ilike(search_term)) | (User.email.ilike(search_term))
        )

    supervisors = query.order_by(User.full_name.asc()).limit(50).all()
    return supervisors

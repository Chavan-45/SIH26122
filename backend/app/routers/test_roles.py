from fastapi import APIRouter, Depends
from app.models.user import User
from app.core.dependencies import require_planner, require_supervisor

router = APIRouter(prefix="/test", tags=["Role Testing"])


@router.get(
    "/planner",
    summary="Test endpoint accessible only to PLANNER role",
)
def test_planner_access(
    current_user: User = Depends(require_planner),
):
    """Verify that the caller has authenticated as a PLANNER."""
    return {
        "status": "authorized",
        "role": current_user.role,
        "user": current_user.full_name,
        "message": "Access granted: Planner authorization verified",
    }


@router.get(
    "/supervisor",
    summary="Test endpoint accessible only to SUPERVISOR role",
)
def test_supervisor_access(
    current_user: User = Depends(require_supervisor),
):
    """Verify that the caller has authenticated as a SUPERVISOR."""
    return {
        "status": "authorized",
        "role": current_user.role,
        "user": current_user.full_name,
        "message": "Access granted: Supervisor authorization verified",
    }

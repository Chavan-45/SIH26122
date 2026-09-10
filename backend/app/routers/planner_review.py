from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.core.dependencies import require_planner
from app.services.project_service import verify_project_planner_owner
from app.schemas.planner_review import (
    PlannerReviewCaseSummary,
    PlannerReviewCaseListResponse,
    PlannerReviewCaseDetail,
    SelectActivityRequest,
    RejectCaseRequest,
    MarkUnplannedRequest,
)
from app.services.planner_review_service import (
    get_review_case_summary,
    list_review_cases,
    get_review_case_detail,
    select_case_activity,
    reject_case,
    mark_case_unplanned,
    apply_resolved_case,
)

router = APIRouter(prefix="/projects", tags=["Planner Review Center"])


@router.get(
    "/{project_id}/review-center/summary",
    response_model=PlannerReviewCaseSummary,
    summary="Get real DB counts for Planner Review Center summary cards (Planner only)",
)
def get_review_summary(
    project_id: int,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Returns database summary counts for unresolved and resolved review cases."""
    verify_project_planner_owner(project_id, current_user, db)
    return get_review_case_summary(db, project_id)


@router.get(
    "/{project_id}/review-center",
    response_model=PlannerReviewCaseListResponse,
    summary="List paginated review cases with filters (Planner only)",
)
def list_review_queue(
    project_id: int,
    status: Optional[str] = Query(None, description="Filter by decision (NEEDS_REVIEW, RESOLVED, REJECTED, UNPLANNED, APPLIED)"),
    source: Optional[str] = Query(None, description="Filter by source (AI_REPORT, PROGRESS_REPORT)"),
    discipline: Optional[str] = Query(None, description="Filter by discipline"),
    confidence: Optional[str] = Query(None, description="Filter by confidence (HIGH, MEDIUM, LOW, UNMATCHED)"),
    search: Optional[str] = Query(None, description="Search original update text, code, or reporter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Retrieves filtered, paginated list of field update review cases."""
    verify_project_planner_owner(project_id, current_user, db)
    return list_review_cases(
        db=db,
        project_id=project_id,
        status=status,
        source=source,
        discipline=discipline,
        confidence=confidence,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{project_id}/review-center/{case_id}",
    response_model=PlannerReviewCaseDetail,
    summary="Get detailed review case with candidate activities and validation (Planner only)",
)
def get_case_detail(
    project_id: int,
    case_id: int,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Retrieves full case detail, candidate activity matches, and state validation."""
    verify_project_planner_owner(project_id, current_user, db)
    return get_review_case_detail(db, project_id, case_id, current_user)


@router.post(
    "/{project_id}/review-center/{case_id}/select-activity",
    response_model=PlannerReviewCaseDetail,
    summary="Link an existing schedule activity to the review case (Planner only)",
)
def select_activity(
    project_id: int,
    case_id: int,
    req: SelectActivityRequest,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Links an activity and sets review decision to RESOLVED without immediately executing."""
    verify_project_planner_owner(project_id, current_user, db)
    return select_case_activity(
        db=db,
        project_id=project_id,
        case_id=case_id,
        activity_id=req.activity_id,
        planner_user=current_user,
        reason=req.review_reason,
    )


@router.post(
    "/{project_id}/review-center/{case_id}/reject",
    response_model=PlannerReviewCaseDetail,
    summary="Reject an update with mandatory reason (Planner only)",
)
def reject_review_case(
    project_id: int,
    case_id: int,
    req: RejectCaseRequest,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Rejects field update. Does not write to execution tables."""
    verify_project_planner_owner(project_id, current_user, db)
    return reject_case(
        db=db,
        project_id=project_id,
        case_id=case_id,
        planner_user=current_user,
        reason=req.review_reason,
    )


@router.post(
    "/{project_id}/review-center/{case_id}/mark-unplanned",
    response_model=PlannerReviewCaseDetail,
    summary="Mark update as genuine unplanned work without altering baseline (Planner only)",
)
def mark_unplanned_work(
    project_id: int,
    case_id: int,
    req: MarkUnplannedRequest,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Classifies update as unplanned work. Baseline activities remain untouched."""
    verify_project_planner_owner(project_id, current_user, db)
    return mark_case_unplanned(
        db=db,
        project_id=project_id,
        case_id=case_id,
        planner_user=current_user,
        reason=req.review_reason,
    )


@router.post(
    "/{project_id}/review-center/{case_id}/apply",
    response_model=PlannerReviewCaseDetail,
    summary="Apply resolved review case to actual execution via Phase 5 service (Planner only)",
)
def apply_case(
    project_id: int,
    case_id: int,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Applies resolved update transactionally via existing Phase 5 execution service."""
    verify_project_planner_owner(project_id, current_user, db)
    return apply_resolved_case(
        db=db,
        project_id=project_id,
        case_id=case_id,
        planner_user=current_user,
    )

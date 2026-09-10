import logging
from datetime import datetime, timezone, date
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.user import User
from app.models.project import Project
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.execution_report_draft import ExecutionReportDraft
from app.models.progress_report_item import ProgressReportItem
from app.models.progress_report_import import ProgressReportImport
from app.models.planner_review_case import PlannerReviewCase
from app.schemas.execution import ProgressReportRequest, UpdateTypeEnum
from app.schemas.planner_review import (
    PlannerReviewCaseSummary,
    PlannerReviewCandidateItem,
    PlannerReviewCaseListItem,
    PlannerReviewCaseDetail,
    PlannerReviewCaseListResponse,
)
from app.services.activity_matching_service import match_activity_for_report
from app.services.execution_service import process_progress_update
from app.services.batch_report_service import validate_item_execution_transition

logger = logging.getLogger(__name__)


def sync_planner_review_cases(db: Session, project_id: int) -> None:
    """
    Idempotent synchronization service that scans eligible unresolved Phase 8 (AI_REPORT)
    and Phase 9 (PROGRESS_REPORT) records and ensures exactly one PlannerReviewCase exists for each.
    Does NOT modify existing decisions or duplicate cases.
    """
    # 1. Scan Phase 8 ExecutionReportDraft items
    drafts = (
        db.query(ExecutionReportDraft)
        .filter(
            ExecutionReportDraft.project_id == project_id,
            ExecutionReportDraft.status.notin_(["CONFIRMED", "REJECTED"]),
            or_(
                ExecutionReportDraft.status == "NEEDS_PLANNER_REVIEW",
                ExecutionReportDraft.match_status.in_(["UNMATCHED", "LOW_CONFIDENCE", "MATCHED_MEDIUM"]),
                ExecutionReportDraft.matched_activity_id.is_(None),
            ),
        )
        .all()
    )

    for draft in drafts:
        existing = (
            db.query(PlannerReviewCase)
            .filter(
                PlannerReviewCase.project_id == project_id,
                PlannerReviewCase.source_type == "AI_REPORT",
                PlannerReviewCase.source_id == draft.id,
            )
            .first()
        )
        if not existing:
            new_case = PlannerReviewCase(
                project_id=project_id,
                source_type="AI_REPORT",
                source_id=draft.id,
                original_activity_id=draft.matched_activity_id,
                original_confidence=draft.match_confidence,
                decision="NEEDS_REVIEW",
            )
            db.add(new_case)

    # 2. Scan Phase 9 ProgressReportItem items
    report_items = (
        db.query(ProgressReportItem)
        .filter(
            ProgressReportItem.project_id == project_id,
            ProgressReportItem.review_status.notin_(["APPLIED", "REJECTED"]),
            or_(
                ProgressReportItem.match_status.in_(["UNMATCHED", "MATCHED_MEDIUM"]),
                ProgressReportItem.matched_activity_id.is_(None),
                ProgressReportItem.review_status.in_(["PENDING", "INVALID"]),
            ),
        )
        .all()
    )

    for item in report_items:
        existing = (
            db.query(PlannerReviewCase)
            .filter(
                PlannerReviewCase.project_id == project_id,
                PlannerReviewCase.source_type == "PROGRESS_REPORT",
                PlannerReviewCase.source_id == item.id,
            )
            .first()
        )
        if not existing:
            new_case = PlannerReviewCase(
                project_id=project_id,
                source_type="PROGRESS_REPORT",
                source_id=item.id,
                original_activity_id=item.matched_activity_id,
                original_confidence=item.match_confidence,
                decision="NEEDS_REVIEW",
            )
            db.add(new_case)

    db.commit()


def get_source_data(db: Session, case: PlannerReviewCase) -> Dict[str, Any]:
    """Extracts normalized metadata from the underlying source record without modifying it."""
    data = {
        "original_text": "Unknown field update",
        "reporter_name": "Unknown",
        "reporter_user": None,
        "reported_date": None,
        "discipline": None,
        "extracted_update_type": "PROGRESS",
        "extracted_progress_percentage": None,
        "remarks": None,
        "original_activity_id": case.original_activity_id,
        "original_activity_code": None,
        "original_activity_name": None,
        "original_confidence": case.original_confidence,
        "match_status": "UNMATCHED",
    }

    if case.source_type == "AI_REPORT":
        draft = (
            db.query(ExecutionReportDraft)
            .filter(ExecutionReportDraft.id == case.source_id)
            .first()
        )
        if draft:
            data["original_text"] = draft.original_text
            data["reporter_user"] = draft.reported_by
            data["reporter_name"] = draft.reported_by.full_name if draft.reported_by else "Supervisor"
            data["reported_date"] = draft.reported_date
            data["extracted_update_type"] = draft.update_type
            data["extracted_progress_percentage"] = draft.progress_percentage
            data["remarks"] = draft.remarks
            data["original_activity_id"] = draft.matched_activity_id
            data["original_confidence"] = draft.match_confidence
            data["match_status"] = draft.match_status

            if draft.matched_activity:
                data["original_activity_code"] = draft.matched_activity.activity_code
                data["original_activity_name"] = draft.matched_activity.activity_name
                data["discipline"] = draft.matched_activity.discipline
            elif draft.reported_by and draft.reported_by.project_memberships:
                mem = next((m for m in draft.reported_by.project_memberships if m.project_id == case.project_id), None)
                if mem:
                    data["discipline"] = mem.discipline

    elif case.source_type == "PROGRESS_REPORT":
        item = (
            db.query(ProgressReportItem)
            .filter(ProgressReportItem.id == case.source_id)
            .first()
        )
        if item:
            data["original_text"] = item.raw_description
            uploader = item.report.uploaded_by if item.report else None
            data["reporter_user"] = uploader
            data["reporter_name"] = uploader.full_name if uploader else "Supervisor"
            data["reported_date"] = item.reported_date
            data["extracted_update_type"] = item.extracted_update_type
            data["extracted_progress_percentage"] = item.extracted_progress_percentage
            data["remarks"] = item.remarks
            data["original_activity_id"] = item.matched_activity_id
            data["original_confidence"] = item.match_confidence
            data["match_status"] = item.match_status

            if item.matched_activity:
                data["original_activity_code"] = item.matched_activity.activity_code
                data["original_activity_name"] = item.matched_activity.activity_name
                data["discipline"] = item.matched_activity.discipline
            elif uploader and uploader.project_memberships:
                mem = next((m for m in uploader.project_memberships if m.project_id == case.project_id), None)
                if mem:
                    data["discipline"] = mem.discipline

    return data


def build_list_item(db: Session, case: PlannerReviewCase) -> PlannerReviewCaseListItem:
    """Builds list item representation for the Review Queue table."""
    source_info = get_source_data(db, case)

    selected_code = None
    selected_name = None
    if case.selected_activity:
        selected_code = case.selected_activity.activity_code
        selected_name = case.selected_activity.activity_name

    reviewer_name = case.reviewed_by.full_name if case.reviewed_by else None

    return PlannerReviewCaseListItem(
        id=case.id,
        project_id=case.project_id,
        source_type=case.source_type,
        source_id=case.source_id,
        original_text=source_info["original_text"],
        reporter_name=source_info["reporter_name"],
        reported_date=source_info["reported_date"],
        discipline=source_info["discipline"],
        extracted_update_type=source_info["extracted_update_type"],
        extracted_progress_percentage=source_info["extracted_progress_percentage"],
        remarks=source_info["remarks"],
        original_activity_id=source_info["original_activity_id"],
        original_activity_code=source_info["original_activity_code"],
        original_activity_name=source_info["original_activity_name"],
        original_confidence=source_info["original_confidence"],
        match_status=source_info["match_status"],
        selected_activity_id=case.selected_activity_id,
        selected_activity_code=selected_code,
        selected_activity_name=selected_name,
        decision=case.decision,
        review_reason=case.review_reason,
        reviewed_by_name=reviewer_name,
        reviewed_at=case.reviewed_at,
        applied_at=case.applied_at,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def get_review_case_summary(db: Session, project_id: int) -> PlannerReviewCaseSummary:
    """Calculates real database statistics for the 4 header summary cards."""
    sync_planner_review_cases(db, project_id)

    cases = (
        db.query(PlannerReviewCase)
        .filter(PlannerReviewCase.project_id == project_id)
        .all()
    )

    needs_review = 0
    low_confidence = 0
    unmatched = 0
    resolved = 0
    unplanned = 0
    rejected = 0
    applied = 0

    for c in cases:
        dec = c.decision
        if dec == "NEEDS_REVIEW":
            needs_review += 1
            conf = c.original_confidence or 0.0
            if c.original_activity_id is None:
                unmatched += 1
            elif conf < 0.65 or conf <= 0.85:
                low_confidence += 1
        elif dec == "RESOLVED":
            resolved += 1
        elif dec == "UNPLANNED":
            unplanned += 1
        elif dec == "REJECTED":
            rejected += 1
        elif dec == "APPLIED":
            applied += 1

    return PlannerReviewCaseSummary(
        needs_review=needs_review,
        low_confidence=low_confidence,
        unmatched=unmatched,
        resolved=resolved,
        unplanned=unplanned,
        rejected=rejected,
        applied=applied,
        total=len(cases),
    )


def list_review_cases(
    db: Session,
    project_id: int,
    status: Optional[str] = None,
    source: Optional[str] = None,
    discipline: Optional[str] = None,
    confidence: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> PlannerReviewCaseListResponse:
    """Lists filtered, paginated review cases for the project."""
    sync_planner_review_cases(db, project_id)

    query = (
        db.query(PlannerReviewCase)
        .filter(PlannerReviewCase.project_id == project_id)
        .order_by(PlannerReviewCase.created_at.desc(), PlannerReviewCase.id.desc())
    )

    if status and status.upper() != "ALL":
        query = query.filter(PlannerReviewCase.decision == status.upper())

    if source and source.upper() != "ALL":
        query = query.filter(PlannerReviewCase.source_type == source.upper())

    all_cases = query.all()
    filtered_items: List[PlannerReviewCaseListItem] = []

    for c in all_cases:
        item = build_list_item(db, c)

        # In-memory filtering for joined source properties
        if discipline and discipline.upper() != "ALL":
            if not item.discipline or item.discipline.upper() != discipline.upper():
                continue

        if confidence and confidence.upper() != "ALL":
            conf_val = item.original_confidence or 0.0
            if confidence.upper() == "HIGH" and conf_val < 0.85:
                continue
            elif confidence.upper() == "MEDIUM" and not (0.65 <= conf_val < 0.85):
                continue
            elif confidence.upper() == "LOW" and not (0.0 < conf_val < 0.65):
                continue
            elif confidence.upper() == "UNMATCHED" and (item.original_activity_id is not None and conf_val > 0.0):
                continue

        if search and search.strip():
            st = search.strip().lower()
            text_match = (
                st in item.original_text.lower()
                or (item.reporter_name and st in item.reporter_name.lower())
                or (item.original_activity_code and st in item.original_activity_code.lower())
                or (item.original_activity_name and st in item.original_activity_name.lower())
                or (item.selected_activity_code and st in item.selected_activity_code.lower())
                or (item.selected_activity_name and st in item.selected_activity_name.lower())
            )
            if not text_match:
                continue

        filtered_items.append(item)

    total = len(filtered_items)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_items = filtered_items[start_idx:end_idx]

    return PlannerReviewCaseListResponse(
        items=paged_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_review_case_detail(db: Session, project_id: int, case_id: int, user: User) -> PlannerReviewCaseDetail:
    """Loads detailed review case information including candidate matches and state validation."""
    case = (
        db.query(PlannerReviewCase)
        .filter(PlannerReviewCase.id == case_id, PlannerReviewCase.project_id == project_id)
        .first()
    )
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planner review case #{case_id} not found in this project.",
        )

    base_item = build_list_item(db, case)
    source_info = get_source_data(db, case)

    # 1. Generate top 5 activity candidate matches using Phase 8 matcher
    _, _, _, alternatives = match_activity_for_report(
        db=db,
        project_id=project_id,
        user_role="PLANNER",
        user_discipline=None,
        activity_description=source_info["original_text"],
        update_type=source_info["extracted_update_type"] or "PROGRESS",
    )

    candidates = [
        PlannerReviewCandidateItem(
            activity_id=alt["activity_id"],
            activity_code=alt["activity_code"],
            activity_name=alt["activity_name"],
            discipline=alt["discipline"],
            confidence=alt["confidence"],
            exec_status=alt["exec_status"],
        )
        for alt in alternatives[:5]
    ]

    # 2. Compute current vs proposed execution state & Phase 5 validation
    target_act_id = case.selected_activity_id or source_info["original_activity_id"]
    target_act = (
        db.query(Activity).filter(Activity.id == target_act_id, Activity.project_id == project_id).first()
        if target_act_id
        else None
    )

    current_status = None
    current_progress = None
    proposed_status = None
    proposed_progress = None
    validation_status = "VALID"
    validation_error = None

    if target_act:
        exec_obj = db.query(ActivityExecution).filter(ActivityExecution.activity_id == target_act.id).first()
        current_status = exec_obj.execution_status if exec_obj else "NOT_STARTED"
        current_progress = exec_obj.progress_percentage if exec_obj else 0.0

        up_type = source_info["extracted_update_type"] or "PROGRESS"
        raw_pct = source_info["extracted_progress_percentage"]

        if up_type == "START":
            proposed_status = "IN_PROGRESS"
            proposed_progress = raw_pct if (raw_pct is not None and raw_pct > 0) else current_progress
        elif up_type == "PROGRESS":
            proposed_status = "IN_PROGRESS"
            proposed_progress = raw_pct if raw_pct is not None else current_progress
        elif up_type == "COMPLETE":
            proposed_status = "COMPLETED"
            proposed_progress = 100.0
        elif up_type == "ON_HOLD":
            proposed_status = "ON_HOLD"
            proposed_progress = current_progress
        elif up_type == "RESUME":
            proposed_status = "IN_PROGRESS"
            proposed_progress = current_progress

        # Validate Phase 5 state machine transition
        val_stat, err_msg = validate_item_execution_transition(
            db=db,
            project_id=project_id,
            user=user,
            matched_activity=target_act,
            update_type=up_type,
            progress_percentage=raw_pct,
            reported_date=source_info["reported_date"],
        )
        validation_status = val_stat
        validation_error = err_msg
    else:
        validation_status = "INVALID"
        validation_error = "No schedule activity linked yet. Select an activity first."

    return PlannerReviewCaseDetail(
        id=base_item.id,
        project_id=base_item.project_id,
        source_type=base_item.source_type,
        source_id=base_item.source_id,
        original_text=base_item.original_text,
        reporter_name=base_item.reporter_name,
        reported_date=base_item.reported_date,
        discipline=base_item.discipline,
        extracted_update_type=base_item.extracted_update_type,
        extracted_progress_percentage=base_item.extracted_progress_percentage,
        remarks=base_item.remarks,
        original_activity_id=base_item.original_activity_id,
        original_activity_code=base_item.original_activity_code,
        original_activity_name=base_item.original_activity_name,
        original_confidence=base_item.original_confidence,
        match_status=base_item.match_status,
        selected_activity_id=base_item.selected_activity_id,
        selected_activity_code=base_item.selected_activity_code,
        selected_activity_name=base_item.selected_activity_name,
        decision=base_item.decision,
        review_reason=base_item.review_reason,
        reviewed_by_name=base_item.reviewed_by_name,
        reviewed_at=base_item.reviewed_at,
        applied_at=base_item.applied_at,
        created_at=base_item.created_at,
        updated_at=base_item.updated_at,
        candidates=candidates,
        validation_status=validation_status,
        validation_error=validation_error,
        current_execution_status=current_status,
        current_progress_percentage=current_progress,
        proposed_execution_status=proposed_status,
        proposed_progress_percentage=proposed_progress,
    )


def select_case_activity(
    db: Session,
    project_id: int,
    case_id: int,
    activity_id: int,
    planner_user: User,
    reason: Optional[str] = None,
) -> PlannerReviewCaseDetail:
    """Planner action to link an activity to an unresolved case without immediately applying."""
    case = (
        db.query(PlannerReviewCase)
        .filter(PlannerReviewCase.id == case_id, PlannerReviewCase.project_id == project_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail=f"Review case #{case_id} not found.")

    if case.decision == "APPLIED":
        raise HTTPException(status_code=409, detail="Applied cases cannot be modified.")

    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_id, Activity.project_id == project_id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail=f"Activity #{activity_id} not found in this project.")

    case.selected_activity_id = activity.id
    case.decision = "RESOLVED"
    case.reviewed_by_id = planner_user.id
    case.reviewed_at = datetime.now(timezone.utc)
    if reason:
        case.review_reason = reason.strip()
    case.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(case)

    return get_review_case_detail(db, project_id, case_id, planner_user)


def reject_case(
    db: Session,
    project_id: int,
    case_id: int,
    planner_user: User,
    reason: str,
) -> PlannerReviewCaseDetail:
    """Planner rejects field update with required reason. Does NOT write to ActivityExecution."""
    case = (
        db.query(PlannerReviewCase)
        .filter(PlannerReviewCase.id == case_id, PlannerReviewCase.project_id == project_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail=f"Review case #{case_id} not found.")

    if case.decision == "APPLIED":
        raise HTTPException(status_code=409, detail="Applied cases cannot be rejected.")

    case.decision = "REJECTED"
    case.reviewed_by_id = planner_user.id
    case.reviewed_at = datetime.now(timezone.utc)
    case.review_reason = reason.strip()
    case.updated_at = datetime.now(timezone.utc)

    # Sync underlying source record status
    if case.source_type == "AI_REPORT":
        draft = db.query(ExecutionReportDraft).filter(ExecutionReportDraft.id == case.source_id).first()
        if draft:
            draft.status = "REJECTED"
            draft.updated_at = datetime.now(timezone.utc)
    elif case.source_type == "PROGRESS_REPORT":
        item = db.query(ProgressReportItem).filter(ProgressReportItem.id == case.source_id).first()
        if item:
            item.review_status = "REJECTED"
            item.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(case)

    return get_review_case_detail(db, project_id, case_id, planner_user)


def mark_case_unplanned(
    db: Session,
    project_id: int,
    case_id: int,
    planner_user: User,
    reason: str,
) -> PlannerReviewCaseDetail:
    """Planner classifies genuine work as unplanned without modifying baseline activities."""
    case = (
        db.query(PlannerReviewCase)
        .filter(PlannerReviewCase.id == case_id, PlannerReviewCase.project_id == project_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail=f"Review case #{case_id} not found.")

    if case.decision == "APPLIED":
        raise HTTPException(status_code=409, detail="Applied cases cannot be marked unplanned.")

    case.decision = "UNPLANNED"
    case.reviewed_by_id = planner_user.id
    case.reviewed_at = datetime.now(timezone.utc)
    case.review_reason = reason.strip()
    case.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(case)

    return get_review_case_detail(db, project_id, case_id, planner_user)


def apply_resolved_case(
    db: Session,
    project_id: int,
    case_id: int,
    planner_user: User,
) -> PlannerReviewCaseDetail:
    """
    Applies a RESOLVED review case transactionally through the existing Phase 5 execution service.
    Guarantees idempotency and preserves original source/reporter audit metadata.
    """
    case = (
        db.query(PlannerReviewCase)
        .filter(PlannerReviewCase.id == case_id, PlannerReviewCase.project_id == project_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail=f"Review case #{case_id} not found.")

    if case.decision == "APPLIED":
        raise HTTPException(status_code=409, detail="Review case has already been applied.")

    if case.decision != "RESOLVED" or not case.selected_activity_id:
        raise HTTPException(
            status_code=400,
            detail="Review case must be in 'RESOLVED' state with a selected activity before applying.",
        )

    target_activity = (
        db.query(Activity)
        .filter(Activity.id == case.selected_activity_id, Activity.project_id == project_id)
        .first()
    )
    if not target_activity:
        raise HTTPException(status_code=404, detail="Selected activity not found.")

    source_info = get_source_data(db, case)
    up_type = source_info["extracted_update_type"] or "PROGRESS"
    raw_pct = source_info["extracted_progress_percentage"]
    rep_date = source_info["reported_date"] or date.today()

    # Re-validate transition before write
    val_status, err_msg = validate_item_execution_transition(
        db=db,
        project_id=project_id,
        user=planner_user,
        matched_activity=target_activity,
        update_type=up_type,
        progress_percentage=raw_pct,
        reported_date=rep_date,
    )
    if val_status == "INVALID":
        raise HTTPException(status_code=400, detail=f"Cannot apply update: {err_msg}")

    # Build Phase 5 ProgressReportRequest
    report_req = ProgressReportRequest(
        update_type=UpdateTypeEnum(up_type),
        reported_date=rep_date,
        progress_percentage=raw_pct if up_type in ["PROGRESS", "START"] else None,
        remarks=f"[Planner Resolved #{case.id}] {source_info['remarks'] or ''}".strip(),
    )

    source_type_tag = "AI_CHAT" if case.source_type == "AI_REPORT" else "REPORT_IMPORT"

    # Delegate execution update transactionally to Phase 5 engine
    process_progress_update(
        db=db,
        project_id=project_id,
        activity_id=case.selected_activity_id,
        user=planner_user,
        report_req=report_req,
        source_type=source_type_tag,
        allow_planner_resolution=True,
        override_reporter=source_info["reporter_user"],
    )

    # Update Review Case status to APPLIED
    case.decision = "APPLIED"
    case.applied_at = datetime.now(timezone.utc)
    case.updated_at = datetime.now(timezone.utc)

    # Sync underlying source record status
    if case.source_type == "AI_REPORT":
        draft = db.query(ExecutionReportDraft).filter(ExecutionReportDraft.id == case.source_id).first()
        if draft:
            draft.status = "CONFIRMED"
            draft.matched_activity_id = case.selected_activity_id
            draft.match_status = "MANUALLY_SELECTED"
            draft.updated_at = datetime.now(timezone.utc)
    elif case.source_type == "PROGRESS_REPORT":
        item = db.query(ProgressReportItem).filter(ProgressReportItem.id == case.source_id).first()
        if item:
            item.review_status = "APPLIED"
            item.matched_activity_id = case.selected_activity_id
            item.match_status = "MANUALLY_SELECTED"
            item.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(case)

    return get_review_case_detail(db, project_id, case_id, planner_user)

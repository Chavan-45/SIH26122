import json
import logging
from datetime import datetime, timezone, date
from typing import List, Dict, Any, Optional
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.activity import Activity
from app.models.progress_report_import import ProgressReportImport
from app.models.progress_report_item import ProgressReportItem
from app.schemas.execution import ProgressReportRequest, UpdateTypeEnum
from app.schemas.progress_report import (
    TextReportImportRequest,
    ColumnMappingRequest,
    SelectReportItemActivityRequest,
    ReviewReportItemRequest,
    ProgressReportItemResponse,
    ProgressReportImportResponse,
    ProgressReportImportListItem,
)
from app.core.dependencies import get_current_user
from app.services.project_service import get_project_or_404, verify_project_access, get_user_assigned_discipline
from app.services.activity_matching_service import match_activity_for_report
from app.services.execution_service import process_progress_update, verify_supervisor_discipline_authorization
from app.services.batch_report_service import (
    read_report_file,
    auto_detect_report_mapping,
    parse_execution_intent,
    parse_date_value,
    extract_items_from_text_dpr,
    validate_item_execution_transition,
    build_report_item_response,
    build_report_import_response,
)
from app.services.document_report_service import process_document_progress_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Progress Report Ingestion"])


@router.post(
    "/{project_id}/progress-reports/preview-spreadsheet",
    summary="Preview spreadsheet columns and auto-detected mapping for progress report import",
)
async def preview_report_spreadsheet(
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Parses CSV/XLSX headers, returns row count, detected mapping, and preview rows."""
    verify_project_access(project_id, current_user, db)

    df, file_type, filename = await read_report_file(file)
    headers = [str(c) for c in df.columns]
    detected_mapping = auto_detect_report_mapping(headers)

    preview_slice = df.head(15).fillna("").to_dict(orient="records")

    return {
        "filename": filename,
        "file_type": file_type,
        "row_count": len(df),
        "headers": headers,
        "detected_mapping": detected_mapping,
        "preview_rows": preview_slice,
    }


@router.post(
    "/{project_id}/progress-reports/import-spreadsheet",
    response_model=ProgressReportImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import spreadsheet progress report with column mapping",
)
async def import_report_spreadsheet(
    project_id: int,
    file: UploadFile = File(...),
    mapping_json: str = "{}",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Imports CSV/XLSX report items, runs activity matching, and creates persistent ProgressReportImport session in REVIEW state.
    """
    project, user_discipline = verify_project_access(project_id, current_user, db)

    df, file_type, filename = await read_report_file(file)
    headers = [str(c) for c in df.columns]

    mapping = {}
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
        except Exception:
            mapping = {}

    if not mapping:
        mapping = auto_detect_report_mapping(headers)

    desc_col = mapping.get("description") or mapping.get("activity_code") or headers[0]
    code_col = mapping.get("activity_code")
    prog_col = mapping.get("progress_percentage")
    type_col = mapping.get("update_type")
    date_col = mapping.get("reported_date")
    remarks_col = mapping.get("remarks")

    report_import = ProgressReportImport(
        project_id=project_id,
        uploaded_by_id=current_user.id,
        source_type=file_type,
        original_filename=filename,
        status="REVIEW",
    )
    db.add(report_import)
    db.commit()
    db.refresh(report_import)

    report_items = []
    for idx, row in df.iterrows():
        raw_desc = str(row.get(desc_col) or "").strip()
        if not raw_desc and code_col:
            raw_desc = str(row.get(code_col) or "").strip()
        if not raw_desc:
            continue

        explicit_code = str(row.get(code_col) or "").strip() if code_col else None
        raw_status = row.get(type_col) if type_col else None
        raw_prog = row.get(prog_col) if prog_col else None
        up_type, pct_val = parse_execution_intent(raw_status, raw_prog)

        raw_d = row.get(date_col) if date_col else None
        rep_date = parse_date_value(raw_d)

        raw_rem = str(row.get(remarks_col)).strip() if remarks_col and not pd.isna(row.get(remarks_col)) else None

        # Execute Phase 8 activity matching
        matched_act, confidence, match_status, _ = match_activity_for_report(
            db=db,
            project_id=project_id,
            user_role=current_user.role,
            user_discipline=user_discipline,
            explicit_activity_code=explicit_code,
            activity_description=raw_desc,
            update_type=up_type,
        )

        item = ProgressReportItem(
            report_id=report_import.id,
            project_id=project_id,
            raw_description=raw_desc,
            reported_date=rep_date,
            extracted_update_type=up_type,
            extracted_progress_percentage=pct_val,
            remarks=raw_rem,
            matched_activity_id=matched_act.id if matched_act else None,
            match_confidence=confidence,
            match_status=match_status,
            review_status="PENDING",
        )
        report_items.append(item)

    if not report_items:
        db.delete(report_import)
        db.commit()
        raise HTTPException(status_code=400, detail="No valid work update rows found in file.")

    db.bulk_save_objects(report_items)
    db.commit()

    db.refresh(report_import)
    return build_report_import_response(db, report_import, current_user)


@router.post(
    "/{project_id}/progress-reports/import-text",
    response_model=ProgressReportImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import pasted free-text Daily Progress Report (DPR)",
)
def import_report_text(
    project_id: int,
    req: TextReportImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Parses multi-item pasted site text report into individual work updates, runs activity matching,
    and creates persistent ProgressReportImport session in REVIEW state.
    """
    project, user_discipline = verify_project_access(project_id, current_user, db)

    raw_text = req.raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Pasted report text cannot be empty.")

    extracted_items = extract_items_from_text_dpr(raw_text)
    if not extracted_items:
        raise HTTPException(status_code=400, detail="Could not extract any work update items from text report.")

    report_import = ProgressReportImport(
        project_id=project_id,
        uploaded_by_id=current_user.id,
        source_type="TEXT",
        raw_text=raw_text,
        status="REVIEW",
    )
    db.add(report_import)
    db.commit()
    db.refresh(report_import)

    report_items = []
    for ext_item in extracted_items:
        raw_desc = ext_item["raw_description"]
        up_type = ext_item["extracted_update_type"] or "PROGRESS"
        pct_val = ext_item["extracted_progress_percentage"]
        rep_date = ext_item["reported_date"]
        remarks = ext_item["remarks"]

        # Match activity using Phase 8 matcher
        matched_act, confidence, match_status, _ = match_activity_for_report(
            db=db,
            project_id=project_id,
            user_role=current_user.role,
            user_discipline=user_discipline,
            activity_description=raw_desc,
            update_type=up_type,
        )

        item = ProgressReportItem(
            report_id=report_import.id,
            project_id=project_id,
            raw_description=raw_desc,
            reported_date=rep_date,
            extracted_update_type=up_type,
            extracted_progress_percentage=pct_val,
            remarks=remarks,
            matched_activity_id=matched_act.id if matched_act else None,
            match_confidence=confidence,
            match_status=match_status,
            review_status="PENDING",
        )
        report_items.append(item)

    db.bulk_save_objects(report_items)
    db.commit()

    db.refresh(report_import)
    return build_report_import_response(db, report_import, current_user)


@router.post(
    "/{project_id}/progress-reports/import-document",
    response_model=ProgressReportImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import site document (PDF, JPG, JPEG, PNG) and extract structured work updates",
)
@router.post(
    "/{project_id}/progress-reports/document",
    response_model=ProgressReportImportResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def import_report_document(
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ingests PDF progress reports (text or scanned) or site images (JPG, PNG).
    Extracts structured updates, executes activity matching, and returns a ProgressReportImport in REVIEW status.
    """
    project, user_discipline = verify_project_access(project_id, current_user, db)

    report_import = await process_document_progress_report(
        db=db,
        project=project,
        user=current_user,
        user_discipline=user_discipline,
        file=file,
    )

    return build_report_import_response(db, report_import, current_user)


@router.get(
    "/{project_id}/progress-reports",
    response_model=List[ProgressReportImportListItem],
    summary="List all progress report import sessions for project",
)
def list_progress_reports(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves history of progress report import sessions for project."""
    verify_project_access(project_id, current_user, db)

    reports = (
        db.query(ProgressReportImport)
        .filter(ProgressReportImport.project_id == project_id)
        .order_by(ProgressReportImport.created_at.desc())
        .all()
    )

    results = []
    for r in reports:
        items = db.query(ProgressReportItem).filter(ProgressReportItem.report_id == r.id).all()
        total_items = len(items)
        pending_items = sum(1 for it in items if it.review_status == "PENDING")
        approved_items = sum(1 for it in items if it.review_status == "APPROVED")
        applied_items = sum(1 for it in items if it.review_status == "APPLIED")
        invalid_items = sum(
            1 for it in items
            if validate_item_execution_transition(
                db, project_id, current_user, it.matched_activity, it.extracted_update_type, it.extracted_progress_percentage, it.reported_date
            )[0] == "INVALID"
        )

        uploader_name = r.uploaded_by.full_name if r.uploaded_by else "Unknown"

        page_count = None
        extraction_method = None
        if r.raw_text and r.raw_text.strip().startswith("{"):
            try:
                meta = json.loads(r.raw_text)
                page_count = meta.get("page_count")
                extraction_method = meta.get("extraction_method")
            except Exception:
                pass

        results.append(
            ProgressReportImportListItem(
                id=r.id,
                project_id=r.project_id,
                uploaded_by_id=r.uploaded_by_id,
                uploaded_by_name=uploader_name,
                source_type=r.source_type,
                original_filename=r.original_filename,
                page_count=page_count,
                extraction_method=extraction_method,
                status=r.status,
                total_items=total_items,
                pending_items=pending_items,
                approved_items=approved_items,
                applied_items=applied_items,
                invalid_items=invalid_items,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )

    return results


@router.get(
    "/{project_id}/progress-reports/{report_id}",
    response_model=ProgressReportImportResponse,
    summary="Get progress report details and review items",
)
def get_progress_report(
    project_id: int,
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves progress report import session details and review items."""
    verify_project_access(project_id, current_user, db)

    report = (
        db.query(ProgressReportImport)
        .filter(ProgressReportImport.id == report_id, ProgressReportImport.project_id == project_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail=f"Progress report session #{report_id} not found.")

    return build_report_import_response(db, report, current_user)


@router.post(
    "/{project_id}/progress-reports/{report_id}/items/{item_id}/review",
    response_model=ProgressReportItemResponse,
    summary="Approve or Reject an individual progress report item",
)
def review_progress_report_item(
    project_id: int,
    report_id: int,
    item_id: int,
    req: ReviewReportItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approves or rejects a specific item in the progress report session."""
    verify_project_access(project_id, current_user, db)

    item = (
        db.query(ProgressReportItem)
        .filter(
            ProgressReportItem.id == item_id,
            ProgressReportItem.report_id == report_id,
            ProgressReportItem.project_id == project_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail=f"Report item #{item_id} not found.")

    if item.review_status == "APPLIED":
        raise HTTPException(status_code=409, detail="Applied items cannot be modified.")

    action_clean = req.action.strip().upper()
    if action_clean == "APPROVE":
        # Validate item state transition first
        val_status, err_msg = validate_item_execution_transition(
            db, project_id, current_user, item.matched_activity, item.extracted_update_type, item.extracted_progress_percentage, item.reported_date
        )
        if val_status == "INVALID":
            raise HTTPException(status_code=400, detail=f"Cannot approve item: {err_msg}")

        item.review_status = "APPROVED"
    elif action_clean == "REJECT":
        item.review_status = "REJECTED"
    else:
        raise HTTPException(status_code=400, detail="Invalid review action. Must be 'APPROVE' or 'REJECT'.")

    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)

    return build_report_item_response(db, item, current_user)


@router.post(
    "/{project_id}/progress-reports/{report_id}/items/{item_id}/select-activity",
    response_model=ProgressReportItemResponse,
    summary="Manually assign schedule activity to a progress report item",
)
def select_report_item_activity(
    project_id: int,
    report_id: int,
    item_id: int,
    req: SelectReportItemActivityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually links a schedule activity to a report item."""
    project, assigned_discipline = verify_project_access(project_id, current_user, db)

    item = (
        db.query(ProgressReportItem)
        .filter(
            ProgressReportItem.id == item_id,
            ProgressReportItem.report_id == report_id,
            ProgressReportItem.project_id == project_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail=f"Report item #{item_id} not found.")

    if item.review_status == "APPLIED":
        raise HTTPException(status_code=409, detail="Applied items cannot be re-linked.")

    activity = (
        db.query(Activity)
        .filter(Activity.project_id == project_id, Activity.id == req.activity_id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail=f"Activity #{req.activity_id} not found.")

    # Check Supervisor discipline authorization if user is a Supervisor
    if current_user.role == "SUPERVISOR":
        verify_supervisor_discipline_authorization(current_user, activity, project, db)

    item.matched_activity_id = activity.id
    item.match_status = "MANUALLY_SELECTED"
    item.match_confidence = None
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)

    return build_report_item_response(db, item, current_user)


@router.post(
    "/{project_id}/progress-reports/{report_id}/bulk-approve",
    response_model=ProgressReportImportResponse,
    summary="Approve all valid pending items in the report session",
)
def bulk_approve_report_items(
    project_id: int,
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approves all pending items that pass state transition and RBAC validation."""
    verify_project_access(project_id, current_user, db)

    report = (
        db.query(ProgressReportImport)
        .filter(ProgressReportImport.id == report_id, ProgressReportImport.project_id == project_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail=f"Progress report session #{report_id} not found.")

    items = db.query(ProgressReportItem).filter(ProgressReportItem.report_id == report_id, ProgressReportItem.review_status == "PENDING").all()

    for item in items:
        val_status, _ = validate_item_execution_transition(
            db, project_id, current_user, item.matched_activity, item.extracted_update_type, item.extracted_progress_percentage, item.reported_date
        )
        if val_status == "VALID":
            item.review_status = "APPROVED"
            item.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(report)

    return build_report_import_response(db, report, current_user)


@router.post(
    "/{project_id}/progress-reports/{report_id}/apply",
    response_model=ProgressReportImportResponse,
    summary="Apply all approved progress report items via existing Phase 5 execution service",
)
def apply_progress_report(
    project_id: int,
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Applies all APPROVED report items transactionally using the existing Phase 5 execution service (process_progress_update).
    Field execution updates must be reported by an assigned Supervisor for their discipline.
    """
    project, assigned_discipline = verify_project_access(project_id, current_user, db)

    if current_user.role != "SUPERVISOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Field progress execution updates must be applied by an assigned Supervisor.",
        )

    report = (
        db.query(ProgressReportImport)
        .filter(ProgressReportImport.id == report_id, ProgressReportImport.project_id == project_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail=f"Progress report session #{report_id} not found.")

    approved_items = (
        db.query(ProgressReportItem)
        .filter(ProgressReportItem.report_id == report_id, ProgressReportItem.review_status == "APPROVED")
        .all()
    )

    if not approved_items:
        raise HTTPException(status_code=400, detail="No APPROVED items ready to apply in this report session.")

    applied_count = 0
    error_messages = []

    for item in approved_items:
        # Re-validate item before execution
        val_status, err_msg = validate_item_execution_transition(
            db, project_id, current_user, item.matched_activity, item.extracted_update_type, item.extracted_progress_percentage, item.reported_date
        )
        if val_status == "INVALID":
            item.review_status = "INVALID"
            item.error_message = err_msg
            error_messages.append(f"Item #{item.id} ('{item.raw_description}'): {err_msg}")
            continue

        try:
            report_req = ProgressReportRequest(
                update_type=UpdateTypeEnum(item.extracted_update_type),
                reported_date=item.reported_date or date.today(),
                progress_percentage=item.extracted_progress_percentage if item.extracted_update_type in ["PROGRESS", "START"] else None,
                remarks=f"[Report Import #{report.id}] {item.remarks or ''}".strip(),
            )

            # Delegate execution transactionally to existing Phase 5 execution service
            process_progress_update(
                db=db,
                project_id=project_id,
                activity_id=item.matched_activity_id,
                user=current_user,
                report_req=report_req,
                source_type="REPORT_IMPORT",
            )

            item.review_status = "APPLIED"
            item.error_message = None
            item.updated_at = datetime.now(timezone.utc)
            applied_count += 1
        except Exception as e:
            item.review_status = "INVALID"
            item.error_message = str(e)
            error_messages.append(f"Item #{item.id} ('{item.raw_description}'): {str(e)}")

    # Update overall report import status
    all_items = db.query(ProgressReportItem).filter(ProgressReportItem.report_id == report_id).all()
    all_applied = all(it.review_status == "APPLIED" for it in all_items)
    any_applied = any(it.review_status == "APPLIED" for it in all_items)

    if all_applied:
        report.status = "APPLIED"
    elif any_applied:
        report.status = "PARTIALLY_APPLIED"
    report.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(report)

    return build_report_import_response(db, report, current_user)

import io
import json
import os
import re
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session
from google import genai
from google.genai import types

from app.core.config import settings
from app.models.user import User
from app.models.project import Project
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_report_import import ProgressReportImport
from app.models.progress_report_item import ProgressReportItem
from app.schemas.execution import ProgressReportRequest, UpdateTypeEnum
from app.schemas.progress_report import (
    ProgressReportItemResponse,
    ProgressReportImportResponse,
    ProgressReportImportListItem,
)
from app.services.activity_matching_service import match_activity_for_report
from app.services.execution_service import process_progress_update, verify_supervisor_discipline_authorization
from app.services.project_service import get_project_or_404, get_user_assigned_discipline

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ROW_LIMIT = 2000

REPORT_CANONICAL_FIELDS = {
    "activity_code": {
        "required": False,
        "aliases": ["activity_code", "activity code", "activity_id", "activity id", "code", "id", "activity"],
    },
    "description": {
        "required": True,
        "aliases": [
            "description", "work_description", "work description", "task name",
            "activity name", "details", "item", "activity", "work_item"
        ],
    },
    "progress_percentage": {
        "required": False,
        "aliases": [
            "progress", "progress_percentage", "progress percentage", "percent",
            "percent complete", "percent_complete", "% complete", "progress %", "progress%"
        ],
    },
    "update_type": {
        "required": False,
        "aliases": ["status", "update_type", "update type", "action", "execution status", "state"],
    },
    "reported_date": {
        "required": False,
        "aliases": ["date", "reported_date", "reported date", "log date", "entry date", "report date"],
    },
    "remarks": {
        "required": False,
        "aliases": ["remarks", "comments", "notes", "remark", "comment"],
    },
}


def normalize_header(header: str) -> str:
    """Normalize header text by stripping, lowercasing, and replacing punctuation."""
    return re.sub(r"[_\-\s]+", " ", str(header).strip().lower())


def auto_detect_report_mapping(df_columns: List[str]) -> Dict[str, Optional[str]]:
    """Attempt auto-mapping of spreadsheet columns to report canonical fields."""
    detected_mapping: Dict[str, Optional[str]] = {field: None for field in REPORT_CANONICAL_FIELDS}
    normalized_cols = {col: normalize_header(col) for col in df_columns}

    for field, config in REPORT_CANONICAL_FIELDS.items():
        aliases = [normalize_header(a) for a in config["aliases"]]

        # Exact normalized match
        for original_col, norm_col in normalized_cols.items():
            if norm_col in aliases:
                detected_mapping[field] = original_col
                break

        # Partial match if not matched
        if not detected_mapping[field]:
            for original_col, norm_col in normalized_cols.items():
                for alias in aliases:
                    if alias in norm_col or norm_col in alias:
                        detected_mapping[field] = original_col
                        break
                if detected_mapping[field]:
                    break

    return detected_mapping


def parse_execution_intent(raw_status: Any, raw_progress: Any) -> Tuple[str, Optional[float]]:
    """
    Deterministically normalizes status/action and progress percentage.
    Reuses Phase 8 semantics:
    - "20% completed" -> PROGRESS 20%
    - "75% complete" -> PROGRESS 75%
    - "100% complete" / "completed" -> COMPLETE 100%
    - "started" -> START
    - "on hold" -> ON_HOLD
    - "resumed" -> RESUME
    """
    status_str = str(raw_status or "").strip().lower()

    # Extract percentage numbers from status string or raw progress
    pct_val = None
    if raw_progress is not None and not pd.isna(raw_progress) and str(raw_progress).strip() != "":
        try:
            match = re.search(r"[-+]?\d*\.\d+|\d+", str(raw_progress).strip())
            if match:
                pct_val = float(match.group())
        except (ValueError, TypeError):
            pass

    if pct_val is None:
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", status_str)
        if pct_match:
            try:
                pct_val = float(pct_match.group(1))
            except ValueError:
                pass

    update_type = "PROGRESS"

    if "on hold" in status_str or "paused" in status_str or "suspended" in status_str:
        update_type = "ON_HOLD"
    elif "resum" in status_str or "restart" in status_str:
        update_type = "RESUME"
    elif "start" in status_str or "begin" in status_str or "commenc" in status_str:
        update_type = "START"
        if pct_val is None:
            pct_val = 0.0
    elif "100" in status_str or "complete" in status_str or "done" in status_str or "finish" in status_str:
        if pct_val is not None and pct_val < 100.0 and "100" not in status_str:
            update_type = "PROGRESS"
        else:
            update_type = "COMPLETE"
            pct_val = 100.0
    else:
        if pct_val == 100.0:
            update_type = "COMPLETE"
        elif pct_val == 0.0:
            update_type = "START"
        else:
            update_type = "PROGRESS"

    if update_type == "COMPLETE":
        pct_val = 100.0

    return update_type, pct_val


def parse_date_value(val: Any) -> Optional[date]:
    """Parse cell/text date value into date object or return None."""
    if pd.isna(val) or val is None or str(val).strip() == "":
        return date.today()

    if isinstance(val, (datetime, date)):
        if isinstance(val, datetime):
            return val.date()
        return val

    val_str = str(val).strip()

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass

    try:
        dt = pd.to_datetime(val_str, dayfirst=True)
        if not pd.isna(dt):
            return dt.date()
    except Exception:
        pass

    return date.today()


async def read_report_file(file: UploadFile) -> Tuple[pd.DataFrame, str, str]:
    """Read UploadFile into DataFrame after validating size and format."""
    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    if ext not in ["csv", "xlsx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '.{ext}'. Supported report formats are .csv and .xlsx.",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum limit of 10 MB ({len(content) / (1024 * 1024):.2f} MB upload).",
        )

    try:
        file_bytes = io.BytesIO(content)
        if ext == "csv":
            df = pd.read_csv(file_bytes)
        else:
            df = pd.read_excel(file_bytes, sheet_name=0)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse report file content: {str(e)}",
        )

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded progress report contains no data rows.",
        )

    if len(df) > MAX_ROW_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report exceeds maximum row limit of {MAX_ROW_LIMIT} items.",
        )

    return df, ext.upper(), filename


def extract_items_from_text_dpr(raw_text: str) -> List[Dict[str, Any]]:
    """
    Splits multi-line free text DPR into individual progress report items.
    Uses regex heuristic parsing + optional Gemini structured output.
    """
    text_content = raw_text.strip()
    if not text_content:
        return []

    # Check for date line at top of report (e.g. "Date: 10 Sep 2026")
    report_date = date.today()
    date_match = re.search(r"\bdate\s*:\s*([0-9A-Za-z\s\-\/]+)", text_content, re.IGNORECASE)
    if date_match:
        report_date = parse_date_value(date_match.group(1).strip())

    items: List[Dict[str, Any]] = []

    # Gemini Structured JSON Extraction if key present
    api_key = (settings.GEMINI_API_KEY or "").strip() or os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"

            prompt = f"""
You are an expert civil & infrastructure project engineer parsing a daily site progress report (DPR).
Split the site report below into individual activity work updates.

Return ONLY a JSON array of objects with the following schema:
[
  {{
    "raw_description": "short description of work item or activity code",
    "extracted_update_type": "START" | "PROGRESS" | "COMPLETE" | "ON_HOLD" | "RESUME",
    "extracted_progress_percentage": float | null,
    "reported_date": "YYYY-MM-DD" or null,
    "remarks": "any extra notes or null"
  }}
]

Strict Rules:
1. Do NOT invent items.
2. If "20% completed" -> update_type="PROGRESS", progress_percentage=20.0
3. If "100% completed" or "completed" -> update_type="COMPLETE", progress_percentage=100.0
4. If "started" -> update_type="START"
5. Do NOT output Markdown formatting outside the JSON block.

Site Report:
{text_content}
"""
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )

            raw_json = response.text or ""
            parsed_data = json.loads(raw_json)
            if isinstance(parsed_data, list):
                for obj in parsed_data:
                    desc = str(obj.get("raw_description") or "").strip()
                    if desc:
                        up_type = obj.get("extracted_update_type") or "PROGRESS"
                        prog = obj.get("extracted_progress_percentage")
                        if prog is not None:
                            try: prog = float(prog)
                            except: prog = None
                        d_str = obj.get("reported_date")
                        rep_d = parse_date_value(d_str) if d_str else report_date
                        items.append({
                            "raw_description": desc,
                            "extracted_update_type": up_type,
                            "extracted_progress_percentage": prog,
                            "reported_date": rep_d,
                            "remarks": str(obj.get("remarks") or "").strip() or None,
                        })
                if items:
                    return items
        except Exception as e:
            logger.warning(f"Gemini DPR text extraction failed ({e}), falling back to deterministic regex parser.")

    # Fallback Deterministic Regex Parsing
    lines = text_content.split("\n")
    current_discipline_prefix = ""

    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue

        # Ignore standalone header lines like "Date: 10 Sep 2026"
        if cleaned.lower().startswith("date:") or cleaned.lower().startswith("daily progress report"):
            continue

        # Discipline section headers like "Civil:", "Piping:", "Electrical:"
        disc_header_match = re.match(r"^([A-Za-z\s]+)\s*:$", cleaned)
        if disc_header_match and disc_header_match.group(1).upper() in ["CIVIL", "PIPING", "ELECTRICAL", "INSTRUMENTATION", "MECHANICAL", "STRUCTURAL", "HSE"]:
            current_discipline_prefix = disc_header_match.group(1).strip()
            continue

        # Strip bullet prefixes like "-", "*", "1.", "•"
        bullet_clean = re.sub(r"^[\-\*\•\d\.\)]+\s*", "", cleaned).strip()
        if not bullet_clean:
            continue

        up_type, pct_val = parse_execution_intent(bullet_clean, None)

        desc = bullet_clean
        if current_discipline_prefix and not desc.lower().startswith(current_discipline_prefix.lower()):
            desc = f"{desc}"

        items.append({
            "raw_description": desc,
            "extracted_update_type": up_type,
            "extracted_progress_percentage": pct_val,
            "reported_date": report_date,
            "remarks": None,
        })

    return items


def validate_item_execution_transition(
    db: Session,
    project_id: int,
    user: User,
    matched_activity: Optional[Activity],
    update_type: Optional[str],
    progress_percentage: Optional[float],
    reported_date: Optional[date],
) -> Tuple[str, Optional[str]]:
    """
    Validates item against existing ActivityExecution state & discipline RBAC.
    Returns (validation_status: "VALID" | "INVALID", error_message: str | None).
    """
    if not matched_activity:
        return "INVALID", "Unmatched activity: Schedule activity must be assigned before applying update."

    # Check Discipline RBAC for Supervisors
    assigned_disc = get_user_assigned_discipline(user, project_id, db)
    if user.role == "SUPERVISOR":
        if not assigned_disc:
            return "INVALID", "Supervisor is not assigned to any discipline in this project."
        act_disc = (matched_activity.discipline or "UNASSIGNED").strip().upper()
        if act_disc != assigned_disc.upper():
            return "INVALID", f"Access forbidden: You are assigned to {assigned_disc}, but activity '{matched_activity.activity_code}' belongs to {act_disc}."

    # Retrieve current execution state
    exec_obj = db.query(ActivityExecution).filter(ActivityExecution.activity_id == matched_activity.id).first()
    cur_status = exec_obj.execution_status if exec_obj else "NOT_STARTED"
    cur_prog = exec_obj.progress_percentage if exec_obj else 0.0
    actual_start = exec_obj.actual_start if exec_obj else None

    action = update_type or "PROGRESS"

    if action == "START":
        if cur_status == "COMPLETED":
            return "INVALID", f"Cannot start activity '{matched_activity.activity_code}': Activity is already COMPLETED."
        if actual_start is not None:
            return "INVALID", f"Activity '{matched_activity.activity_code}' has already been started on {actual_start}."

    elif action == "PROGRESS":
        if actual_start is None:
            return "INVALID", f"Activity '{matched_activity.activity_code}' must be started before progress can be reported."
        if cur_status == "ON_HOLD":
            return "INVALID", f"Activity '{matched_activity.activity_code}' is currently ON_HOLD. You must RESUME the activity first."
        if cur_status == "COMPLETED":
            return "INVALID", f"Activity '{matched_activity.activity_code}' is already COMPLETED. No further progress updates permitted."
        if progress_percentage is None:
            return "INVALID", "Progress percentage is required for PROGRESS updates."
        if progress_percentage <= 0 or progress_percentage >= 100:
            return "INVALID", "Progress percentage must be between 1% and 99% for incremental updates."
        if progress_percentage <= cur_prog:
            return "INVALID", f"Progress percentage cannot regress or stay same (Current: {cur_prog:.0f}%, Requested: {progress_percentage:.0f}%)."

    elif action == "COMPLETE":
        if actual_start is None:
            return "INVALID", f"Activity '{matched_activity.activity_code}' must be started before it can be completed."
        if cur_status == "COMPLETED":
            return "INVALID", f"Activity '{matched_activity.activity_code}' is already COMPLETED."

    elif action == "ON_HOLD":
        if actual_start is None or cur_status != "IN_PROGRESS":
            return "INVALID", f"Only IN_PROGRESS activities can be put ON_HOLD."

    elif action == "RESUME":
        if cur_status != "ON_HOLD":
            return "INVALID", f"Only ON_HOLD activities can be resumed."

    return "VALID", None


def build_report_item_response(
    db: Session,
    item: ProgressReportItem,
    user: User,
) -> ProgressReportItemResponse:
    """Builds ProgressReportItemResponse with full activity identity, proposed progress, and validation error status."""
    matched_act = item.matched_activity
    code = matched_act.activity_code if matched_act else None
    name = matched_act.activity_name if matched_act else None
    discipline = matched_act.discipline if matched_act else None

    current_status = None
    current_progress = None
    proposed_status = None
    proposed_progress = None

    if matched_act:
        exec_obj = db.query(ActivityExecution).filter(ActivityExecution.activity_id == matched_act.id).first()
        current_status = exec_obj.execution_status if exec_obj else "NOT_STARTED"
        current_progress = exec_obj.progress_percentage if exec_obj else 0.0

        if item.extracted_update_type == "START":
            proposed_status = "IN_PROGRESS"
            proposed_progress = item.extracted_progress_percentage if (item.extracted_progress_percentage is not None and item.extracted_progress_percentage > 0) else current_progress
        elif item.extracted_update_type == "PROGRESS":
            proposed_status = "IN_PROGRESS"
            proposed_progress = item.extracted_progress_percentage if item.extracted_progress_percentage is not None else current_progress
        elif item.extracted_update_type == "COMPLETE":
            proposed_status = "COMPLETED"
            proposed_progress = 100.0
        elif item.extracted_update_type in ["ON_HOLD"]:
            proposed_status = "ON_HOLD"
            proposed_progress = current_progress
        elif item.extracted_update_type in ["RESUME"]:
            proposed_status = "IN_PROGRESS"
            proposed_progress = current_progress

    val_status, err_msg = validate_item_execution_transition(
        db=db,
        project_id=item.project_id,
        user=user,
        matched_activity=matched_act,
        update_type=item.extracted_update_type,
        progress_percentage=item.extracted_progress_percentage,
        reported_date=item.reported_date,
    )

    alternatives = []
    if item.match_status in ["MATCHED_MEDIUM", "UNMATCHED"]:
        user_disc = get_user_assigned_discipline(user, item.project_id, db)
        _, _, _, alternatives = match_activity_for_report(
            db=db,
            project_id=item.project_id,
            user_role=user.role,
            user_discipline=user_disc,
            activity_description=item.raw_description,
            update_type=item.extracted_update_type or "PROGRESS",
        )

    # Parse page provenance from remarks if available (e.g. "[Page 3] ...")
    source_page = None
    if item.remarks:
        page_match = re.search(r"\[Page\s+(\d+)\]", item.remarks)
        if page_match:
            try:
                source_page = int(page_match.group(1))
            except ValueError:
                pass

    return ProgressReportItemResponse(
        id=item.id,
        report_id=item.report_id,
        project_id=item.project_id,
        raw_description=item.raw_description,
        reported_date=item.reported_date,
        extracted_update_type=item.extracted_update_type,
        extracted_progress_percentage=item.extracted_progress_percentage,
        remarks=item.remarks,
        source_page=source_page,
        raw_extracted_text=item.raw_description,
        matched_activity_id=item.matched_activity_id,
        matched_activity_code=code,
        matched_activity_name=name,
        matched_discipline=discipline,
        current_status=current_status,
        current_progress=current_progress,
        proposed_status=proposed_status,
        proposed_progress=proposed_progress,
        match_confidence=item.match_confidence,
        match_status=item.match_status,
        review_status=item.review_status,
        validation_status=val_status,
        error_message=err_msg if val_status == "INVALID" else item.error_message,
        alternatives=alternatives,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def build_report_import_response(
    db: Session,
    report: ProgressReportImport,
    user: User,
) -> ProgressReportImportResponse:
    """Builds detailed ProgressReportImportResponse with item list and item status breakdown counts."""
    items = db.query(ProgressReportItem).filter(ProgressReportItem.report_id == report.id).order_by(ProgressReportItem.id.asc()).all()

    item_responses = [build_report_item_response(db, it, user) for it in items]

    total_items = len(item_responses)
    pending_items = sum(1 for r in item_responses if r.review_status == "PENDING")
    approved_items = sum(1 for r in item_responses if r.review_status == "APPROVED")
    applied_items = sum(1 for r in item_responses if r.review_status == "APPLIED")
    rejected_items = sum(1 for r in item_responses if r.review_status == "REJECTED")
    invalid_items = sum(1 for r in item_responses if r.validation_status == "INVALID")

    uploaded_by_name = report.uploaded_by.full_name if report.uploaded_by else "Unknown"

    page_count = None
    extraction_method = None
    if report.raw_text and report.raw_text.strip().startswith("{"):
        try:
            meta = json.loads(report.raw_text)
            page_count = meta.get("page_count")
            extraction_method = meta.get("extraction_method")
        except Exception:
            pass

    return ProgressReportImportResponse(
        id=report.id,
        project_id=report.project_id,
        uploaded_by_id=report.uploaded_by_id,
        uploaded_by_name=uploaded_by_name,
        source_type=report.source_type,
        original_filename=report.original_filename,
        raw_text=report.raw_text,
        page_count=page_count,
        extraction_method=extraction_method,
        status=report.status,
        total_items=total_items,
        pending_items=pending_items,
        approved_items=approved_items,
        applied_items=applied_items,
        rejected_items=rejected_items,
        invalid_items=invalid_items,
        items=item_responses,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )

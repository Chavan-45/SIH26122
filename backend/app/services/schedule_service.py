import io
import json
import re
from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.activity import Activity
from app.models.schedule_import import ScheduleImport
from app.models.project import Project
from app.models.user import User

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ROW_LIMIT = 10000

CANONICAL_FIELDS = {
    "activity_code": {
        "required": True,
        "aliases": ["activity id", "activity code", "id", "task id", "activity_id", "activity_code", "task_id"],
    },
    "activity_name": {
        "required": True,
        "aliases": ["activity name", "task name", "name", "description", "activity_name", "task_name"],
    },
    "planned_start": {
        "required": True,
        "aliases": [
            "planned start", "start", "baseline start", "planned start date",
            "planned_start", "start date", "start_date"
        ],
    },
    "planned_finish": {
        "required": True,
        "aliases": [
            "planned finish", "finish", "baseline finish", "planned finish date",
            "planned_finish", "finish date", "finish_date",
            "planned end", "planned_end", "planned end date", "end date", "end_date", "end"
        ],
    },
    "wbs_code": {
        "required": False,
        "aliases": ["wbs", "wbs code", "wbs_code", "wbs element"],
    },
    "wbs_name": {
        "required": False,
        "aliases": ["wbs name", "wbs description", "wbs_name"],
    },
    "schedule_level": {
        "required": False,
        "aliases": ["level", "schedule level", "wbs level", "schedule_level"],
    },
    "discipline": {
        "required": False,
        "aliases": ["discipline", "department", "trade"],
    },
    "planned_duration": {
        "required": False,
        "aliases": ["duration", "original duration", "planned duration", "planned_duration"],
    },
    "predecessors": {
        "required": False,
        "aliases": ["predecessors", "predecessor", "logic predecessors"],
    },
}

VALID_DISCIPLINES = {
    "CIVIL": "CIVIL",
    "PIPING": "PIPING",
    "PIPE": "PIPING",
    "ELECTRICAL": "ELECTRICAL",
    "ELEC": "ELECTRICAL",
    "MECHANICAL": "MECHANICAL",
    "MECH": "MECHANICAL",
    "INSTRUMENTATION": "INSTRUMENTATION",
    "INST": "INSTRUMENTATION",
    "HSE": "HSE",
    "SAFETY": "HSE",
    "OTHER": "OTHER",
}


def normalize_header(header: str) -> str:
    """Normalize header text by stripping, lowercasing, and replacing punctuation."""
    return re.sub(r"[_\-\s]+", " ", str(header).strip().lower())


def auto_detect_mapping(df_columns: List[str]) -> Dict[str, Optional[str]]:
    """Attempt auto-mapping of schedule file columns to canonical field names."""
    detected_mapping: Dict[str, Optional[str]] = {field: None for field in CANONICAL_FIELDS}

    normalized_cols = {col: normalize_header(col) for col in df_columns}

    for field, config in CANONICAL_FIELDS.items():
        aliases = [normalize_header(a) for a in config["aliases"]]

        # Exact normalized match search
        for original_col, norm_col in normalized_cols.items():
            if norm_col in aliases:
                detected_mapping[field] = original_col
                break

        # Partial match search if not found
        if not detected_mapping[field]:
            for original_col, norm_col in normalized_cols.items():
                for alias in aliases:
                    if alias in norm_col or norm_col in alias:
                        detected_mapping[field] = original_col
                        break
                if detected_mapping[field]:
                    break

    return detected_mapping


def parse_date_value(val: Any, row_num: int, field_name: str) -> Tuple[Optional[date], Optional[str]]:
    """Parse raw cell value into date object or return error message."""
    if pd.isna(val) or val is None or str(val).strip() == "":
        return None, f"Row {row_num}: Missing required {field_name}"

    if isinstance(val, (datetime, date)):
        if isinstance(val, datetime):
            return val.date(), None
        return val, None

    val_str = str(val).strip()

    # Try common formats explicitly
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(val_str, fmt).date()
            return parsed, None
        except ValueError:
            pass

    # Try pandas to_datetime fallback
    try:
        dt = pd.to_datetime(val_str, dayfirst=True)
        if not pd.isna(dt):
            return dt.date(), None
    except Exception:
        pass

    return None, f"Row {row_num}: Invalid date format '{val_str}' for {field_name}"


def normalize_discipline(val: Any) -> str:
    """Normalize raw discipline string into standard DisciplineEnum value."""
    if pd.isna(val) or val is None or str(val).strip() == "":
        return "UNASSIGNED"

    clean_val = str(val).strip().upper()
    if clean_val in VALID_DISCIPLINES:
        return VALID_DISCIPLINES[clean_val]

    # Partial match check
    for key, mapped in VALID_DISCIPLINES.items():
        if key in clean_val:
            return mapped

    return "OTHER"


def normalize_duration(val: Any) -> Optional[float]:
    """Extract numeric duration value if supplied."""
    if pd.isna(val) or val is None or str(val).strip() == "":
        return None
    try:
        # Strip trailing units if any like "10 days" -> 10.0
        val_str = str(val).strip()
        match = re.search(r"[-+]?\d*\.\d+|\d+", val_str)
        if match:
            return float(match.group())
        return float(val)
    except (ValueError, TypeError):
        return None


async def read_uploaded_file(file: UploadFile) -> Tuple[pd.DataFrame, str]:
    """Read UploadFile into DataFrame after validating size and format."""
    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    if ext not in ["csv", "xlsx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '.{ext}'. Supported schedule formats are .csv and .xlsx.",
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
            detail=f"Failed to parse schedule file content: {str(e)}",
        )

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded schedule file contains no data rows.",
        )

    if len(df) > MAX_ROW_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Schedule exceeds maximum row limit of {MAX_ROW_LIMIT} activities ({len(df)} rows detected).",
        )

    return df, ext


def parse_and_validate_schedule_df(
    df: pd.DataFrame,
    mapping: Dict[str, Optional[str]],
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """
    Parse DataFrame using provided column mapping and run strict validations.
    Returns (normalized_activities, warnings, errors).
    """
    errors: List[str] = []
    warnings: List[str] = []
    normalized_activities: List[Dict[str, Any]] = []

    # Verify required canonical fields are mapped
    for field, config in CANONICAL_FIELDS.items():
        if config["required"] and not mapping.get(field):
            errors.append(f"Required canonical field '{field}' is not mapped to any column.")

    if errors:
        return [], warnings, errors

    seen_activity_codes = set()

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed including header

        # Activity Code
        code_col = mapping["activity_code"]
        raw_code = row.get(code_col) if code_col else None
        if pd.isna(raw_code) or str(raw_code).strip() == "":
            errors.append(f"Row {row_num}: Missing Activity ID")
            continue
        activity_code = str(raw_code).strip().upper()

        if activity_code in seen_activity_codes:
            errors.append(f"Row {row_num}: Duplicate Activity ID '{activity_code}' found within schedule file")
            continue
        seen_activity_codes.add(activity_code)

        # Activity Name
        name_col = mapping["activity_name"]
        raw_name = row.get(name_col) if name_col else None
        if pd.isna(raw_name) or str(raw_name).strip() == "":
            errors.append(f"Row {row_num}: Missing Activity Name")
            continue
        activity_name = str(raw_name).strip()

        # Dates
        start_col = mapping["planned_start"]
        raw_start = row.get(start_col) if start_col else None
        planned_start, start_err = parse_date_value(raw_start, row_num, "Planned Start")
        if start_err:
            errors.append(start_err)

        finish_col = mapping["planned_finish"]
        raw_finish = row.get(finish_col) if finish_col else None
        planned_finish, finish_err = parse_date_value(raw_finish, row_num, "Planned Finish")
        if finish_err:
            errors.append(finish_err)

        if planned_start and planned_finish:
            if planned_finish < planned_start:
                errors.append(f"Row {row_num}: Planned Finish ({planned_finish}) occurs before Planned Start ({planned_start})")

        # Optional fields
        wbs_code_col = mapping.get("wbs_code")
        wbs_code = str(row.get(wbs_code_col)).strip() if wbs_code_col and not pd.isna(row.get(wbs_code_col)) else None

        wbs_name_col = mapping.get("wbs_name")
        wbs_name = str(row.get(wbs_name_col)).strip() if wbs_name_col and not pd.isna(row.get(wbs_name_col)) else None

        level_col = mapping.get("schedule_level")
        schedule_level = str(row.get(level_col)).strip().upper() if level_col and not pd.isna(row.get(level_col)) else None

        discipline_col = mapping.get("discipline")
        raw_disc = row.get(discipline_col) if discipline_col else None
        discipline = normalize_discipline(raw_disc)

        duration_col = mapping.get("planned_duration")
        raw_dur = row.get(duration_col) if duration_col else None
        planned_duration = normalize_duration(raw_dur)

        predecessors_col = mapping.get("predecessors")
        raw_preds = row.get(predecessors_col) if predecessors_col else None
        predecessors = str(raw_preds).strip() if raw_preds and not pd.isna(raw_preds) else None

        normalized_activities.append({
            "activity_code": activity_code,
            "activity_name": activity_name,
            "wbs_code": wbs_code,
            "wbs_name": wbs_name,
            "schedule_level": schedule_level,
            "discipline": discipline,
            "planned_start": planned_start,
            "planned_finish": planned_finish,
            "planned_duration": planned_duration,
            "predecessors": predecessors,
        })

    return normalized_activities, warnings, errors


def process_schedule_preview(df: pd.DataFrame, filename: str) -> Dict[str, Any]:
    """Generate preview response data for schedule upload."""
    headers = [str(c) for c in df.columns]
    detected_mapping = auto_detect_mapping(headers)

    normalized_rows, warnings, errors = parse_and_validate_schedule_df(df, detected_mapping)

    # Format first 15 rows for visual UI preview
    preview_slice = df.head(15).fillna("").to_dict(orient="records")

    return {
        "filename": filename,
        "row_count": len(df),
        "headers": headers,
        "detected_mapping": detected_mapping,
        "preview_rows": preview_slice,
        "warnings": warnings,
        "errors": errors[:50],  # cap error list to 50 for readability
    }


def execute_schedule_import(
    db: Session,
    project_id: int,
    user: User,
    df: pd.DataFrame,
    filename: str,
    file_type: str,
    mapping: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    """
    Executes baseline schedule import in a single database transaction.
    If project already has activities, raises 409 Conflict.
    If any validation error occurs, raises 400 Bad Request and commits nothing.
    """
    # Check existing activities in project
    existing_count = db.query(func.count(Activity.id)).filter(Activity.project_id == project_id).scalar()
    if existing_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This project already has an imported baseline schedule. Multiple schedule imports are not permitted in this phase.",
        )

    normalized_activities, warnings, errors = parse_and_validate_schedule_df(df, mapping)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Schedule validation failed with {len(errors)} error(s). Import aborted.",
                "errors": errors,
            },
        )

    if not normalized_activities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid activity rows could be parsed from the uploaded schedule file.",
        )

    # All rows valid — execute atomic transaction
    try:
        activity_objects = []
        for act in normalized_activities:
            activity_objects.append(
                Activity(
                    project_id=project_id,
                    activity_code=act["activity_code"],
                    activity_name=act["activity_name"],
                    wbs_code=act["wbs_code"],
                    wbs_name=act["wbs_name"],
                    schedule_level=act["schedule_level"],
                    discipline=act["discipline"],
                    planned_start=act["planned_start"],
                    planned_finish=act["planned_finish"],
                    planned_duration=act["planned_duration"],
                    predecessors=act["predecessors"],
                )
            )

        db.bulk_save_objects(activity_objects)

        # Audit log entry
        import_record = ScheduleImport(
            project_id=project_id,
            original_filename=filename,
            file_type=file_type.upper(),
            imported_by_id=user.id,
            total_rows=len(df),
            imported_rows=len(activity_objects),
            status="COMPLETED",
        )
        db.add(import_record)

        db.commit()

        return {
            "status": "success",
            "project_id": project_id,
            "activities_imported": len(activity_objects),
            "filename": filename,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction error during schedule import: {str(e)}",
        )

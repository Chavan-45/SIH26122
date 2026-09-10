import io
import re
import csv
import json
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from fastapi import HTTPException, status

from app.models.project import Project
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.schedule_export import ScheduleExport, ScheduleExportItem
from app.models.user import User
from app.schemas.schedule_export import (
    ScheduleSyncSummaryResponse,
    ScheduleSyncPreviewItem,
    ScheduleSyncPreviewResponse,
    ScheduleExportListItemResponse,
    ScheduleExportDetailResponse,
)

CANONICAL_COLUMNS = [
    "project_code",
    "project_name",
    "activity_code",
    "activity_name",
    "wbs_code",
    "wbs_name",
    "schedule_level",
    "discipline",
    "planned_start",
    "planned_finish",
    "actual_start",
    "actual_finish",
    "progress_percentage",
    "execution_status",
    "start_variance_days",
    "finish_variance_days",
    "overdue_days",
    "last_updated_at",
    "last_updated_by",
    "last_update_source",
]


def sanitize_filename_part(text: str) -> str:
    """Sanitizes project code or text for safe cross-platform file names."""
    if not text:
        return "project"
    cleaned = re.sub(r'[^A-Za-z0-9_-]', '_', text.strip())
    return cleaned[:50]


def build_canonical_row(
    activity: Activity,
    execution: Optional[ActivityExecution],
    latest_update: Optional[ProgressUpdate],
    project: Project,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Builds the canonical 20-column actuals row dictionary for an activity.
    Handles missing execution state with fallback to 0% NOT_STARTED and empty actual dates.
    Calculates deterministic start, finish, and overdue variances without leaking database internal IDs.
    """
    if today is None:
        today = date.today()

    p_start_str = activity.planned_start.strftime("%Y-%m-%d") if activity.planned_start else ""
    p_finish_str = activity.planned_finish.strftime("%Y-%m-%d") if activity.planned_finish else ""

    act_start_str = ""
    act_finish_str = ""
    progress = 0.0
    status_val = "NOT_STARTED"
    last_up_at = ""
    last_up_by = ""
    start_var = None
    finish_var = None

    if execution:
        if execution.actual_start:
            act_start_str = execution.actual_start.strftime("%Y-%m-%d")
            if activity.planned_start:
                start_var = (execution.actual_start - activity.planned_start).days

        if execution.actual_finish:
            act_finish_str = execution.actual_finish.strftime("%Y-%m-%d")
            if activity.planned_finish:
                finish_var = (execution.actual_finish - activity.planned_finish).days

        progress = round(float(execution.progress_percentage or 0.0), 2)
        status_val = execution.execution_status or "NOT_STARTED"

        if execution.last_updated_at:
            last_up_at = execution.last_updated_at.isoformat()
        if execution.last_updated_by:
            last_up_by = execution.last_updated_by.full_name or execution.last_updated_by.email

    # Determine overdue days
    overdue_days = 0
    if status_val != "COMPLETED" and activity.planned_finish and activity.planned_finish < today:
        overdue_days = (today - activity.planned_finish).days

    last_src = latest_update.source_type if latest_update else ""

    return {
        "project_code": project.project_code,
        "project_name": project.name,
        "activity_code": activity.activity_code,
        "activity_name": activity.activity_name,
        "wbs_code": activity.wbs_code or "",
        "wbs_name": activity.wbs_name or "",
        "schedule_level": activity.schedule_level or "",
        "discipline": activity.discipline or "UNASSIGNED",
        "planned_start": p_start_str,
        "planned_finish": p_finish_str,
        "actual_start": act_start_str,
        "actual_finish": act_finish_str,
        "progress_percentage": progress,
        "execution_status": status_val,
        "start_variance_days": start_var,
        "finish_variance_days": finish_var,
        "overdue_days": overdue_days,
        "last_updated_at": last_up_at,
        "last_updated_by": last_up_by,
        "last_update_source": last_src,
    }


def detect_activity_changes(
    curr_row: Dict[str, Any],
    prev_snapshot: Optional[Dict[str, Any]],
    has_prev_export: bool,
) -> List[str]:
    """
    Compares current execution state against previous snapshot.
    Evaluates ONLY meaningful execution fields (actual_start, actual_finish, progress, execution_status).
    Calculated values like overdue_days do NOT trigger change flags.
    """
    if not has_prev_export:
        return []

    if prev_snapshot is None:
        return ["NEW_ACTIVITY_SNAPSHOT"]

    flags = []

    prev_start = prev_snapshot.get("actual_start") or ""
    curr_start = curr_row.get("actual_start") or ""
    if not prev_start and curr_start:
        flags.append("ACTUAL_START_SET")
    elif prev_start and curr_start and prev_start != curr_start:
        flags.append("ACTUAL_START_CHANGED")

    prev_prog = float(prev_snapshot.get("progress_percentage") or 0.0)
    curr_prog = float(curr_row.get("progress_percentage") or 0.0)
    if abs(prev_prog - curr_prog) > 0.001:
        flags.append("PROGRESS_CHANGED")

    prev_status = prev_snapshot.get("execution_status") or "NOT_STARTED"
    curr_status = curr_row.get("execution_status") or "NOT_STARTED"
    if prev_status != curr_status:
        flags.append("STATUS_CHANGED")

    prev_finish = prev_snapshot.get("actual_finish") or ""
    curr_finish = curr_row.get("actual_finish") or ""
    if not prev_finish and curr_finish:
        flags.append("ACTUAL_FINISH_SET")
    elif prev_finish and curr_finish and prev_finish != curr_finish:
        flags.append("ACTUAL_FINISH_CHANGED")

    return flags


def get_last_successful_export(db: Session, project_id: int) -> Optional[ScheduleExport]:
    """Retrieves the most recent successful schedule export for the project."""
    return (
        db.query(ScheduleExport)
        .filter(
            ScheduleExport.project_id == project_id,
            ScheduleExport.status == "GENERATED",
        )
        .order_by(ScheduleExport.generated_at.desc())
        .first()
    )


def load_previous_export_snapshots(db: Session, export_id: int) -> Dict[str, Dict[str, Any]]:
    """Loads a mapping of activity_code -> snapshot dictionary from a ScheduleExport."""
    items = db.query(ScheduleExportItem).filter(ScheduleExportItem.export_id == export_id).all()
    snapshots = {}
    for item in items:
        try:
            snapshots[item.activity_code] = json.loads(item.snapshot_json)
        except Exception:
            pass
    return snapshots


def get_project_activities_with_execution(
    db: Session, project_id: int
) -> Tuple[Project, List[Tuple[Activity, Optional[ActivityExecution], Optional[ProgressUpdate]]]]:
    """
    Fetches the project and all activities joined with execution and latest progress update.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )

    activities = (
        db.query(Activity)
        .filter(Activity.project_id == project_id)
        .order_by(Activity.activity_code.asc())
        .all()
    )

    # Fetch executions in map
    executions = (
        db.query(ActivityExecution)
        .options(joinedload(ActivityExecution.last_updated_by))
        .filter(ActivityExecution.project_id == project_id)
        .all()
    )
    exec_map = {e.activity_id: e for e in executions}

    # Fetch latest progress update per activity
    updates = (
        db.query(ProgressUpdate)
        .filter(ProgressUpdate.project_id == project_id)
        .order_by(ProgressUpdate.reported_date.desc(), ProgressUpdate.created_at.desc())
        .all()
    )
    latest_update_map: Dict[int, ProgressUpdate] = {}
    for up in updates:
        if up.activity_id not in latest_update_map:
            latest_update_map[up.activity_id] = up

    rows = []
    for act in activities:
        rows.append((act, exec_map.get(act.id), latest_update_map.get(act.id)))

    return project, rows


def get_schedule_sync_summary(db: Session, project_id: int) -> ScheduleSyncSummaryResponse:
    """Computes real 100% database-derived KPI metrics for Schedule Sync summary cards."""
    project, rows = get_project_activities_with_execution(db, project_id)
    total_activities = len(rows)

    with_actuals_count = 0
    for act, exc, _ in rows:
        if exc and (exc.actual_start or exc.progress_percentage > 0 or exc.execution_status != "NOT_STARTED"):
            with_actuals_count += 1

    last_export = get_last_successful_export(db, project_id)
    changed_count = 0
    has_prev = last_export is not None
    prev_snapshots: Dict[str, Dict[str, Any]] = {}
    if has_prev:
        prev_snapshots = load_previous_export_snapshots(db, last_export.id)
        today = date.today()
        for act, exc, lup in rows:
            curr_row = build_canonical_row(act, exc, lup, project, today)
            prev_snap = prev_snapshots.get(act.activity_code)
            flags = detect_activity_changes(curr_row, prev_snap, has_prev_export=True)
            if len(flags) > 0:
                changed_count += 1

    return ScheduleSyncSummaryResponse(
        total_activities=total_activities,
        activities_with_actuals=with_actuals_count,
        changed_since_last_export=changed_count,
        has_previous_export=has_prev,
        last_export_at=last_export.generated_at if last_export else None,
        last_export_format=last_export.file_format if last_export else None,
        last_export_mode=last_export.export_mode if last_export else None,
        last_export_id=last_export.id if last_export else None,
    )


def get_schedule_sync_preview(
    db: Session,
    project_id: int,
    mode: str = "FULL_SNAPSHOT",
) -> ScheduleSyncPreviewResponse:
    """Generates a read-only preview of the actuals export dataset."""
    mode_upper = mode.upper() if mode else "FULL_SNAPSHOT"
    if mode_upper not in ["FULL_SNAPSHOT", "CHANGES_ONLY"]:
        mode_upper = "FULL_SNAPSHOT"

    project, rows = get_project_activities_with_execution(db, project_id)
    total_activities = len(rows)
    today = date.today()

    last_export = get_last_successful_export(db, project_id)
    has_prev = last_export is not None
    prev_snapshots: Dict[str, Dict[str, Any]] = {}
    if has_prev:
        prev_snapshots = load_previous_export_snapshots(db, last_export.id)

    preview_items: List[ScheduleSyncPreviewItem] = []
    changed_count = 0

    for act, exc, lup in rows:
        canonical_dict = build_canonical_row(act, exc, lup, project, today)
        prev_snap = prev_snapshots.get(act.activity_code) if has_prev else None
        flags = detect_activity_changes(canonical_dict, prev_snap, has_prev)
        is_changed = len(flags) > 0
        if is_changed:
            changed_count += 1

        if mode_upper == "FULL_SNAPSHOT" or is_changed:
            preview_items.append(
                ScheduleSyncPreviewItem(
                    **canonical_dict,
                    change_flags=flags,
                    is_changed=is_changed,
                )
            )

    return ScheduleSyncPreviewResponse(
        export_mode=mode_upper,
        total_activities=total_activities,
        rows_to_export=len(preview_items),
        changed_activity_count=changed_count,
        has_previous_export=has_prev,
        previous_export_at=last_export.generated_at if last_export else None,
        items=preview_items,
    )


def create_schedule_export(
    db: Session,
    project_id: int,
    planner_user: User,
    export_mode: str,
    file_format: str,
) -> ScheduleExportDetailResponse:
    """
    Creates an immutable ScheduleExport and associated ScheduleExportItem records.
    Read-only with respect to Activity, ActivityExecution, and ProgressUpdate.
    """
    mode_upper = export_mode.upper() if export_mode else "FULL_SNAPSHOT"
    format_upper = file_format.upper() if file_format else "XLSX"

    if mode_upper not in ["FULL_SNAPSHOT", "CHANGES_ONLY"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid export_mode. Must be FULL_SNAPSHOT or CHANGES_ONLY.",
        )
    if format_upper not in ["CSV", "XLSX"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid file_format. Must be CSV or XLSX.",
        )

    project, rows = get_project_activities_with_execution(db, project_id)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot export empty schedule. Please import baseline activities first.",
        )

    last_export = get_last_successful_export(db, project_id)
    has_prev = last_export is not None
    if mode_upper == "CHANGES_ONLY" and not has_prev:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No previous export exists. Create a full snapshot first.",
        )

    prev_snapshots: Dict[str, Dict[str, Any]] = {}
    if has_prev:
        prev_snapshots = load_previous_export_snapshots(db, last_export.id)

    today = date.today()
    items_to_persist: List[Tuple[Activity, Dict[str, Any], List[str]]] = []
    total_changed = 0

    for act, exc, lup in rows:
        canonical_dict = build_canonical_row(act, exc, lup, project, today)
        prev_snap = prev_snapshots.get(act.activity_code) if has_prev else None
        flags = detect_activity_changes(canonical_dict, prev_snap, has_prev)
        is_changed = len(flags) > 0
        if is_changed:
            total_changed += 1

        if mode_upper == "FULL_SNAPSHOT" or is_changed:
            items_to_persist.append((act, canonical_dict, flags))

    if mode_upper == "CHANGES_ONLY" and len(items_to_persist) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No execution changes since last export. Nothing to export in Changes Only mode.",
        )

    now = datetime.now(timezone.utc)
    safe_code = sanitize_filename_part(project.project_code)
    mode_str = "full" if mode_upper == "FULL_SNAPSHOT" else "changes"
    date_str = now.strftime("%Y%m%d_%H%M")
    ext = format_upper.lower()
    file_name = f"{safe_code}_actuals_{mode_str}_{date_str}.{ext}"

    export_record = ScheduleExport(
        project_id=project_id,
        exported_by_id=planner_user.id,
        export_mode=mode_upper,
        file_format=format_upper,
        status="GENERATED",
        row_count=len(items_to_persist),
        changed_activity_count=total_changed,
        file_name=file_name,
        error_message=None,
        generated_at=now,
        created_at=now,
    )
    db.add(export_record)
    db.flush()

    export_items_response: List[ScheduleSyncPreviewItem] = []
    for act, canonical_dict, flags in items_to_persist:
        item = ScheduleExportItem(
            export_id=export_record.id,
            activity_id=act.id,
            activity_code=act.activity_code,
            snapshot_json=json.dumps(canonical_dict),
            change_flags_json=json.dumps(flags) if flags else None,
            created_at=now,
        )
        db.add(item)
        export_items_response.append(
            ScheduleSyncPreviewItem(
                **canonical_dict,
                change_flags=flags,
                is_changed=len(flags) > 0,
            )
        )

    db.commit()
    db.refresh(export_record)

    return ScheduleExportDetailResponse(
        id=export_record.id,
        project_id=project_id,
        project_code=project.project_code,
        project_name=project.name,
        export_mode=export_record.export_mode,
        file_format=export_record.file_format,
        status=export_record.status,
        row_count=export_record.row_count,
        changed_activity_count=export_record.changed_activity_count,
        file_name=export_record.file_name,
        exported_by_id=planner_user.id,
        exported_by_name=planner_user.full_name or planner_user.username,
        generated_at=export_record.generated_at,
        created_at=export_record.created_at,
        error_message=export_record.error_message,
        items=export_items_response,
    )


def get_export_history(db: Session, project_id: int) -> List[ScheduleExportListItemResponse]:
    """Retrieves all past schedule exports for a project, sorted by most recent first."""
    exports = (
        db.query(ScheduleExport)
        .options(joinedload(ScheduleExport.exported_by))
        .filter(ScheduleExport.project_id == project_id)
        .order_by(ScheduleExport.generated_at.desc())
        .all()
    )

    result = []
    for exp in exports:
        user_name = exp.exported_by.full_name or exp.exported_by.username if exp.exported_by else None
        result.append(
            ScheduleExportListItemResponse(
                id=exp.id,
                project_id=exp.project_id,
                export_mode=exp.export_mode,
                file_format=exp.file_format,
                status=exp.status,
                row_count=exp.row_count,
                changed_activity_count=exp.changed_activity_count,
                file_name=exp.file_name,
                exported_by_id=exp.exported_by_id,
                exported_by_name=user_name,
                generated_at=exp.generated_at,
                created_at=exp.created_at,
                error_message=exp.error_message,
            )
        )
    return result


def get_export_detail(db: Session, project_id: int, export_id: int) -> ScheduleExportDetailResponse:
    """Retrieves detailed export metadata and all snapshotted item rows."""
    export_record = (
        db.query(ScheduleExport)
        .options(joinedload(ScheduleExport.exported_by), joinedload(ScheduleExport.project))
        .filter(ScheduleExport.id == export_id, ScheduleExport.project_id == project_id)
        .first()
    )
    if not export_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ScheduleExport with ID {export_id} not found for this project.",
        )

    items = (
        db.query(ScheduleExportItem)
        .filter(ScheduleExportItem.export_id == export_id)
        .order_by(ScheduleExportItem.activity_code.asc())
        .all()
    )

    preview_items: List[ScheduleSyncPreviewItem] = []
    for it in items:
        try:
            s_dict = json.loads(it.snapshot_json)
            flags = json.loads(it.change_flags_json) if it.change_flags_json else []
            preview_items.append(
                ScheduleSyncPreviewItem(
                    **s_dict,
                    change_flags=flags,
                    is_changed=len(flags) > 0,
                )
            )
        except Exception:
            pass

    user_name = (
        export_record.exported_by.full_name or export_record.exported_by.username
        if export_record.exported_by
        else None
    )

    return ScheduleExportDetailResponse(
        id=export_record.id,
        project_id=project_id,
        project_code=export_record.project.project_code,
        project_name=export_record.project.name,
        export_mode=export_record.export_mode,
        file_format=export_record.file_format,
        status=export_record.status,
        row_count=export_record.row_count,
        changed_activity_count=export_record.changed_activity_count,
        file_name=export_record.file_name,
        exported_by_id=export_record.exported_by_id,
        exported_by_name=user_name,
        generated_at=export_record.generated_at,
        created_at=export_record.created_at,
        error_message=export_record.error_message,
        items=preview_items,
    )


def generate_csv_bytes(items: List[Dict[str, Any]]) -> io.BytesIO:
    """Generates standard UTF-8 CSV bytes from canonical snapshot item dictionaries."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CANONICAL_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    for item in items:
        # Normalize None values to empty string
        row = {k: ("" if item.get(k) is None else item.get(k)) for k in CANONICAL_COLUMNS}
        writer.writerow(row)

    csv_bytes = output.getvalue().encode("utf-8")
    return io.BytesIO(csv_bytes)


def generate_xlsx_bytes(
    export_record: ScheduleExport,
    items: List[Dict[str, Any]],
    project: Project,
    planner_user: Optional[User],
) -> io.BytesIO:
    """
    Generates structured multi-sheet XLSX bytes:
    Sheet 1: Activity Actuals (formatted canonical columns, bold header, frozen panes, autofilter)
    Sheet 2: Export Summary (metadata, timestamps, and Primavera/MS Project integration notice)
    """
    wb = openpyxl.Workbook()

    # --- Sheet 1: Activity Actuals ---
    ws_actuals = wb.active
    ws_actuals.title = "Activity Actuals"
    ws_actuals.views.sheetView[0].showGridLines = True

    # Styling constants
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")  # Deep Navy Slate
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    data_font = Font(name="Segoe UI", size=9)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    # Write Header Row
    ws_actuals.append(CANONICAL_COLUMNS)
    for col_idx in range(1, len(CANONICAL_COLUMNS) + 1):
        cell = ws_actuals.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border
    ws_actuals.row_dimensions[1].height = 24

    # Write Data Rows
    for row_idx, item in enumerate(items, start=2):
        row_values = []
        for col_name in CANONICAL_COLUMNS:
            val = item.get(col_name)
            if val is None:
                val = ""
            row_values.append(val)
        ws_actuals.append(row_values)

        for col_idx in range(1, len(CANONICAL_COLUMNS) + 1):
            c = ws_actuals.cell(row=row_idx, column=col_idx)
            c.font = data_font
            c.border = thin_border
            col_name = CANONICAL_COLUMNS[col_idx - 1]
            if col_name in ["progress_percentage", "start_variance_days", "finish_variance_days", "overdue_days"]:
                c.alignment = right_align
            elif col_name in ["planned_start", "planned_finish", "actual_start", "actual_finish", "execution_status", "discipline", "schedule_level"]:
                c.alignment = center_align
            else:
                c.alignment = left_align
        ws_actuals.row_dimensions[row_idx].height = 18

    # Freeze Header Row and Enable AutoFilter
    ws_actuals.freeze_panes = "A2"
    if items:
        max_col_letter = get_column_letter(len(CANONICAL_COLUMNS))
        ws_actuals.auto_filter.ref = f"A1:{max_col_letter}{len(items) + 1}"

    # Auto-adjust column widths
    for col in ws_actuals.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val_str = str(cell.value or '')
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws_actuals.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # --- Sheet 2: Export Summary ---
    ws_summary = wb.create_sheet(title="Export Summary")
    ws_summary.views.sheetView[0].showGridLines = True

    summary_title_font = Font(name="Segoe UI", size=14, bold=True, color="0F172A")
    summary_label_font = Font(name="Segoe UI", size=10, bold=True, color="334155")
    summary_val_font = Font(name="Segoe UI", size=10, color="0F172A")
    summary_note_font = Font(name="Segoe UI", size=9, italic=True, color="64748B")

    ws_summary.cell(row=1, column=1, value="Project Schedule Actuals Export Summary").font = summary_title_font
    ws_summary.row_dimensions[1].height = 28

    user_str = (
        planner_user.full_name or planner_user.username
        if planner_user
        else (export_record.exported_by.full_name or export_record.exported_by.username if export_record.exported_by else "Lead Planner")
    )
    gen_at_str = export_record.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")

    meta_rows = [
        ("Project Name", project.name),
        ("Project Code", project.project_code),
        ("Export Mode", export_record.export_mode),
        ("File Format", export_record.file_format),
        ("Generated At", gen_at_str),
        ("Generated By", user_str),
        ("Total Baseline Activities", len(project.activities) if project.activities else export_record.row_count),
        ("Rows Exported", export_record.row_count),
        ("Changed Activities Count", export_record.changed_activity_count),
        ("Integration Key", "activity_code"),
        ("Notice", "This export contains schedule-linked actual execution data and does not directly modify Primavera P6 or Microsoft Project."),
    ]

    for idx, (label, val) in enumerate(meta_rows, start=3):
        c_lbl = ws_summary.cell(row=idx, column=1, value=label)
        c_lbl.font = summary_label_font
        c_lbl.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        c_lbl.border = thin_border
        c_lbl.alignment = left_align

        c_val = ws_summary.cell(row=idx, column=2, value=str(val))
        c_val.font = summary_val_font if label != "Notice" else summary_note_font
        c_val.border = thin_border
        c_val.alignment = left_align
        ws_summary.row_dimensions[idx].height = 22

    ws_summary.column_dimensions["A"].width = 28
    ws_summary.column_dimensions["B"].width = 75

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def download_export_snapshot(db: Session, project_id: int, export_id: int) -> Tuple[io.BytesIO, str, str]:
    """
    Downloads historical export by reconstructing CSV or XLSX directly from persisted ScheduleExportItems.
    Does NOT query live state, ensuring historical immutability.
    Returns: (file_bytes_io, media_type, filename)
    """
    export_record = (
        db.query(ScheduleExport)
        .options(joinedload(ScheduleExport.project), joinedload(ScheduleExport.exported_by))
        .filter(ScheduleExport.id == export_id, ScheduleExport.project_id == project_id)
        .first()
    )
    if not export_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule export {export_id} not found.",
        )
    if export_record.status != "GENERATED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot download an export that failed or is not in GENERATED state.",
        )

    items = (
        db.query(ScheduleExportItem)
        .filter(ScheduleExportItem.export_id == export_id)
        .order_by(ScheduleExportItem.activity_code.asc())
        .all()
    )

    item_dicts = []
    for it in items:
        try:
            item_dicts.append(json.loads(it.snapshot_json))
        except Exception:
            pass

    file_name = export_record.file_name or f"export_{export_id}.{export_record.file_format.lower()}"

    if export_record.file_format == "CSV":
        bio = generate_csv_bytes(item_dicts)
        media_type = "text/csv; charset=utf-8"
        return bio, media_type, file_name
    else:
        bio = generate_xlsx_bytes(export_record, item_dicts, export_record.project, export_record.exported_by)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return bio, media_type, file_name

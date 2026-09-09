from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.project import Project
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.project_member import ProjectMember
from app.models.user import User
from app.core.datetime_utils import get_today_date


# ============================================================================
# 10 Safe Server-Bound Read-Only Tools for Project Context Data
# ============================================================================

def get_project_overview(db: Session, project_id: int) -> Dict[str, Any]:
    """Retrieves high-level baseline information and progress summary for the current project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"error": f"Project with ID {project_id} not found."}

    activities_with_exec = (
        db.query(Activity, ActivityExecution)
        .outerjoin(ActivityExecution, Activity.id == ActivityExecution.activity_id)
        .filter(Activity.project_id == project_id)
        .all()
    )

    total_activities = len(activities_with_exec)
    completed_count = 0
    progress_sum = 0.0

    for act, exec_obj in activities_with_exec:
        prog = float(exec_obj.progress_percentage or 0.0) if exec_obj else 0.0
        status_val = exec_obj.execution_status.value if exec_obj and hasattr(exec_obj.execution_status, "value") else (str(exec_obj.execution_status) if exec_obj else "NOT_STARTED")
        progress_sum += prog
        if status_val == "COMPLETED" or prog >= 100.0:
            completed_count += 1

    overall_progress = round(progress_sum / total_activities, 1) if total_activities > 0 else 0.0

    memberships = (
        db.query(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project_id)
        .all()
    )

    members = [
        {
            "user_id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
            "assigned_discipline": pm.discipline,
        }
        for pm, u in memberships
    ]

    today = get_today_date()
    days_until_finish = (project.planned_end_date - today).days if project.planned_end_date else None

    return {
        "project_id": project.id,
        "project_code": project.project_code,
        "name": project.name,
        "description": project.description,
        "location": project.location,
        "status": project.status.value if hasattr(project.status, "value") else str(project.status),
        "planned_start_date": str(project.planned_start_date) if project.planned_start_date else None,
        "planned_end_date": str(project.planned_end_date) if project.planned_end_date else None,
        "days_until_planned_finish": days_until_finish,
        "total_activities": total_activities,
        "completed_activities": completed_count,
        "overall_progress": overall_progress,
        "team_members": members,
    }


def get_execution_summary(
    db: Session, project_id: int, user_role: str = "PLANNER", user_discipline: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves overall execution status breakdown and progress summary."""
    query = (
        db.query(Activity, ActivityExecution)
        .outerjoin(ActivityExecution, Activity.id == ActivityExecution.activity_id)
        .filter(Activity.project_id == project_id)
    )

    # Discipline scoping for Supervisors
    effective_discipline = None
    if user_role == "SUPERVISOR" and user_discipline:
        effective_discipline = user_discipline.strip().upper()
        query = query.filter(func.upper(Activity.discipline) == effective_discipline)

    activities_with_exec = query.all()
    total_activities = len(activities_with_exec)
    today = get_today_date()

    status_counts = {"NOT_STARTED": 0, "IN_PROGRESS": 0, "ON_HOLD": 0, "COMPLETED": 0}
    progress_sum = 0.0
    overdue_count = 0
    today_work_count = 0

    for act, exec_obj in activities_with_exec:
        exec_status = "NOT_STARTED"
        prog = 0.0
        if exec_obj:
            raw_stat = exec_obj.execution_status
            exec_status = raw_stat.value if hasattr(raw_stat, "value") else str(raw_stat)
            prog = float(exec_obj.progress_percentage or 0.0)

        progress_sum += prog

        if exec_status in status_counts:
            status_counts[exec_status] += 1
        else:
            status_counts["NOT_STARTED"] += 1

        if act.planned_finish and act.planned_finish < today and exec_status != "COMPLETED":
            overdue_count += 1

        if act.planned_start and act.planned_finish and act.planned_start <= today <= act.planned_finish and exec_status != "COMPLETED":
            today_work_count += 1

    overall_progress = round(progress_sum / total_activities, 1) if total_activities > 0 else 0.0

    return {
        "scope": f"Discipline: {effective_discipline}" if effective_discipline else "Project-wide",
        "total_activities": total_activities,
        "overall_progress_percentage": overall_progress,
        "status_counts": status_counts,
        "overdue_activities_count": overdue_count,
        "today_work_activities_count": today_work_count,
    }


def get_today_work(
    db: Session, project_id: int, user_role: str = "PLANNER", user_discipline: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves activities scheduled to be in progress today."""
    today = get_today_date()
    query = (
        db.query(Activity, ActivityExecution)
        .outerjoin(ActivityExecution, Activity.id == ActivityExecution.activity_id)
        .filter(
            Activity.project_id == project_id,
            Activity.planned_start <= today,
            Activity.planned_finish >= today,
        )
    )

    effective_discipline = None
    if user_role == "SUPERVISOR" and user_discipline:
        effective_discipline = user_discipline.strip().upper()
        query = query.filter(func.upper(Activity.discipline) == effective_discipline)

    items = query.all()
    results = []
    for act, exec_obj in items:
        status_val = exec_obj.execution_status.value if exec_obj and hasattr(exec_obj.execution_status, "value") else (str(exec_obj.execution_status) if exec_obj else "NOT_STARTED")
        if status_val == "COMPLETED":
            continue

        prog = float(exec_obj.progress_percentage or 0.0) if exec_obj else 0.0
        results.append({
            "activity_id": act.id,
            "activity_code": act.activity_code,
            "activity_name": act.activity_name,
            "discipline": act.discipline or "UNASSIGNED",
            "planned_start": str(act.planned_start) if act.planned_start else None,
            "planned_finish": str(act.planned_finish) if act.planned_finish else None,
            "status": status_val,
            "progress_percentage": prog,
            "days_remaining": (act.planned_finish - today).days if act.planned_finish else None,
        })

    results.sort(key=lambda x: (x["discipline"], x["activity_code"]))

    return {
        "today_date": str(today),
        "scope": f"Discipline: {effective_discipline}" if effective_discipline else "Project-wide",
        "count": len(results),
        "activities": results,
    }


def get_overdue_activities(
    db: Session, project_id: int, user_role: str = "PLANNER", user_discipline: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves activities whose planned finish date has passed and are not yet completed."""
    today = get_today_date()
    query = (
        db.query(Activity, ActivityExecution)
        .outerjoin(ActivityExecution, Activity.id == ActivityExecution.activity_id)
        .filter(
            Activity.project_id == project_id,
            Activity.planned_finish < today,
        )
    )

    effective_discipline = None
    if user_role == "SUPERVISOR" and user_discipline:
        effective_discipline = user_discipline.strip().upper()
        query = query.filter(func.upper(Activity.discipline) == effective_discipline)

    items = query.all()
    results = []
    for act, exec_obj in items:
        status_val = exec_obj.execution_status.value if exec_obj and hasattr(exec_obj.execution_status, "value") else (str(exec_obj.execution_status) if exec_obj else "NOT_STARTED")
        prog = float(exec_obj.progress_percentage or 0.0) if exec_obj else 0.0
        if status_val == "COMPLETED" or prog >= 100.0:
            continue

        overdue_days = (today - act.planned_finish).days if act.planned_finish else 0
        results.append({
            "activity_id": act.id,
            "activity_code": act.activity_code,
            "activity_name": act.activity_name,
            "discipline": act.discipline or "UNASSIGNED",
            "planned_start": str(act.planned_start) if act.planned_start else None,
            "planned_finish": str(act.planned_finish) if act.planned_finish else None,
            "status": status_val,
            "progress_percentage": prog,
            "overdue_days": overdue_days,
        })

    results.sort(key=lambda x: x["overdue_days"], reverse=True)

    return {
        "today_date": str(today),
        "scope": f"Discipline: {effective_discipline}" if effective_discipline else "Project-wide",
        "count": len(results),
        "activities": results,
    }


def get_upcoming_deadlines(
    db: Session,
    project_id: int,
    days: int = 7,
    user_role: str = "PLANNER",
    user_discipline: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieves activities due within specified days (default 7 days)."""
    today = get_today_date()
    cutoff_date = today + timedelta(days=days)

    query = (
        db.query(Activity, ActivityExecution)
        .outerjoin(ActivityExecution, Activity.id == ActivityExecution.activity_id)
        .filter(
            Activity.project_id == project_id,
            Activity.planned_finish >= today,
            Activity.planned_finish <= cutoff_date,
        )
    )

    effective_discipline = None
    if user_role == "SUPERVISOR" and user_discipline:
        effective_discipline = user_discipline.strip().upper()
        query = query.filter(func.upper(Activity.discipline) == effective_discipline)

    items = query.all()
    results = []
    for act, exec_obj in items:
        status_val = exec_obj.execution_status.value if exec_obj and hasattr(exec_obj.execution_status, "value") else (str(exec_obj.execution_status) if exec_obj else "NOT_STARTED")
        if status_val == "COMPLETED":
            continue

        prog = float(exec_obj.progress_percentage or 0.0) if exec_obj else 0.0
        results.append({
            "activity_id": act.id,
            "activity_code": act.activity_code,
            "activity_name": act.activity_name,
            "discipline": act.discipline or "UNASSIGNED",
            "planned_start": str(act.planned_start) if act.planned_start else None,
            "planned_finish": str(act.planned_finish) if act.planned_finish else None,
            "status": status_val,
            "progress_percentage": prog,
            "days_until_due": (act.planned_finish - today).days if act.planned_finish else 0,
        })

    results.sort(key=lambda x: x["planned_finish"] or "")

    return {
        "today_date": str(today),
        "lookahead_days": days,
        "scope": f"Discipline: {effective_discipline}" if effective_discipline else "Project-wide",
        "count": len(results),
        "activities": results,
    }


def get_activity_details(db: Session, project_id: int, activity_code: str) -> Dict[str, Any]:
    """Retrieves full baseline and execution details for a specific activity code."""
    activity = (
        db.query(Activity)
        .filter(
            Activity.project_id == project_id,
            func.upper(Activity.activity_code) == activity_code.strip().upper(),
        )
        .first()
    )

    if not activity:
        # Substring match fallback
        activity = (
            db.query(Activity)
            .filter(
                Activity.project_id == project_id,
                Activity.activity_code.ilike(f"%{activity_code.strip()}%"),
            )
            .first()
        )

    if not activity:
        return {"error": f"Activity code '{activity_code}' not found in project ID {project_id}."}

    execution = (
        db.query(ActivityExecution)
        .filter(ActivityExecution.activity_id == activity.id)
        .first()
    )

    updates = (
        db.query(ProgressUpdate, User)
        .outerjoin(User, ProgressUpdate.reported_by_id == User.id)
        .filter(ProgressUpdate.activity_id == activity.id)
        .order_by(ProgressUpdate.created_at.desc())
        .limit(5)
        .all()
    )

    history = [
        {
            "id": u.id,
            "reported_by": user.full_name if user else "Unknown",
            "update_type": u.update_type.value if hasattr(u.update_type, "value") else str(u.update_type),
            "reported_date": str(u.reported_date),
            "progress_percentage": float(u.progress_percentage),
            "remarks": u.remarks,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u, user in updates
    ]

    status_val = execution.execution_status.value if execution and hasattr(execution.execution_status, "value") else (str(execution.execution_status) if execution else "NOT_STARTED")

    return {
        "activity_id": activity.id,
        "activity_code": activity.activity_code,
        "activity_name": activity.activity_name,
        "wbs_code": activity.wbs_code,
        "discipline": activity.discipline,
        "location": activity.wbs_name or activity.wbs_code or "N/A",
        "planned_start": str(activity.planned_start) if activity.planned_start else None,
        "planned_finish": str(activity.planned_finish) if activity.planned_finish else None,
        "planned_duration": activity.planned_duration,
        "actual_start": str(execution.actual_start) if execution and execution.actual_start else None,
        "actual_finish": str(execution.actual_finish) if execution and execution.actual_finish else None,
        "status": status_val,
        "progress_percentage": float(execution.progress_percentage or 0.0) if execution else 0.0,
        "last_updated_at": execution.last_updated_at.isoformat() if execution and hasattr(execution, "last_updated_at") and execution.last_updated_at else None,
        "recent_updates_count": len(history),
        "recent_updates": history,
    }


def search_activities(
    db: Session,
    project_id: int,
    query: Optional[str] = None,
    discipline: Optional[str] = None,
    status: Optional[str] = None,
    user_role: str = "PLANNER",
    user_discipline: Optional[str] = None,
) -> Dict[str, Any]:
    """Searches activities by text query (code or name), discipline, or execution status."""
    q = (
        db.query(Activity, ActivityExecution)
        .outerjoin(ActivityExecution, Activity.id == ActivityExecution.activity_id)
        .filter(Activity.project_id == project_id)
    )

    if query and query.strip():
        search_term = f"%{query.strip()}%"
        q = q.filter(
            (Activity.activity_code.ilike(search_term))
            | (Activity.activity_name.ilike(search_term))
            | (Activity.wbs_code.ilike(search_term))
            | (Activity.wbs_name.ilike(search_term))
        )

    # Supervisor restriction
    if user_role == "SUPERVISOR" and user_discipline:
        q = q.filter(func.upper(Activity.discipline) == user_discipline.strip().upper())
    elif discipline and discipline.strip():
        q = q.filter(func.upper(Activity.discipline) == discipline.strip().upper())

    items = q.all()
    results = []

    for act, exec_obj in items:
        status_val = exec_obj.execution_status.value if exec_obj and hasattr(exec_obj.execution_status, "value") else (str(exec_obj.execution_status) if exec_obj else "NOT_STARTED")

        if status and status.strip():
            if status_val.upper() != status.strip().upper():
                continue

        prog = float(exec_obj.progress_percentage or 0.0) if exec_obj else 0.0

        results.append({
            "activity_id": act.id,
            "activity_code": act.activity_code,
            "activity_name": act.activity_name,
            "discipline": act.discipline or "UNASSIGNED",
            "location": act.wbs_name or act.wbs_code or "N/A",
            "planned_start": str(act.planned_start) if act.planned_start else None,
            "planned_finish": str(act.planned_finish) if act.planned_finish else None,
            "status": status_val,
            "progress_percentage": prog,
        })

    return {
        "search_query": query,
        "discipline_filter": discipline,
        "status_filter": status,
        "count": len(results),
        "activities": results[:30],  # Cap output to top 30 for prompt efficiency
    }


def get_discipline_progress(
    db: Session, project_id: int, discipline: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves progress and status breakdown grouped by engineering discipline."""
    q = (
        db.query(Activity, ActivityExecution)
        .outerjoin(ActivityExecution, Activity.id == ActivityExecution.activity_id)
        .filter(Activity.project_id == project_id)
    )

    if discipline and discipline.strip():
        q = q.filter(func.upper(Activity.discipline) == discipline.strip().upper())

    items = q.all()
    today = get_today_date()

    discipline_map: Dict[str, Dict[str, Any]] = {}

    for act, exec_obj in items:
        disc = act.discipline.strip() if act.discipline and act.discipline.strip() else "UNASSIGNED"
        if disc not in discipline_map:
            discipline_map[disc] = {
                "discipline": disc,
                "total_activities": 0,
                "progress_sum": 0.0,
                "not_started": 0,
                "in_progress": 0,
                "on_hold": 0,
                "completed": 0,
                "overdue": 0,
            }
        d = discipline_map[disc]
        d["total_activities"] += 1

        status_val = exec_obj.execution_status.value if exec_obj and hasattr(exec_obj.execution_status, "value") else (str(exec_obj.execution_status) if exec_obj else "NOT_STARTED")
        prog = float(exec_obj.progress_percentage or 0.0) if exec_obj else 0.0

        d["progress_sum"] += prog

        if status_val == "NOT_STARTED":
            d["not_started"] += 1
        elif status_val == "IN_PROGRESS":
            d["in_progress"] += 1
        elif status_val == "ON_HOLD":
            d["on_hold"] += 1
        elif status_val == "COMPLETED":
            d["completed"] += 1

        if act.planned_finish and act.planned_finish < today and status_val != "COMPLETED":
            d["overdue"] += 1

    summary_list = []
    for dname, ddata in discipline_map.items():
        tot = ddata["total_activities"]
        avg_prog = round(ddata["progress_sum"] / tot, 1) if tot > 0 else 0.0
        summary_list.append({
            "discipline": dname,
            "total_activities": tot,
            "overall_progress_percentage": avg_prog,
            "not_started": ddata["not_started"],
            "in_progress": ddata["in_progress"],
            "on_hold": ddata["on_hold"],
            "completed": ddata["completed"],
            "overdue": ddata["overdue"],
        })

    summary_list.sort(key=lambda x: x["discipline"])

    return {
        "discipline_count": len(summary_list),
        "disciplines": summary_list,
    }


def get_recent_progress_updates(
    db: Session,
    project_id: int,
    limit: int = 10,
    user_role: str = "PLANNER",
    user_discipline: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieves recent site progress update audit logs."""
    q = (
        db.query(ProgressUpdate, Activity, User)
        .join(Activity, ProgressUpdate.activity_id == Activity.id)
        .outerjoin(User, ProgressUpdate.reported_by_id == User.id)
        .filter(ProgressUpdate.project_id == project_id)
    )

    effective_discipline = None
    if user_role == "SUPERVISOR" and user_discipline:
        effective_discipline = user_discipline.strip().upper()
        q = q.filter(func.upper(Activity.discipline) == effective_discipline)

    logs = q.order_by(ProgressUpdate.created_at.desc()).limit(limit).all()

    results = []
    for u_obj, act_obj, user_obj in logs:
        results.append({
            "update_id": u_obj.id,
            "activity_code": act_obj.activity_code,
            "activity_name": act_obj.activity_name,
            "discipline": act_obj.discipline or "UNASSIGNED",
            "reporter_name": user_obj.full_name if user_obj else "System/Unknown",
            "update_type": u_obj.update_type.value if hasattr(u_obj.update_type, "value") else str(u_obj.update_type),
            "reported_date": str(u_obj.reported_date),
            "progress_percentage": float(u_obj.progress_percentage),
            "remarks": u_obj.remarks,
            "created_at": u_obj.created_at.isoformat() if u_obj.created_at else None,
        })

    return {
        "limit": limit,
        "scope": f"Discipline: {effective_discipline}" if effective_discipline else "Project-wide",
        "count": len(results),
        "updates": results,
    }


def get_activity_progress_history(
    db: Session, project_id: int, activity_code: str
) -> Dict[str, Any]:
    """Retrieves complete progress update audit history for a specific activity code."""
    activity = (
        db.query(Activity)
        .filter(
            Activity.project_id == project_id,
            func.upper(Activity.activity_code) == activity_code.strip().upper(),
        )
        .first()
    )

    if not activity:
        activity = (
            db.query(Activity)
            .filter(
                Activity.project_id == project_id,
                Activity.activity_code.ilike(f"%{activity_code.strip()}%"),
            )
            .first()
        )

    if not activity:
        return {"error": f"Activity code '{activity_code}' not found in project ID {project_id}."}

    logs = (
        db.query(ProgressUpdate, User)
        .outerjoin(User, ProgressUpdate.reported_by_id == User.id)
        .filter(ProgressUpdate.activity_id == activity.id)
        .order_by(ProgressUpdate.created_at.asc())
        .all()
    )

    history = []
    for u_obj, user_obj in logs:
        history.append({
            "update_id": u_obj.id,
            "reporter_name": user_obj.full_name if user_obj else "System/Unknown",
            "update_type": u_obj.update_type.value if hasattr(u_obj.update_type, "value") else str(u_obj.update_type),
            "reported_date": str(u_obj.reported_date),
            "progress_percentage": float(u_obj.progress_percentage),
            "remarks": u_obj.remarks,
            "created_at": u_obj.created_at.isoformat() if u_obj.created_at else None,
        })

    return {
        "activity_code": activity.activity_code,
        "activity_name": activity.activity_name,
        "total_updates": len(history),
        "history": history,
    }


def get_project_team(db: Session, project_id: int) -> Dict[str, Any]:
    """Retrieves structured information about assigned project team members, roles, and disciplines."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"error": f"Project with ID {project_id} not found."}

    memberships = (
        db.query(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project_id)
        .all()
    )

    supervisor_count = 0
    members_list = []

    for pm, u in memberships:
        role_str = u.role.value if hasattr(u.role, "value") else str(u.role)
        if role_str == "SUPERVISOR":
            supervisor_count += 1
        members_list.append({
            "full_name": u.full_name,
            "role": role_str,
            "discipline": pm.discipline or "ALL",
        })

    planner_user = db.query(User).filter(User.id == project.created_by_id).first()
    if planner_user:
        planner_role = planner_user.role.value if hasattr(planner_user.role, "value") else str(planner_user.role)
        if not any(m["full_name"] == planner_user.full_name for m in members_list):
            members_list.insert(0, {
                "full_name": planner_user.full_name,
                "role": planner_role,
                "discipline": "PROJECT_WIDE",
            })

    return {
        "project_id": project.id,
        "project_code": project.project_code,
        "total_members": len(members_list),
        "supervisor_count": supervisor_count,
        "members": members_list,
    }


# Dispatcher mapping
TOOL_DISPATCHER = {
    "get_project_overview": get_project_overview,
    "get_execution_summary": get_execution_summary,
    "get_today_work": get_today_work,
    "get_overdue_activities": get_overdue_activities,
    "get_upcoming_deadlines": get_upcoming_deadlines,
    "get_activity_details": get_activity_details,
    "search_activities": search_activities,
    "get_discipline_progress": get_discipline_progress,
    "get_recent_progress_updates": get_recent_progress_updates,
    "get_activity_progress_history": get_activity_progress_history,
    "get_project_team": get_project_team,
}



def execute_tool(
    db: Session,
    project_id: int,
    user_role: str,
    user_discipline: Optional[str],
    tool_name: str,
    tool_args: Dict[str, Any],
) -> Dict[str, Any]:
    """Executes a named AI tool safely with project and user context binding."""
    fn = TOOL_DISPATCHER.get(tool_name)
    if not fn:
        return {"error": f"Unknown tool name '{tool_name}'."}

    kwargs = dict(tool_args or {})
    kwargs["db"] = db
    kwargs["project_id"] = project_id

    import inspect
    sig = inspect.signature(fn)
    if "user_role" in sig.parameters:
        kwargs["user_role"] = user_role
    if "user_discipline" in sig.parameters:
        kwargs["user_discipline"] = user_discipline

    try:
        return fn(**kwargs)
    except Exception as e:
        return {"error": f"Tool execution error: {str(e)}"}

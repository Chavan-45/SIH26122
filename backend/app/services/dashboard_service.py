from datetime import timedelta, date
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.project import Project
from app.models.user import User
from app.models.project_member import ProjectMember
from app.core.datetime_utils import get_today_date
from app.schemas.dashboard import (
    ProjectDashboardResponse,
    DashboardProjectInfo,
    DashboardSummary,
    ScheduleHealthMetrics,
    DisciplineProgressItem,
    ActivityDashboardSummary,
    RecentUpdateItem,
    BaselineVsActualMetrics,
    SupervisorDisciplineSummary,
)


def get_project_dashboard_data(
    db: Session, project: Project, user: User, assigned_discipline: Optional[str] = None
) -> ProjectDashboardResponse:
    today = get_today_date()

    # 1. Project Info Header
    days_until_finish = None
    deadline_label = "No planned end date"
    if project.planned_end_date:
        days_until_finish = (project.planned_end_date - today).days
        if days_until_finish > 0:
            deadline_label = f"{days_until_finish} days remaining"
        elif days_until_finish == 0:
            deadline_label = "Planned finish is today"
        else:
            deadline_label = f"Planned finish passed {abs(days_until_finish)} days ago"

    project_info = DashboardProjectInfo(
        id=project.id,
        name=project.name,
        project_code=project.project_code,
        location=project.location,
        status=project.status.value if hasattr(project.status, "value") else str(project.status),
        planned_start_date=project.planned_start_date,
        planned_end_date=project.planned_end_date,
        days_until_planned_finish=days_until_finish,
        deadline_label=deadline_label,
    )

    # 2. Bulk query activities and left join activity executions
    activities_with_exec = (
        db.query(Activity, ActivityExecution)
        .outerjoin(ActivityExecution, Activity.id == ActivityExecution.activity_id)
        .filter(Activity.project_id == project.id)
        .all()
    )

    total_activities = len(activities_with_exec)

    if total_activities == 0:
        # Handle empty project schedule state cleanly
        summary = DashboardSummary(
            total_activities=0,
            overall_progress=0.0,
            not_started=0,
            in_progress=0,
            on_hold=0,
            completed=0,
            overdue=0,
        )
        health = ScheduleHealthMetrics(
            overdue_activities_count=0,
            completed_late_count=0,
            completed_on_time_or_early_count=0,
            largest_current_overdue_days=0,
            average_completed_finish_variance=None,
        )
        baseline_actual = BaselineVsActualMetrics(
            scheduled_to_have_started=0,
            actually_started=0,
            scheduled_to_have_finished=0,
            actually_completed=0,
            average_start_variance_days=None,
        )
        supervisor_summary = None
        if assigned_discipline:
            supervisor_summary = SupervisorDisciplineSummary(
                assigned_discipline=assigned_discipline,
                total_activities=0,
                overall_progress=0.0,
                not_started=0,
                in_progress=0,
                on_hold=0,
                completed=0,
                overdue=0,
                today_work=[],
                overdue_activities=[],
                upcoming_deadlines=[],
                recent_updates=[],
            )

        return ProjectDashboardResponse(
            project=project_info,
            summary=summary,
            schedule_health=health,
            discipline_progress=[],
            today_work=[],
            overdue_activities=[],
            upcoming_deadlines=[],
            recent_updates=[],
            baseline_actual=baseline_actual,
            supervisor_summary=supervisor_summary,
        )

    # Counters & collections
    progress_sum = 0.0
    status_counts = {"NOT_STARTED": 0, "IN_PROGRESS": 0, "ON_HOLD": 0, "COMPLETED": 0}

    overdue_list: List[ActivityDashboardSummary] = []
    today_work_list: List[ActivityDashboardSummary] = []
    upcoming_deadlines_list: List[ActivityDashboardSummary] = []

    discipline_map: Dict[str, Dict[str, Any]] = {}

    completed_late_count = 0
    completed_on_time_or_early_count = 0
    finish_variances: List[int] = []
    start_variances: List[int] = []

    scheduled_to_have_started = 0
    actually_started = 0
    scheduled_to_have_finished = 0
    actually_completed = 0

    for activity, execution in activities_with_exec:
        disc = activity.discipline.strip() if activity.discipline and activity.discipline.strip() else "UNASSIGNED"
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
        disc_entry = discipline_map[disc]
        disc_entry["total_activities"] += 1

        exec_status = "NOT_STARTED"
        prog_pct = 0.0
        act_start = None
        act_finish = None

        if execution:
            raw_stat = execution.execution_status
            exec_status = raw_stat.value if hasattr(raw_stat, "value") else str(raw_stat)
            prog_pct = float(execution.progress_percentage or 0.0)
            act_start = execution.actual_start
            act_finish = execution.actual_finish

        progress_sum += prog_pct
        disc_entry["progress_sum"] += prog_pct

        if exec_status in status_counts:
            status_counts[exec_status] += 1
        else:
            status_counts["NOT_STARTED"] += 1

        if exec_status == "NOT_STARTED":
            disc_entry["not_started"] += 1
        elif exec_status == "IN_PROGRESS":
            disc_entry["in_progress"] += 1
        elif exec_status == "ON_HOLD":
            disc_entry["on_hold"] += 1
        elif exec_status == "COMPLETED":
            disc_entry["completed"] += 1

        # Check baseline vs actual adherence
        if activity.planned_start and activity.planned_start <= today:
            scheduled_to_have_started += 1

        if act_start is not None:
            actually_started += 1
            if activity.planned_start:
                start_variances.append((act_start - activity.planned_start).days)

        if activity.planned_finish and activity.planned_finish <= today:
            scheduled_to_have_finished += 1

        if exec_status == "COMPLETED":
            actually_completed += 1
            if act_finish and activity.planned_finish:
                f_var = (act_finish - activity.planned_finish).days
                finish_variances.append(f_var)
                if f_var > 0:
                    completed_late_count += 1
                else:
                    completed_on_time_or_early_count += 1
            else:
                completed_on_time_or_early_count += 1

        # Check Overdue condition: planned_finish < today AND execution_status != COMPLETED
        is_overdue = False
        overdue_days_val = None
        if activity.planned_finish and activity.planned_finish < today and exec_status != "COMPLETED":
            is_overdue = True
            overdue_days_val = (today - activity.planned_finish).days
            disc_entry["overdue"] += 1

            act_summary = ActivityDashboardSummary(
                activity_id=activity.id,
                activity_code=activity.activity_code,
                activity_name=activity.activity_name,
                discipline=disc,
                planned_start=activity.planned_start,
                planned_finish=activity.planned_finish,
                actual_start=act_start,
                actual_finish=act_finish,
                progress_percentage=prog_pct,
                execution_status=exec_status,
                overdue_days=overdue_days_val,
                wbs_code=activity.wbs_code,
            )
            overdue_list.append(act_summary)

        # Check Scheduled Today condition: planned_start <= today <= planned_finish AND execution_status != COMPLETED
        if (
            activity.planned_start
            and activity.planned_finish
            and activity.planned_start <= today <= activity.planned_finish
            and exec_status != "COMPLETED"
        ):
            act_summary = ActivityDashboardSummary(
                activity_id=activity.id,
                activity_code=activity.activity_code,
                activity_name=activity.activity_name,
                discipline=disc,
                planned_start=activity.planned_start,
                planned_finish=activity.planned_finish,
                actual_start=act_start,
                actual_finish=act_finish,
                progress_percentage=prog_pct,
                execution_status=exec_status,
                days_until_finish=(activity.planned_finish - today).days,
                wbs_code=activity.wbs_code,
            )
            today_work_list.append(act_summary)

        # Check Upcoming Deadline condition: today <= planned_finish <= today + 7 days AND execution_status != COMPLETED
        seven_days_later = today + timedelta(days=7)
        if (
            activity.planned_finish
            and today <= activity.planned_finish <= seven_days_later
            and exec_status != "COMPLETED"
        ):
            act_summary = ActivityDashboardSummary(
                activity_id=activity.id,
                activity_code=activity.activity_code,
                activity_name=activity.activity_name,
                discipline=disc,
                planned_start=activity.planned_start,
                planned_finish=activity.planned_finish,
                actual_start=act_start,
                actual_finish=act_finish,
                progress_percentage=prog_pct,
                execution_status=exec_status,
                days_until_finish=(activity.planned_finish - today).days,
                wbs_code=activity.wbs_code,
            )
            upcoming_deadlines_list.append(act_summary)

    # Sort lists
    # Overdue: highest overdue days first
    overdue_list.sort(key=lambda x: x.overdue_days or 0, reverse=True)
    # Today's work: discipline, then activity_code
    today_work_list.sort(key=lambda x: (x.discipline, x.activity_code))
    # Upcoming deadlines: nearest finish date first
    upcoming_deadlines_list.sort(key=lambda x: x.planned_finish or today)

    # Overall activity-weighted progress
    overall_progress = round(progress_sum / total_activities, 1)

    overdue_count = len(overdue_list)
    largest_overdue_days = max([x.overdue_days for x in overdue_list], default=0)

    avg_finish_var = None
    if finish_variances:
        avg_finish_var = round(sum(finish_variances) / len(finish_variances), 1)

    avg_start_var = None
    if start_variances:
        avg_start_var = round(sum(start_variances) / len(start_variances), 1)

    summary = DashboardSummary(
        total_activities=total_activities,
        overall_progress=overall_progress,
        not_started=status_counts["NOT_STARTED"],
        in_progress=status_counts["IN_PROGRESS"],
        on_hold=status_counts["ON_HOLD"],
        completed=status_counts["COMPLETED"],
        overdue=overdue_count,
    )

    health = ScheduleHealthMetrics(
        overdue_activities_count=overdue_count,
        completed_late_count=completed_late_count,
        completed_on_time_or_early_count=completed_on_time_or_early_count,
        largest_current_overdue_days=largest_overdue_days,
        average_completed_finish_variance=avg_finish_var,
    )

    baseline_actual = BaselineVsActualMetrics(
        scheduled_to_have_started=scheduled_to_have_started,
        actually_started=actually_started,
        scheduled_to_have_finished=scheduled_to_have_finished,
        actually_completed=actually_completed,
        average_start_variance_days=avg_start_var,
    )

    # Discipline Progress list
    discipline_progress: List[DisciplineProgressItem] = []
    for disc_name, ddata in discipline_map.items():
        disc_tot = ddata["total_activities"]
        disc_prog = round(ddata["progress_sum"] / disc_tot, 1) if disc_tot > 0 else 0.0
        discipline_progress.append(
            DisciplineProgressItem(
                discipline=disc_name,
                total_activities=disc_tot,
                overall_progress=disc_prog,
                not_started=ddata["not_started"],
                in_progress=ddata["in_progress"],
                on_hold=ddata["on_hold"],
                completed=ddata["completed"],
                overdue=ddata["overdue"],
            )
        )
    discipline_progress.sort(key=lambda x: x.discipline)

    # 3. Recent Site Updates (latest 10)
    recent_updates_raw = (
        db.query(ProgressUpdate, Activity, User)
        .join(Activity, ProgressUpdate.activity_id == Activity.id)
        .outerjoin(User, ProgressUpdate.reported_by_id == User.id)
        .filter(ProgressUpdate.project_id == project.id)
        .order_by(ProgressUpdate.created_at.desc())
        .limit(10)
        .all()
    )

    recent_updates: List[RecentUpdateItem] = []
    for update_obj, act_obj, user_obj in recent_updates_raw:
        disc = act_obj.discipline.strip() if act_obj.discipline and act_obj.discipline.strip() else "UNASSIGNED"
        reporter_name = user_obj.full_name if user_obj else "System/Unknown"
        update_type_val = (
            update_obj.update_type.value
            if hasattr(update_obj.update_type, "value")
            else str(update_obj.update_type)
        )
        source_type_val = (
            update_obj.source_type.value
            if hasattr(update_obj.source_type, "value")
            else str(update_obj.source_type)
        )

        recent_updates.append(
            RecentUpdateItem(
                id=update_obj.id,
                activity_id=act_obj.id,
                activity_code=act_obj.activity_code,
                activity_name=act_obj.activity_name,
                discipline=disc,
                update_type=update_type_val,
                reported_date=update_obj.reported_date,
                progress_percentage=float(update_obj.progress_percentage),
                remarks=update_obj.remarks,
                reporter_name=reporter_name,
                source_type=source_type_val,
                created_at=update_obj.created_at,
            )
        )

    # 4. Supervisor Discipline Summary if assigned
    supervisor_summary = None
    if assigned_discipline:
        norm_assigned = assigned_discipline.strip().upper()
        # Find matching discipline item
        disc_item = next((d for d in discipline_progress if d.discipline.upper() == norm_assigned), None)

        sup_today = [x for x in today_work_list if x.discipline.upper() == norm_assigned]
        sup_overdue = [x for x in overdue_list if x.discipline.upper() == norm_assigned]
        sup_upcoming = [x for x in upcoming_deadlines_list if x.discipline.upper() == norm_assigned]
        sup_recent = [x for x in recent_updates if x.discipline.upper() == norm_assigned]

        if disc_item:
            supervisor_summary = SupervisorDisciplineSummary(
                assigned_discipline=norm_assigned,
                total_activities=disc_item.total_activities,
                overall_progress=disc_item.overall_progress,
                not_started=disc_item.not_started,
                in_progress=disc_item.in_progress,
                on_hold=disc_item.on_hold,
                completed=disc_item.completed,
                overdue=disc_item.overdue,
                today_work=sup_today,
                overdue_activities=sup_overdue,
                upcoming_deadlines=sup_upcoming,
                recent_updates=sup_recent,
            )
        else:
            supervisor_summary = SupervisorDisciplineSummary(
                assigned_discipline=norm_assigned,
                total_activities=0,
                overall_progress=0.0,
                not_started=0,
                in_progress=0,
                on_hold=0,
                completed=0,
                overdue=0,
                today_work=[],
                overdue_activities=[],
                upcoming_deadlines=[],
                recent_updates=[],
            )

    return ProjectDashboardResponse(
        project=project_info,
        summary=summary,
        schedule_health=health,
        discipline_progress=discipline_progress,
        today_work=today_work_list,
        overdue_activities=overdue_list,
        upcoming_deadlines=upcoming_deadlines_list,
        recent_updates=recent_updates,
        baseline_actual=baseline_actual,
        supervisor_summary=supervisor_summary,
    )

from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.project import Project
from app.models.user import User
from app.core.datetime_utils import get_today_date
from app.schemas.analytics import (
    AnalyticsKPIs,
    AnalyticsSummaryResponse,
    ProgressTrendPoint,
    ProgressTrendResponse,
    DisciplineMetricItem,
    DisciplineAnalyticsResponse,
    RiskItem,
    ScheduleRiskResponse,
    ActivityForecastItem,
    ActivityForecastsResponse,
    CompletedActivityItem,
    CompletedPerformanceResponse,
)

ANALYTICS_STALE_UPDATE_DAYS = 3


def calculate_activity_expected_progress(
    planned_start: Optional[date], planned_finish: Optional[date], target_date: date
) -> float:
    """
    Calculates deterministic time-based linear expected progress for an activity
    as of a specific target date.
    
    - If target_date < planned_start: 0.0%
    - If target_date > planned_finish: 100.0%
    - If planned_start <= target_date <= planned_finish:
      linear elapsed-day progress clamped to [0.0, 100.0]%.
    """
    if not planned_start or not planned_finish:
        return 0.0

    if target_date < planned_start:
        return 0.0
    if target_date > planned_finish:
        return 100.0

    total_days = max((planned_finish - planned_start).days + 1, 1)
    elapsed_days = (target_date - planned_start).days + 1
    expected_pct = (100.0 * elapsed_days) / total_days
    return round(min(100.0, max(0.0, expected_pct)), 1)


def calculate_activity_forecast_internal(
    activity: Activity,
    execution: Optional[ActivityExecution],
    updates: List[ProgressUpdate],
    today: date,
) -> Dict[str, Any]:
    """
    Computes deterministic velocity and indicative finish date for an activity.
    Uses real percentage-bearing progress updates from ProgressUpdate history.
    """
    exec_status = "NOT_STARTED"
    current_progress = 0.0
    actual_finish = None

    if execution:
        raw_status = execution.execution_status
        exec_status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
        current_progress = float(execution.progress_percentage or 0.0)
        actual_finish = execution.actual_finish

    if exec_status == "COMPLETED":
        var_days = None
        if actual_finish and activity.planned_finish:
            var_days = (actual_finish - activity.planned_finish).days
        return {
            "forecast_status": "COMPLETED",
            "indicative_finish": actual_finish or activity.planned_finish,
            "forecast_variance_days": var_days,
            "progress_rate_pp_per_day": None,
            "data_quality": "GOOD" if actual_finish else "LIMITED",
            "observation_count": len(updates),
            "observation_span_days": 0,
        }

    if exec_status == "ON_HOLD":
        return {
            "forecast_status": "ON_HOLD",
            "indicative_finish": None,
            "forecast_variance_days": None,
            "progress_rate_pp_per_day": None,
            "data_quality": "INSUFFICIENT",
            "observation_count": len(updates),
            "observation_span_days": 0,
        }

    if exec_status == "NOT_STARTED":
        return {
            "forecast_status": "NOT_STARTED",
            "indicative_finish": None,
            "forecast_variance_days": None,
            "progress_rate_pp_per_day": None,
            "data_quality": "INSUFFICIENT",
            "observation_count": 0,
            "observation_span_days": 0,
        }

    # IN_PROGRESS activity
    if current_progress <= 0.0 or current_progress >= 100.0:
        return {
            "forecast_status": "INSUFFICIENT_DATA",
            "indicative_finish": None,
            "forecast_variance_days": None,
            "progress_rate_pp_per_day": None,
            "data_quality": "INSUFFICIENT",
            "observation_count": len(updates),
            "observation_span_days": 0,
        }

    # Filter percentage-bearing updates and collapse multiple updates on the same date
    valid_updates = [
        u for u in updates
        if u.progress_percentage is not None
    ]
    valid_updates.sort(key=lambda u: (u.reported_date, u.id))

    # Daily latest collapse
    date_to_pct: Dict[date, float] = {}
    for u in valid_updates:
        date_to_pct[u.reported_date] = float(u.progress_percentage)

    distinct_points = sorted(date_to_pct.items(), key=lambda x: x[0])
    obs_count = len(distinct_points)

    if obs_count < 2:
        return {
            "forecast_status": "INSUFFICIENT_DATA",
            "indicative_finish": None,
            "forecast_variance_days": None,
            "progress_rate_pp_per_day": None,
            "data_quality": "INSUFFICIENT",
            "observation_count": obs_count,
            "observation_span_days": 0,
        }

    # Take recent observation window (up to last 14 days or last 5 observations)
    window = distinct_points[-5:]
    first_date, first_pct = window[0]
    last_date, last_pct = window[-1]
    span_days = (last_date - first_date).days
    progress_delta = last_pct - first_pct

    if span_days < 1 or progress_delta <= 0.0:
        return {
            "forecast_status": "INSUFFICIENT_DATA",
            "indicative_finish": None,
            "forecast_variance_days": None,
            "progress_rate_pp_per_day": None,
            "data_quality": "INSUFFICIENT",
            "observation_count": obs_count,
            "observation_span_days": span_days,
        }

    velocity = progress_delta / span_days  # pp per day
    remaining_progress = 100.0 - current_progress
    est_remaining_days = round(remaining_progress / velocity)

    if est_remaining_days > 365:
        return {
            "forecast_status": "UNRELIABLE",
            "indicative_finish": None,
            "forecast_variance_days": None,
            "progress_rate_pp_per_day": round(velocity, 2),
            "data_quality": "LIMITED",
            "observation_count": obs_count,
            "observation_span_days": span_days,
        }

    forecast_finish = today + timedelta(days=int(est_remaining_days))
    forecast_variance_days = None
    if activity.planned_finish:
        forecast_variance_days = (forecast_finish - activity.planned_finish).days

    data_quality = "GOOD" if (obs_count >= 3 and span_days >= 3) else "LIMITED"

    return {
        "forecast_status": "FORECASTED",
        "indicative_finish": forecast_finish,
        "forecast_variance_days": forecast_variance_days,
        "progress_rate_pp_per_day": round(velocity, 2),
        "data_quality": data_quality,
        "observation_count": obs_count,
        "observation_span_days": span_days,
    }


def classify_activity_risk_internal(
    activity: Activity,
    execution: Optional[ActivityExecution],
    expected_progress: float,
    forecast_info: Dict[str, Any],
    updates: List[ProgressUpdate],
    today: date,
) -> Tuple[str, List[str]]:
    """
    Evaluates deterministic rule-based schedule risk: HIGH, MEDIUM, LOW, NORMAL
    and generates concise, explainable, deduplicated reasons.
    """
    exec_status = "NOT_STARTED"
    actual_progress = 0.0
    last_updated_at = None

    if execution:
        raw_status = execution.execution_status
        exec_status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
        actual_progress = float(execution.progress_percentage or 0.0)
        last_updated_at = execution.last_updated_at

    # Completed activities are not current risks
    if exec_status == "COMPLETED":
        return "NORMAL", []

    is_overdue = bool(activity.planned_finish and activity.planned_finish < today and exec_status != "COMPLETED")
    overdue_days = (today - activity.planned_finish).days if is_overdue and activity.planned_finish else 0
    variance_pp = round(actual_progress - expected_progress, 1)

    # Check update freshness for active work
    is_stale = False
    stale_days = 0
    if exec_status in ["IN_PROGRESS", "ON_HOLD"]:
        latest_date = None
        if updates:
            latest_date = max(u.reported_date for u in updates)
        elif last_updated_at:
            latest_date = last_updated_at.date() if isinstance(last_updated_at, datetime) else last_updated_at

        if latest_date:
            stale_days = (today - latest_date).days
            if stale_days > ANALYTICS_STALE_UPDATE_DAYS:
                is_stale = True

    reasons: List[str] = []

    # HIGH criteria checks
    if is_overdue:
        reasons.append(f"Activity is {overdue_days} days overdue.")
    if exec_status == "ON_HOLD":
        reasons.append("Activity is currently on hold.")
    forecast_var = forecast_info.get("forecast_variance_days")
    if forecast_var is not None and forecast_var > 7:
        reasons.append(f"Indicative finish is {forecast_var} days later than planned.")

    is_high = bool(is_overdue or exec_status == "ON_HOLD" or (forecast_var is not None and forecast_var > 7))

    if is_high:
        # If already high, optionally append secondary notable conditions if not duplicate
        if variance_pp <= -15.0 and f"Schedule variance is {variance_pp:.1f} pp behind expected." not in reasons:
            reasons.append(f"Schedule variance is {variance_pp:.1f} pp behind expected.")
        if is_stale:
            reasons.append(f"No execution updates for {stale_days} days.")
        return "HIGH", reasons

    # MEDIUM criteria checks
    approaching_deadline_delay = False
    if activity.planned_finish and today <= activity.planned_finish <= (today + timedelta(days=7)):
        if variance_pp <= -5.0 or actual_progress < expected_progress:
            approaching_deadline_delay = True

    is_medium = bool(variance_pp <= -15.0 or approaching_deadline_delay or is_stale)

    if is_medium:
        if variance_pp <= -15.0:
            reasons.append(f"Schedule variance is {variance_pp:.1f} pp behind expected.")
        if approaching_deadline_delay:
            reasons.append(f"Approaching planned finish with {abs(variance_pp):.1f} pp schedule lag.")
        if is_stale:
            reasons.append(f"No execution updates for {stale_days} days.")
        return "MEDIUM", reasons

    # LOW criteria checks
    is_low = bool(-15.0 < variance_pp <= -5.0 or (activity.planned_finish and today <= activity.planned_finish <= (today + timedelta(days=7)) and variance_pp < 0))
    if is_low:
        reasons.append(f"Minor schedule lag ({variance_pp:.1f} pp).")
        return "LOW", reasons

    return "NORMAL", []


def _load_project_activities_and_updates(
    db: Session, project_id: int, assigned_discipline: Optional[str] = None
) -> Tuple[List[Tuple[Activity, Optional[ActivityExecution]]], Dict[int, List[ProgressUpdate]]]:
    """Helper to fetch activities, executions and progress updates efficiently."""
    query = (
        db.query(Activity, ActivityExecution)
        .outerjoin(ActivityExecution, Activity.id == ActivityExecution.activity_id)
        .filter(Activity.project_id == project_id)
    )

    if assigned_discipline:
        norm_disc = assigned_discipline.strip().upper()
        query = query.filter(func.upper(Activity.discipline) == norm_disc)

    activities_with_exec = query.all()
    act_ids = [a.id for a, _ in activities_with_exec]

    updates_map: Dict[int, List[ProgressUpdate]] = {aid: [] for aid in act_ids}
    if act_ids:
        updates = (
            db.query(ProgressUpdate)
            .filter(ProgressUpdate.activity_id.in_(act_ids))
            .order_by(ProgressUpdate.reported_date.asc(), ProgressUpdate.id.asc())
            .all()
        )
        for u in updates:
            if u.activity_id in updates_map:
                updates_map[u.activity_id].append(u)

    return activities_with_exec, updates_map


def get_analytics_summary_data(
    db: Session, project: Project, user: User, assigned_discipline: Optional[str] = None
) -> AnalyticsSummaryResponse:
    today = get_today_date()
    activities_with_exec, updates_map = _load_project_activities_and_updates(
        db, project.id, assigned_discipline
    )

    total_activities = len(activities_with_exec)

    if total_activities == 0:
        kpis = AnalyticsKPIs(
            actual_progress=0.0,
            expected_progress=0.0,
            progress_variance_pp=0.0,
            total_activities=0,
            completed_activities=0,
            in_progress_activities=0,
            not_started_activities=0,
            on_hold_activities=0,
            currently_overdue=0,
            at_risk_count=0,
            high_risk_count=0,
            medium_risk_count=0,
            low_risk_count=0,
            indicative_completion_date=project.planned_end_date,
            baseline_completion_date=project.planned_end_date,
            indicative_variance_days=0 if project.planned_end_date else None,
            forecast_coverage_count=0,
            incomplete_activity_count=0,
            forecast_coverage_pct=0.0,
            is_discipline_scoped=bool(assigned_discipline),
            scoped_discipline=assigned_discipline,
        )
        return AnalyticsSummaryResponse(
            project_id=project.id,
            project_name=project.name,
            project_code=project.project_code,
            kpis=kpis,
        )

    actual_progress_sum = 0.0
    expected_progress_sum = 0.0

    status_counts = {"NOT_STARTED": 0, "IN_PROGRESS": 0, "ON_HOLD": 0, "COMPLETED": 0}
    overdue_count = 0
    risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "NORMAL": 0}

    incomplete_count = 0
    forecast_coverage_count = 0
    incomplete_finish_candidates: List[date] = []

    for activity, execution in activities_with_exec:
        exec_status = "NOT_STARTED"
        prog_pct = 0.0
        if execution:
            raw_status = execution.execution_status
            exec_status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
            prog_pct = float(execution.progress_percentage or 0.0)

        actual_progress_sum += prog_pct
        if exec_status in status_counts:
            status_counts[exec_status] += 1
        else:
            status_counts["NOT_STARTED"] += 1

        exp_pct = calculate_activity_expected_progress(activity.planned_start, activity.planned_finish, today)
        expected_progress_sum += exp_pct

        # Check overdue
        if activity.planned_finish and activity.planned_finish < today and exec_status != "COMPLETED":
            overdue_count += 1

        # Calculate forecast
        act_updates = updates_map.get(activity.id, [])
        f_info = calculate_activity_forecast_internal(activity, execution, act_updates, today)

        # Classify risk
        risk_level, _ = classify_activity_risk_internal(
            activity, execution, exp_pct, f_info, act_updates, today
        )
        risk_counts[risk_level] += 1

        if exec_status != "COMPLETED":
            incomplete_count += 1
            if f_info.get("forecast_status") == "FORECASTED" and f_info.get("indicative_finish"):
                forecast_coverage_count += 1
                incomplete_finish_candidates.append(f_info["indicative_finish"])
            elif activity.planned_finish:
                incomplete_finish_candidates.append(activity.planned_finish)

    actual_project_progress = round(actual_progress_sum / total_activities, 1)
    expected_project_progress = round(expected_progress_sum / total_activities, 1)
    variance_pp = round(actual_project_progress - expected_project_progress, 1)

    at_risk_total = risk_counts["HIGH"] + risk_counts["MEDIUM"] + risk_counts["LOW"]

    # Indicative project completion calculation
    indicative_date = None
    if incomplete_finish_candidates:
        indicative_date = max(incomplete_finish_candidates)
    elif project.planned_end_date:
        indicative_date = project.planned_end_date

    baseline_date = project.planned_end_date
    if not baseline_date:
        planned_finishes = [a.planned_finish for a, _ in activities_with_exec if a.planned_finish]
        if planned_finishes:
            baseline_date = max(planned_finishes)

    indicative_var_days = None
    if indicative_date and baseline_date:
        indicative_var_days = (indicative_date - baseline_date).days

    coverage_pct = (
        round(100.0 * forecast_coverage_count / max(incomplete_count, 1), 1)
        if incomplete_count > 0
        else 100.0
    )

    kpis = AnalyticsKPIs(
        actual_progress=actual_project_progress,
        expected_progress=expected_project_progress,
        progress_variance_pp=variance_pp,
        total_activities=total_activities,
        completed_activities=status_counts["COMPLETED"],
        in_progress_activities=status_counts["IN_PROGRESS"],
        not_started_activities=status_counts["NOT_STARTED"],
        on_hold_activities=status_counts["ON_HOLD"],
        currently_overdue=overdue_count,
        at_risk_count=at_risk_total,
        high_risk_count=risk_counts["HIGH"],
        medium_risk_count=risk_counts["MEDIUM"],
        low_risk_count=risk_counts["LOW"],
        indicative_completion_date=indicative_date,
        baseline_completion_date=baseline_date,
        indicative_variance_days=indicative_var_days,
        forecast_coverage_count=forecast_coverage_count,
        incomplete_activity_count=incomplete_count,
        forecast_coverage_pct=coverage_pct,
        is_discipline_scoped=bool(assigned_discipline),
        scoped_discipline=assigned_discipline,
    )

    return AnalyticsSummaryResponse(
        project_id=project.id,
        project_name=project.name,
        project_code=project.project_code,
        kpis=kpis,
    )


def get_progress_trend_data(
    db: Session,
    project: Project,
    user: User,
    assigned_discipline: Optional[str] = None,
    range_key: str = "30d",
) -> ProgressTrendResponse:
    """
    Reconstructs true historical progress by replaying ProgressUpdate history for each date.
    No fake daily points or interpolations are generated.
    """
    today = get_today_date()
    range_key_norm = range_key.strip().lower()

    if range_key_norm == "7d":
        days_back = 7
    elif range_key_norm == "90d":
        days_back = 90
    elif range_key_norm == "all":
        days_back = 180  # Up to 6 months history or project duration
    else:
        range_key_norm = "30d"
        days_back = 30

    start_date = today - timedelta(days=days_back - 1)

    activities_with_exec, updates_map = _load_project_activities_and_updates(
        db, project.id, assigned_discipline
    )

    total_activities = len(activities_with_exec)
    if total_activities == 0:
        return ProgressTrendResponse(
            range=range_key_norm,
            start_date=start_date.isoformat(),
            end_date=today.isoformat(),
            trend_points=[],
        )

    # Pre-index updates per activity sorted by reported_date
    act_updates_sorted: Dict[int, List[Tuple[date, float, int]]] = {}
    for act, _ in activities_with_exec:
        raw_list = updates_map.get(act.id, [])
        cleaned: List[Tuple[date, float, int]] = []
        for u in raw_list:
            if u.progress_percentage is not None:
                cleaned.append((u.reported_date, float(u.progress_percentage), u.id))
        cleaned.sort(key=lambda x: (x[0], x[2]))
        act_updates_sorted[act.id] = cleaned

    trend_points: List[ProgressTrendPoint] = []
    curr_date = start_date

    while curr_date <= today:
        daily_actual_sum = 0.0
        daily_expected_sum = 0.0

        for act, _ in activities_with_exec:
            # Determine latest reported progress as of curr_date
            up_list = act_updates_sorted.get(act.id, [])
            latest_pct_as_of_d = 0.0
            for rep_date, pct, _ in up_list:
                if rep_date <= curr_date:
                    latest_pct_as_of_d = pct
                else:
                    break

            daily_actual_sum += latest_pct_as_of_d

            # Deterministic time-based expected progress as of curr_date
            exp_pct_d = calculate_activity_expected_progress(act.planned_start, act.planned_finish, curr_date)
            daily_expected_sum += exp_pct_d

        act_avg = round(daily_actual_sum / total_activities, 1)
        exp_avg = round(daily_expected_sum / total_activities, 1)
        var_avg = round(act_avg - exp_avg, 1)

        trend_points.append(
            ProgressTrendPoint(
                date=curr_date.isoformat(),
                actual_progress=act_avg,
                expected_progress=exp_avg,
                progress_variance_pp=var_avg,
            )
        )
        curr_date += timedelta(days=1)

    return ProgressTrendResponse(
        range=range_key_norm,
        start_date=start_date.isoformat(),
        end_date=today.isoformat(),
        trend_points=trend_points,
    )


def get_discipline_analytics_data(
    db: Session, project: Project, user: User, assigned_discipline: Optional[str] = None
) -> DisciplineAnalyticsResponse:
    today = get_today_date()
    activities_with_exec, updates_map = _load_project_activities_and_updates(
        db, project.id, assigned_discipline
    )

    discipline_map: Dict[str, Dict[str, Any]] = {}

    for activity, execution in activities_with_exec:
        disc = activity.discipline.strip() if activity.discipline and activity.discipline.strip() else "UNASSIGNED"
        if disc not in discipline_map:
            discipline_map[disc] = {
                "discipline": disc,
                "total_activities": 0,
                "actual_progress_sum": 0.0,
                "expected_progress_sum": 0.0,
                "completed": 0,
                "in_progress": 0,
                "not_started": 0,
                "on_hold": 0,
                "overdue": 0,
                "at_risk": 0,
            }

        d_entry = discipline_map[disc]
        d_entry["total_activities"] += 1

        exec_status = "NOT_STARTED"
        prog_pct = 0.0
        if execution:
            raw_status = execution.execution_status
            exec_status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
            prog_pct = float(execution.progress_percentage or 0.0)

        d_entry["actual_progress_sum"] += prog_pct

        if exec_status == "COMPLETED":
            d_entry["completed"] += 1
        elif exec_status == "IN_PROGRESS":
            d_entry["in_progress"] += 1
        elif exec_status == "ON_HOLD":
            d_entry["on_hold"] += 1
        else:
            d_entry["not_started"] += 1

        exp_pct = calculate_activity_expected_progress(activity.planned_start, activity.planned_finish, today)
        d_entry["expected_progress_sum"] += exp_pct

        if activity.planned_finish and activity.planned_finish < today and exec_status != "COMPLETED":
            d_entry["overdue"] += 1

        act_updates = updates_map.get(activity.id, [])
        f_info = calculate_activity_forecast_internal(activity, execution, act_updates, today)
        risk_level, _ = classify_activity_risk_internal(
            activity, execution, exp_pct, f_info, act_updates, today
        )
        if risk_level in ["HIGH", "MEDIUM", "LOW"]:
            d_entry["at_risk"] += 1

    items: List[DisciplineMetricItem] = []
    for disc_name, d in discipline_map.items():
        tot = d["total_activities"]
        act_prog = round(d["actual_progress_sum"] / tot, 1) if tot > 0 else 0.0
        exp_prog = round(d["expected_progress_sum"] / tot, 1) if tot > 0 else 0.0
        var_pp = round(act_prog - exp_prog, 1)

        items.append(
            DisciplineMetricItem(
                discipline=disc_name,
                total_activities=tot,
                completed=d["completed"],
                in_progress=d["in_progress"],
                not_started=d["not_started"],
                on_hold=d["on_hold"],
                actual_progress=act_prog,
                expected_progress=exp_prog,
                progress_variance_pp=var_pp,
                overdue_count=d["overdue"],
                at_risk_count=d["at_risk"],
            )
        )

    items.sort(key=lambda x: x.discipline)
    return DisciplineAnalyticsResponse(disciplines=items)


def get_schedule_risks_data(
    db: Session,
    project: Project,
    user: User,
    assigned_discipline: Optional[str] = None,
    level_filter: Optional[str] = None,
    discipline_filter: Optional[str] = None,
) -> ScheduleRiskResponse:
    today = get_today_date()
    effective_discipline = assigned_discipline if assigned_discipline else discipline_filter
    activities_with_exec, updates_map = _load_project_activities_and_updates(
        db, project.id, effective_discipline
    )

    risk_items: List[RiskItem] = []
    high_count = 0
    medium_count = 0
    low_count = 0

    for activity, execution in activities_with_exec:
        exec_status = "NOT_STARTED"
        prog_pct = 0.0
        act_start = None
        last_updated = None

        if execution:
            raw_status = execution.execution_status
            exec_status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
            prog_pct = float(execution.progress_percentage or 0.0)
            act_start = execution.actual_start
            last_updated = execution.last_updated_at

        # Completed activities do not appear in current at-risk list
        if exec_status == "COMPLETED":
            continue

        exp_pct = calculate_activity_expected_progress(activity.planned_start, activity.planned_finish, today)
        var_pp = round(prog_pct - exp_pct, 1)

        act_updates = updates_map.get(activity.id, [])
        f_info = calculate_activity_forecast_internal(activity, execution, act_updates, today)
        risk_level, reasons = classify_activity_risk_internal(
            activity, execution, exp_pct, f_info, act_updates, today
        )

        if risk_level == "HIGH":
            high_count += 1
        elif risk_level == "MEDIUM":
            medium_count += 1
        elif risk_level == "LOW":
            low_count += 1

        is_overdue = bool(activity.planned_finish and activity.planned_finish < today and exec_status != "COMPLETED")
        overdue_days = (today - activity.planned_finish).days if is_overdue and activity.planned_finish else None

        # Filter by risk level if requested
        if level_filter and level_filter.upper() != "ALL":
            if risk_level != level_filter.upper():
                continue
        else:
            # Default risk view shows activities with risk level in HIGH, MEDIUM, LOW
            if risk_level == "NORMAL":
                continue

        disc = activity.discipline.strip() if activity.discipline and activity.discipline.strip() else "UNASSIGNED"

        risk_items.append(
            RiskItem(
                activity_id=activity.id,
                activity_code=activity.activity_code,
                activity_name=activity.activity_name,
                discipline=disc,
                wbs_code=activity.wbs_code,
                planned_start=activity.planned_start,
                planned_finish=activity.planned_finish,
                actual_start=act_start,
                current_progress=prog_pct,
                expected_progress=exp_pct,
                progress_variance_pp=var_pp,
                execution_status=exec_status,
                overdue_days=overdue_days,
                last_updated_at=last_updated,
                risk_level=risk_level,
                risk_reasons=reasons,
                forecast_finish=f_info.get("indicative_finish"),
                forecast_variance_days=f_info.get("forecast_variance_days"),
            )
        )

    # Sort risks: HIGH first, then MEDIUM, then LOW; within level by highest overdue or largest negative variance
    level_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NORMAL": 3}
    risk_items.sort(key=lambda x: (level_order.get(x.risk_level, 99), x.progress_variance_pp))

    return ScheduleRiskResponse(
        total_at_risk=high_count + medium_count + low_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        items=risk_items,
    )


def get_activity_forecasts_data(
    db: Session, project: Project, user: User, assigned_discipline: Optional[str] = None
) -> ActivityForecastsResponse:
    today = get_today_date()
    activities_with_exec, updates_map = _load_project_activities_and_updates(
        db, project.id, assigned_discipline
    )

    forecast_items: List[ActivityForecastItem] = []
    incomplete_count = 0
    forecast_coverage_count = 0
    incomplete_finishes: List[date] = []

    for activity, execution in activities_with_exec:
        exec_status = "NOT_STARTED"
        prog_pct = 0.0
        if execution:
            raw_status = execution.execution_status
            exec_status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
            prog_pct = float(execution.progress_percentage or 0.0)

        # Show incomplete activities in forecast list
        if exec_status == "COMPLETED":
            continue

        incomplete_count += 1
        act_updates = updates_map.get(activity.id, [])
        f_info = calculate_activity_forecast_internal(activity, execution, act_updates, today)

        if f_info.get("forecast_status") == "FORECASTED" and f_info.get("indicative_finish"):
            forecast_coverage_count += 1
            incomplete_finishes.append(f_info["indicative_finish"])
        elif activity.planned_finish:
            incomplete_finishes.append(activity.planned_finish)

        disc = activity.discipline.strip() if activity.discipline and activity.discipline.strip() else "UNASSIGNED"

        forecast_items.append(
            ActivityForecastItem(
                activity_id=activity.id,
                activity_code=activity.activity_code,
                activity_name=activity.activity_name,
                discipline=disc,
                wbs_code=activity.wbs_code,
                execution_status=exec_status,
                current_progress=prog_pct,
                progress_rate_pp_per_day=f_info.get("progress_rate_pp_per_day"),
                planned_finish=activity.planned_finish,
                indicative_finish=f_info.get("indicative_finish"),
                forecast_variance_days=f_info.get("forecast_variance_days"),
                data_quality=f_info.get("data_quality", "INSUFFICIENT"),
                forecast_status=f_info.get("forecast_status", "INSUFFICIENT_DATA"),
                observation_count=f_info.get("observation_count", 0),
                observation_span_days=f_info.get("observation_span_days", 0),
            )
        )

    # Sort forecasts: IN_PROGRESS first, then largest variance or nearest finish
    status_order = {"IN_PROGRESS": 0, "ON_HOLD": 1, "NOT_STARTED": 2}
    forecast_items.sort(
        key=lambda x: (
            status_order.get(x.execution_status, 99),
            -(x.forecast_variance_days or -9999),
            x.planned_finish or today,
        )
    )

    indicative_project_date = max(incomplete_finishes) if incomplete_finishes else project.planned_end_date
    baseline_date = project.planned_end_date
    if not baseline_date:
        planned_finishes = [a.planned_finish for a, _ in activities_with_exec if a.planned_finish]
        if planned_finishes:
            baseline_date = max(planned_finishes)

    var_days = None
    if indicative_project_date and baseline_date:
        var_days = (indicative_project_date - baseline_date).days

    coverage_pct = (
        round(100.0 * forecast_coverage_count / max(incomplete_count, 1), 1)
        if incomplete_count > 0
        else 100.0
    )

    return ActivityForecastsResponse(
        indicative_project_completion=indicative_project_date,
        baseline_project_completion=baseline_date,
        project_indicative_variance_days=var_days,
        forecast_coverage_count=forecast_coverage_count,
        incomplete_activity_count=incomplete_count,
        forecast_coverage_pct=coverage_pct,
        forecasts=forecast_items,
    )


def get_completed_performance_data(
    db: Session, project: Project, user: User, assigned_discipline: Optional[str] = None
) -> CompletedPerformanceResponse:
    activities_with_exec, _ = _load_project_activities_and_updates(
        db, project.id, assigned_discipline
    )

    completed_items: List[CompletedActivityItem] = []
    finish_variances: List[int] = []
    on_time_count = 0
    late_count = 0

    for activity, execution in activities_with_exec:
        if not execution:
            continue

        raw_status = execution.execution_status
        exec_status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)

        if exec_status != "COMPLETED":
            continue

        act_finish = execution.actual_finish
        planned_finish = activity.planned_finish
        var_days = (act_finish - planned_finish).days if act_finish and planned_finish else 0

        finish_variances.append(var_days)
        is_late = var_days > 0

        if is_late:
            late_count += 1
        else:
            on_time_count += 1

        disc = activity.discipline.strip() if activity.discipline and activity.discipline.strip() else "UNASSIGNED"

        completed_items.append(
            CompletedActivityItem(
                activity_id=activity.id,
                activity_code=activity.activity_code,
                activity_name=activity.activity_name,
                discipline=disc,
                planned_finish=planned_finish,
                actual_finish=act_finish,
                finish_variance_days=var_days,
                is_late=is_late,
            )
        )

    completed_items.sort(key=lambda x: x.actual_finish or date.min, reverse=True)

    avg_var = None
    if finish_variances:
        avg_var = round(sum(finish_variances) / len(finish_variances), 1)

    return CompletedPerformanceResponse(
        total_completed=len(completed_items),
        completed_on_time_or_early=on_time_count,
        completed_late=late_count,
        average_finish_variance_days=avg_var,
        completed_activities=completed_items,
    )

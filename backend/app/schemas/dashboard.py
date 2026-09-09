from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime


class DashboardProjectInfo(BaseModel):
    id: int
    name: str
    project_code: str
    location: Optional[str] = None
    status: str
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    days_until_planned_finish: Optional[int] = None
    deadline_label: str

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    total_activities: int
    overall_progress: float
    not_started: int
    in_progress: int
    on_hold: int
    completed: int
    overdue: int


class ScheduleHealthMetrics(BaseModel):
    overdue_activities_count: int
    completed_late_count: int
    completed_on_time_or_early_count: int
    largest_current_overdue_days: int
    average_completed_finish_variance: Optional[float] = None


class DisciplineProgressItem(BaseModel):
    discipline: str
    total_activities: int
    overall_progress: float
    not_started: int
    in_progress: int
    on_hold: int
    completed: int
    overdue: int


class ActivityDashboardSummary(BaseModel):
    activity_id: int
    activity_code: str
    activity_name: str
    discipline: str
    planned_start: Optional[date] = None
    planned_finish: Optional[date] = None
    actual_start: Optional[date] = None
    actual_finish: Optional[date] = None
    progress_percentage: float
    execution_status: str
    overdue_days: Optional[int] = None
    days_until_finish: Optional[int] = None
    wbs_code: Optional[str] = None


class RecentUpdateItem(BaseModel):
    id: int
    activity_id: int
    activity_code: str
    activity_name: str
    discipline: str
    update_type: str
    reported_date: date
    progress_percentage: float
    remarks: Optional[str] = None
    reporter_name: str
    source_type: str
    created_at: datetime


class BaselineVsActualMetrics(BaseModel):
    scheduled_to_have_started: int
    actually_started: int
    scheduled_to_have_finished: int
    actually_completed: int
    average_start_variance_days: Optional[float] = None


class SupervisorDisciplineSummary(BaseModel):
    assigned_discipline: str
    total_activities: int
    overall_progress: float
    not_started: int
    in_progress: int
    on_hold: int
    completed: int
    overdue: int
    today_work: List[ActivityDashboardSummary] = []
    overdue_activities: List[ActivityDashboardSummary] = []
    upcoming_deadlines: List[ActivityDashboardSummary] = []
    recent_updates: List[RecentUpdateItem] = []


class ProjectDashboardResponse(BaseModel):
    project: DashboardProjectInfo
    summary: DashboardSummary
    schedule_health: ScheduleHealthMetrics
    discipline_progress: List[DisciplineProgressItem]
    today_work: List[ActivityDashboardSummary]
    overdue_activities: List[ActivityDashboardSummary]
    upcoming_deadlines: List[ActivityDashboardSummary]
    recent_updates: List[RecentUpdateItem]
    baseline_actual: BaselineVsActualMetrics
    supervisor_summary: Optional[SupervisorDisciplineSummary] = None

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel


class AnalyticsKPIs(BaseModel):
    actual_progress: float
    expected_progress: float
    progress_variance_pp: float
    total_activities: int
    completed_activities: int
    in_progress_activities: int
    not_started_activities: int
    on_hold_activities: int
    currently_overdue: int
    at_risk_count: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    indicative_completion_date: Optional[date] = None
    baseline_completion_date: Optional[date] = None
    indicative_variance_days: Optional[int] = None
    forecast_coverage_count: int = 0
    incomplete_activity_count: int = 0
    forecast_coverage_pct: float = 0.0
    is_discipline_scoped: bool = False
    scoped_discipline: Optional[str] = None


class AnalyticsSummaryResponse(BaseModel):
    project_id: int
    project_name: str
    project_code: str
    kpis: AnalyticsKPIs


class ProgressTrendPoint(BaseModel):
    date: str  # YYYY-MM-DD
    actual_progress: float
    expected_progress: float
    progress_variance_pp: float


class ProgressTrendResponse(BaseModel):
    range: str
    start_date: str
    end_date: str
    trend_points: List[ProgressTrendPoint]


class DisciplineMetricItem(BaseModel):
    discipline: str
    total_activities: int
    completed: int
    in_progress: int
    not_started: int
    on_hold: int
    actual_progress: float
    expected_progress: float
    progress_variance_pp: float
    overdue_count: int
    at_risk_count: int


class DisciplineAnalyticsResponse(BaseModel):
    disciplines: List[DisciplineMetricItem]


class RiskItem(BaseModel):
    activity_id: int
    activity_code: str
    activity_name: str
    discipline: str
    wbs_code: Optional[str] = None
    planned_start: Optional[date] = None
    planned_finish: Optional[date] = None
    actual_start: Optional[date] = None
    current_progress: float
    expected_progress: float
    progress_variance_pp: float
    execution_status: str
    overdue_days: Optional[int] = None
    last_updated_at: Optional[datetime] = None
    risk_level: str  # HIGH, MEDIUM, LOW, NORMAL
    risk_reasons: List[str]
    forecast_finish: Optional[date] = None
    forecast_variance_days: Optional[int] = None


class ScheduleRiskResponse(BaseModel):
    total_at_risk: int
    high_count: int
    medium_count: int
    low_count: int
    items: List[RiskItem]


class ActivityForecastItem(BaseModel):
    activity_id: int
    activity_code: str
    activity_name: str
    discipline: str
    wbs_code: Optional[str] = None
    execution_status: str
    current_progress: float
    progress_rate_pp_per_day: Optional[float] = None
    planned_finish: Optional[date] = None
    indicative_finish: Optional[date] = None
    forecast_variance_days: Optional[int] = None
    data_quality: str  # GOOD, LIMITED, INSUFFICIENT
    forecast_status: str  # FORECASTED, INSUFFICIENT_DATA, ON_HOLD, NOT_STARTED, COMPLETED, UNRELIABLE
    observation_count: int = 0
    observation_span_days: int = 0


class ActivityForecastsResponse(BaseModel):
    indicative_project_completion: Optional[date] = None
    baseline_project_completion: Optional[date] = None
    project_indicative_variance_days: Optional[int] = None
    forecast_coverage_count: int
    incomplete_activity_count: int
    forecast_coverage_pct: float
    forecasts: List[ActivityForecastItem]


class CompletedActivityItem(BaseModel):
    activity_id: int
    activity_code: str
    activity_name: str
    discipline: str
    planned_finish: Optional[date] = None
    actual_finish: Optional[date] = None
    finish_variance_days: int
    is_late: bool


class CompletedPerformanceResponse(BaseModel):
    total_completed: int
    completed_on_time_or_early: int
    completed_late: int
    average_finish_variance_days: Optional[float] = None
    completed_activities: List[CompletedActivityItem]

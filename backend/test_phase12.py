import unittest
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.main import app
from app.core.security import hash_password, create_access_token
from app.core.datetime_utils import get_today_date
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.services.analytics_service import (
    calculate_activity_expected_progress,
    calculate_activity_forecast_internal,
    classify_activity_risk_internal,
    get_analytics_summary_data,
    get_progress_trend_data,
    get_discipline_analytics_data,
    get_schedule_risks_data,
    get_activity_forecasts_data,
    get_completed_performance_data,
)

# Isolated in-memory SQLite database
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class Phase12AnalyticsForecastingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        self.db = TestingSessionLocal()

        # Clear tables
        self.db.query(ProgressUpdate).delete()
        self.db.query(ActivityExecution).delete()
        self.db.query(Activity).delete()
        self.db.query(ProjectMember).delete()
        self.db.query(Project).delete()
        self.db.query(User).delete()
        self.db.commit()

        # Create Planner User
        self.planner = User(
            email="lead.planner@infrastructure.org",
            hashed_password=hash_password("PlannerPass123!"),
            full_name="Lead Project Planner",
            role="PLANNER",
            is_active=True,
        )
        # Create Civil Supervisor
        self.sup_civil = User(
            email="civil.sup@infrastructure.org",
            hashed_password=hash_password("SupervisorPass123!"),
            full_name="Civil Field Supervisor",
            role="SUPERVISOR",
            is_active=True,
        )
        # Create Piping Supervisor
        self.sup_piping = User(
            email="piping.sup@infrastructure.org",
            hashed_password=hash_password("SupervisorPass123!"),
            full_name="Piping Field Supervisor",
            role="SUPERVISOR",
            is_active=True,
        )
        self.db.add_all([self.planner, self.sup_civil, self.sup_piping])
        self.db.commit()
        self.db.refresh(self.planner)
        self.db.refresh(self.sup_civil)
        self.db.refresh(self.sup_piping)

        # Create Project
        self.project = Project(
            project_code="PRJ-ANALYTICS-01",
            name="Terminal Expansion Refinery",
            description="Phase 12 Analytics Test Facility",
            location="Site Alpha",
            planned_start_date=date(2026, 1, 1),
            planned_end_date=date(2026, 12, 31),
            created_by_id=self.planner.id,
        )
        self.db.add(self.project)
        self.db.commit()
        self.db.refresh(self.project)

        # Assign Civil Supervisor
        self.pm_civil = ProjectMember(
            project_id=self.project.id,
            user_id=self.sup_civil.id,
            discipline="CIVIL",
        )
        # Assign Piping Supervisor
        self.pm_piping = ProjectMember(
            project_id=self.project.id,
            user_id=self.sup_piping.id,
            discipline="PIPING",
        )
        self.db.add_all([self.pm_civil, self.pm_piping])
        self.db.commit()

        # Auth Tokens
        self.planner_token = create_access_token(self.planner.id)
        self.civil_token = create_access_token(self.sup_civil.id)
        self.piping_token = create_access_token(self.sup_piping.id)

    def tearDown(self):
        self.db.close()

    # TEST 1: Activity without execution -> actual progress = 0
    def test_01_activity_without_execution_actual_progress(self):
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-001",
            activity_name="Site Clearing",
            discipline="CIVIL",
            planned_start=date(2026, 5, 1),
            planned_finish=date(2026, 6, 1),
        )
        self.db.add(act)
        self.db.commit()

        summary = get_analytics_summary_data(self.db, self.project, self.planner)
        self.assertEqual(summary.kpis.actual_progress, 0.0)
        self.assertEqual(summary.kpis.not_started_activities, 1)

    # TEST 2: Activity before planned start -> expected progress = 0
    def test_02_activity_before_planned_start_expected_zero(self):
        today = get_today_date()
        future_start = today + timedelta(days=10)
        future_finish = today + timedelta(days=30)
        exp = calculate_activity_expected_progress(future_start, future_finish, today)
        self.assertEqual(exp, 0.0)

    # TEST 3: Activity after planned finish -> expected progress = 100
    def test_03_activity_after_planned_finish_expected_hundred(self):
        today = get_today_date()
        past_start = today - timedelta(days=40)
        past_finish = today - timedelta(days=10)
        exp = calculate_activity_expected_progress(past_start, past_finish, today)
        self.assertEqual(exp, 100.0)

    # TEST 4: Activity midway through planned duration -> proportional expected progress
    def test_04_activity_midway_proportional_expected(self):
        # 11-day duration: day 1 to day 11. Midway at day 6 -> 6/11 * 100 = 54.5%
        p_start = date(2026, 6, 1)
        p_finish = date(2026, 6, 11)
        target = date(2026, 6, 6)  # Day 6 elapsed out of 11 total days
        exp = calculate_activity_expected_progress(p_start, p_finish, target)
        self.assertAlmostEqual(exp, 54.5, delta=0.1)

    # TEST 5: Actual 40%, Expected 60% -> variance = -20 pp
    def test_05_schedule_variance_calculation(self):
        today = get_today_date()
        # Activity with planned start 5 days ago, finish in 5 days (total 11 days, elapsed 6 days -> ~54.5%)
        # Let's create an activity with expected = 60.0%
        # Total days = 10, elapsed = 6 -> 60.0%
        p_start = today - timedelta(days=5)
        p_finish = today + timedelta(days=4)  # total days = 10, elapsed = 6 -> 60.0%
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-VAR-01",
            activity_name="Foundation Concrete",
            discipline="CIVIL",
            planned_start=p_start,
            planned_finish=p_finish,
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="IN_PROGRESS",
            progress_percentage=40.0,
            actual_start=p_start,
        )
        self.db.add(exec_obj)
        self.db.commit()

        summary = get_analytics_summary_data(self.db, self.project, self.planner)
        self.assertEqual(summary.kpis.actual_progress, 40.0)
        self.assertEqual(summary.kpis.expected_progress, 60.0)
        self.assertEqual(summary.kpis.progress_variance_pp, -20.0)

    # TEST 6: Currently overdue activity -> HIGH risk with overdue reason
    def test_06_overdue_activity_high_risk(self):
        today = get_today_date()
        p_start = today - timedelta(days=20)
        p_finish = today - timedelta(days=5)  # 5 days overdue
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-OD-01",
            activity_name="Earthwork Excavation",
            discipline="CIVIL",
            planned_start=p_start,
            planned_finish=p_finish,
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="IN_PROGRESS",
            progress_percentage=70.0,
            actual_start=p_start,
        )
        self.db.add(exec_obj)
        self.db.commit()

        risks = get_schedule_risks_data(self.db, self.project, self.planner)
        self.assertEqual(risks.high_count, 1)
        self.assertEqual(len(risks.items), 1)
        self.assertEqual(risks.items[0].risk_level, "HIGH")
        self.assertTrue(any("5 days overdue" in r for r in risks.items[0].risk_reasons))

    # TEST 7: ON_HOLD activity -> HIGH risk
    def test_07_on_hold_activity_high_risk(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-HOLD-01",
            activity_name="Trench Shoring",
            discipline="CIVIL",
            planned_start=today - timedelta(days=5),
            planned_finish=today + timedelta(days=15),
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="ON_HOLD",
            progress_percentage=25.0,
            actual_start=today - timedelta(days=5),
        )
        self.db.add(exec_obj)
        self.db.commit()

        risks = get_schedule_risks_data(self.db, self.project, self.planner)
        self.assertEqual(risks.high_count, 1)
        self.assertEqual(risks.items[0].risk_level, "HIGH")
        self.assertTrue(any("on hold" in r.lower() for r in risks.items[0].risk_reasons))

    # TEST 8: Activity 20 pp behind expected -> at least MEDIUM risk
    def test_08_activity_twenty_pp_behind_medium_risk(self):
        today = get_today_date()
        # 10 days total, elapsed 6 -> expected = 60%, actual = 40% -> variance = -20 pp
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-MED-01",
            activity_name="Column Rebar",
            discipline="CIVIL",
            planned_start=today - timedelta(days=5),
            planned_finish=today + timedelta(days=20),  # Not overdue
        )
        self.db.add(act)
        self.db.commit()

        # Set up dates so expected is 70% and actual is 45% (variance = -25 pp)
        # planned_start 7 days ago, planned_finish in 3 days -> 11 days total, 8 elapsed -> 72.7%
        act.planned_start = today - timedelta(days=7)
        act.planned_finish = today + timedelta(days=3)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="IN_PROGRESS",
            progress_percentage=40.0,
            actual_start=act.planned_start,
        )
        self.db.add(exec_obj)
        self.db.commit()

        risks = get_schedule_risks_data(self.db, self.project, self.planner)
        self.assertGreaterEqual(risks.total_at_risk, 1)
        self.assertIn(risks.items[0].risk_level, ["HIGH", "MEDIUM"])

    # TEST 9: Stale active activity -> risk reason identifies stale execution update
    def test_09_stale_active_activity_risk_reason(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-STALE-01",
            activity_name="Pump Station Piping",
            discipline="PIPING",
            planned_start=today - timedelta(days=10),
            planned_finish=today + timedelta(days=30),
        )
        self.db.add(act)
        self.db.commit()

        # Old execution timestamp 5 days ago (> 3 stale threshold)
        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="IN_PROGRESS",
            progress_percentage=20.0,
            actual_start=today - timedelta(days=10),
            last_updated_at=datetime.combine(today - timedelta(days=5), datetime.min.time()),
        )
        self.db.add(exec_obj)
        self.db.commit()

        risks = get_schedule_risks_data(self.db, self.project, self.planner)
        self.assertTrue(any("No execution updates for" in r for r in risks.items[0].risk_reasons))

    # TEST 10: Completed activity -> not treated as current overdue risk
    def test_10_completed_activity_not_in_current_risk(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-COMP-01",
            activity_name="Site Survey",
            discipline="CIVIL",
            planned_start=today - timedelta(days=30),
            planned_finish=today - timedelta(days=10),
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="COMPLETED",
            progress_percentage=100.0,
            actual_start=today - timedelta(days=30),
            actual_finish=today - timedelta(days=5),  # finished late but is COMPLETED
        )
        self.db.add(exec_obj)
        self.db.commit()

        risks = get_schedule_risks_data(self.db, self.project, self.planner)
        self.assertEqual(risks.total_at_risk, 0)
        self.assertEqual(len(risks.items), 0)

    # TEST 11: Completed late -> appears in completed variance metric
    def test_11_completed_late_appears_in_completed_metric(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-COMP-LATE",
            activity_name="Hydrotesting Segment A",
            discipline="PIPING",
            planned_start=today - timedelta(days=30),
            planned_finish=today - timedelta(days=15),
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="COMPLETED",
            progress_percentage=100.0,
            actual_start=today - timedelta(days=30),
            actual_finish=today - timedelta(days=10),  # 5 days late
        )
        self.db.add(exec_obj)
        self.db.commit()

        comp = get_completed_performance_data(self.db, self.project, self.planner)
        self.assertEqual(comp.total_completed, 1)
        self.assertEqual(comp.completed_late, 1)
        self.assertEqual(comp.completed_on_time_or_early, 0)
        self.assertEqual(comp.average_finish_variance_days, 5.0)

    # TEST 12: Progress history (20% on day 1, 40% on day 5, 60% on day 9) -> positive velocity and valid forecast
    def test_12_valid_progress_velocity_forecast(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-FCST-01",
            activity_name="Welding Pipeline Section 1",
            discipline="PIPING",
            planned_start=today - timedelta(days=10),
            planned_finish=today + timedelta(days=15),
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="IN_PROGRESS",
            progress_percentage=60.0,
            actual_start=today - timedelta(days=10),
        )
        self.db.add(exec_obj)
        self.db.commit()

        # Add 3 progress updates: day -8: 20%, day -4: 40%, day 0: 60%
        # Velocity = (60 - 20) / 8 = 5.0 pp / day
        # Remaining = 100 - 60 = 40 pp -> Remaining days = 40 / 5 = 8 days
        # Forecast finish = today + 8 days
        u1 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today - timedelta(days=8),
            progress_percentage=20.0,
        )
        u2 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today - timedelta(days=4),
            progress_percentage=40.0,
        )
        u3 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today,
            progress_percentage=60.0,
        )
        self.db.add_all([u1, u2, u3])
        self.db.commit()

        forecasts = get_activity_forecasts_data(self.db, self.project, self.planner)
        self.assertEqual(len(forecasts.forecasts), 1)
        f_item = forecasts.forecasts[0]
        self.assertEqual(f_item.forecast_status, "FORECASTED")
        self.assertEqual(f_item.data_quality, "GOOD")
        self.assertAlmostEqual(f_item.progress_rate_pp_per_day, 5.0, delta=0.1)
        self.assertEqual(f_item.indicative_finish, today + timedelta(days=8))

    # TEST 13: Only one progress observation -> INSUFFICIENT_DATA, no forecast date
    def test_13_single_observation_insufficient_data(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-FCST-02",
            activity_name="Cable Pulling",
            discipline="ELECTRICAL",
            planned_start=today - timedelta(days=3),
            planned_finish=today + timedelta(days=10),
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="IN_PROGRESS",
            progress_percentage=15.0,
            actual_start=today - timedelta(days=3),
        )
        self.db.add(exec_obj)
        self.db.commit()

        u1 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today,
            progress_percentage=15.0,
        )
        self.db.add(u1)
        self.db.commit()

        forecasts = get_activity_forecasts_data(self.db, self.project, self.planner)
        f_item = forecasts.forecasts[0]
        self.assertEqual(f_item.forecast_status, "INSUFFICIENT_DATA")
        self.assertEqual(f_item.data_quality, "INSUFFICIENT")
        self.assertIsNone(f_item.indicative_finish)

    # TEST 14: Zero/negative velocity -> no fake forecast
    def test_14_zero_or_negative_velocity_no_fake_forecast(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-FCST-03",
            activity_name="Equipment Foundation",
            discipline="CIVIL",
            planned_start=today - timedelta(days=10),
            planned_finish=today + timedelta(days=10),
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="IN_PROGRESS",
            progress_percentage=30.0,
            actual_start=today - timedelta(days=10),
        )
        self.db.add(exec_obj)
        self.db.commit()

        # Two updates with same 30% progress (zero velocity)
        u1 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today - timedelta(days=5),
            progress_percentage=30.0,
        )
        u2 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today,
            progress_percentage=30.0,
        )
        self.db.add_all([u1, u2])
        self.db.commit()

        forecasts = get_activity_forecasts_data(self.db, self.project, self.planner)
        f_item = forecasts.forecasts[0]
        self.assertEqual(f_item.forecast_status, "INSUFFICIENT_DATA")
        self.assertIsNone(f_item.indicative_finish)

    # TEST 15: ON_HOLD forecast -> forecast_status = ON_HOLD
    def test_15_on_hold_forecast_status(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-HOLD-02",
            activity_name="Pipeline Flange Assembly",
            discipline="PIPING",
            planned_start=today - timedelta(days=5),
            planned_finish=today + timedelta(days=15),
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="ON_HOLD",
            progress_percentage=45.0,
            actual_start=today - timedelta(days=5),
        )
        self.db.add(exec_obj)
        self.db.commit()

        forecasts = get_activity_forecasts_data(self.db, self.project, self.planner)
        f_item = forecasts.forecasts[0]
        self.assertEqual(f_item.forecast_status, "ON_HOLD")
        self.assertIsNone(f_item.indicative_finish)

    # TEST 16: NOT_STARTED activity -> no data-driven forecast
    def test_16_not_started_no_data_driven_forecast(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-NS-01",
            activity_name="Transformer Installation",
            discipline="ELECTRICAL",
            planned_start=today + timedelta(days=5),
            planned_finish=today + timedelta(days=20),
        )
        self.db.add(act)
        self.db.commit()

        forecasts = get_activity_forecasts_data(self.db, self.project, self.planner)
        f_item = forecasts.forecasts[0]
        self.assertEqual(f_item.forecast_status, "NOT_STARTED")
        self.assertIsNone(f_item.indicative_finish)

    # TEST 17: Unrealistic >365 day projection -> UNRELIABLE
    def test_17_unrealistic_long_projection_unreliable(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-SLOW-01",
            activity_name="Slow Boring Activity",
            discipline="CIVIL",
            planned_start=today - timedelta(days=100),
            planned_finish=today + timedelta(days=20),
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="IN_PROGRESS",
            progress_percentage=2.0,
            actual_start=today - timedelta(days=100),
        )
        self.db.add(exec_obj)
        self.db.commit()

        # 0.1 pp progress over 5 days -> 0.02 pp/day -> 98 pp remaining -> 4900 days (> 365)
        u1 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today - timedelta(days=5),
            progress_percentage=1.9,
        )
        u2 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today,
            progress_percentage=2.0,
        )
        self.db.add_all([u1, u2])
        self.db.commit()

        forecasts = get_activity_forecasts_data(self.db, self.project, self.planner)
        f_item = forecasts.forecasts[0]
        self.assertEqual(f_item.forecast_status, "UNRELIABLE")
        self.assertIsNone(f_item.indicative_finish)

    # TEST 18: Trend reconstruction: historical dates use latest progress known AS OF that date
    def test_18_historical_trend_reconstruction_accuracy(self):
        today = get_today_date()
        act = Activity(
            project_id=self.project.id,
            activity_code="ACT-TREND-01",
            activity_name="Main Pipeline Trench",
            discipline="PIPING",
            planned_start=today - timedelta(days=20),
            planned_finish=today + timedelta(days=10),
        )
        self.db.add(act)
        self.db.commit()

        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=act.id,
            execution_status="IN_PROGRESS",
            progress_percentage=80.0,
            actual_start=today - timedelta(days=20),
        )
        self.db.add(exec_obj)
        self.db.commit()

        # Updates reported at different historical points:
        # Day -10: 25%
        # Day -5: 50%
        # Day 0 (today): 80%
        u1 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today - timedelta(days=10),
            progress_percentage=25.0,
        )
        u2 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today - timedelta(days=5),
            progress_percentage=50.0,
        )
        u3 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=act.id,
            reported_by_id=self.planner.id,
            update_type="PROGRESS",
            reported_date=today,
            progress_percentage=80.0,
        )
        self.db.add_all([u1, u2, u3])
        self.db.commit()

        trend = get_progress_trend_data(self.db, self.project, self.planner, range_key="30d")
        points_map = {p.date: p.actual_progress for p in trend.trend_points}

        # Date -15 (before any updates) -> 0.0%
        d_before = (today - timedelta(days=15)).isoformat()
        if d_before in points_map:
            self.assertEqual(points_map[d_before], 0.0)

        # Date -8 (after day -10 update) -> 25.0%
        d_mid1 = (today - timedelta(days=8)).isoformat()
        self.assertEqual(points_map[d_mid1], 25.0)

        # Date -3 (after day -5 update) -> 50.0%
        d_mid2 = (today - timedelta(days=3)).isoformat()
        self.assertEqual(points_map[d_mid2], 50.0)

        # Today -> 80.0%
        self.assertEqual(points_map[today.isoformat()], 80.0)

    # TEST 19: Planner analytics sees all project disciplines
    def test_19_planner_sees_all_disciplines(self):
        act_civ = Activity(
            project_id=self.project.id,
            activity_code="CIV-101",
            activity_name="Civil Foundation",
            discipline="CIVIL",
            planned_start=date(2026, 1, 1),
            planned_finish=date(2026, 6, 1),
        )
        act_pip = Activity(
            project_id=self.project.id,
            activity_code="PIP-101",
            activity_name="Piping Header",
            discipline="PIPING",
            planned_start=date(2026, 1, 1),
            planned_finish=date(2026, 6, 1),
        )
        self.db.add_all([act_civ, act_pip])
        self.db.commit()

        resp = self.client.get(
            f"/api/projects/{self.project.id}/analytics/disciplines",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        disciplines = [d["discipline"] for d in data["disciplines"]]
        self.assertIn("CIVIL", disciplines)
        self.assertIn("PIPING", disciplines)

    # TEST 20: Supervisor analytics sees assigned discipline only
    def test_20_supervisor_sees_assigned_discipline_only(self):
        act_civ = Activity(
            project_id=self.project.id,
            activity_code="CIV-102",
            activity_name="Civil Foundation 2",
            discipline="CIVIL",
            planned_start=date(2026, 1, 1),
            planned_finish=date(2026, 6, 1),
        )
        act_pip = Activity(
            project_id=self.project.id,
            activity_code="PIP-102",
            activity_name="Piping Header 2",
            discipline="PIPING",
            planned_start=date(2026, 1, 1),
            planned_finish=date(2026, 6, 1),
        )
        self.db.add_all([act_civ, act_pip])
        self.db.commit()

        resp = self.client.get(
            f"/api/projects/{self.project.id}/analytics/disciplines",
            headers={"Authorization": f"Bearer {self.civil_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        disciplines = [d["discipline"] for d in data["disciplines"]]
        self.assertEqual(disciplines, ["CIVIL"])

    # TEST 21: Supervisor attempts unauthorized discipline query -> 403 Forbidden
    def test_21_supervisor_unauthorized_discipline_rejected(self):
        resp = self.client.get(
            f"/api/projects/{self.project.id}/analytics/risks?discipline=PIPING",
            headers={"Authorization": f"Bearer {self.civil_token}"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Supervisors cannot query analytics outside their assigned discipline", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()

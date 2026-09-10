import unittest
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.main import app
from app.core.security import hash_password, create_access_token
from app.core.datetime_utils import get_today_date, get_yesterday_date, get_last_week_range, get_last_7_days_range
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.planner_review_case import PlannerReviewCase
from app.models.progress_report_import import ProgressReportImport
from app.models.progress_report_item import ProgressReportItem
from app.services.project_memory_service import ProjectMemoryService

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


class Phase14ProjectMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.core.config import settings
        cls._orig_key = settings.GEMINI_API_KEY
        settings.GEMINI_API_KEY = ""
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from app.core.config import settings
        settings.GEMINI_API_KEY = cls._orig_key
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        self.db = TestingSessionLocal()

        # Clear tables
        self.db.query(PlannerReviewCase).delete()
        self.db.query(ProgressReportItem).delete()
        self.db.query(ProgressReportImport).delete()
        self.db.query(ProgressUpdate).delete()
        self.db.query(ActivityExecution).delete()
        self.db.query(Activity).delete()
        self.db.query(ProjectMember).delete()
        self.db.query(Project).delete()
        self.db.query(User).delete()
        self.db.commit()

        # Create Users
        self.planner = User(
            email="lead.planner@project.org",
            hashed_password=hash_password("PlannerPass123!"),
            full_name="Lead Project Planner",
            role="PLANNER",
            is_active=True,
        )
        self.sup_civil = User(
            email="civil.sup@project.org",
            hashed_password=hash_password("SupervisorPass123!"),
            full_name="Luffy Civil Sup",
            role="SUPERVISOR",
            is_active=True,
        )
        self.sup_piping = User(
            email="piping.sup@project.org",
            hashed_password=hash_password("SupervisorPass123!"),
            full_name="Zoro Piping Sup",
            role="SUPERVISOR",
            is_active=True,
        )
        self.unassigned_user = User(
            email="outsider@project.org",
            hashed_password=hash_password("OutsiderPass123!"),
            full_name="Outsider User",
            role="SUPERVISOR",
            is_active=True,
        )
        self.db.add_all([self.planner, self.sup_civil, self.sup_piping, self.unassigned_user])
        self.db.commit()

        # Create Project
        today = get_today_date()
        self.project = Project(
            project_code="OIL-FAC-001",
            name="Oil Processing Facility Expansion",
            description="L5/L6 Infrastructure Project",
            location="Industrial Complex Sector 4",
            planned_start_date=today - timedelta(days=30),
            planned_end_date=today + timedelta(days=60),
            status="ACTIVE",
            created_by_id=self.planner.id,
        )
        self.db.add(self.project)
        self.db.commit()

        # Project Memberships
        self.pm_civil = ProjectMember(project_id=self.project.id, user_id=self.sup_civil.id, discipline="CIVIL")
        self.pm_piping = ProjectMember(project_id=self.project.id, user_id=self.sup_piping.id, discipline="PIPING")
        self.db.add_all([self.pm_civil, self.pm_piping])
        self.db.commit()

        # Create Activities
        today = get_today_date()
        self.act_civ101 = Activity(
            project_id=self.project.id,
            activity_code="CIV-101",
            activity_name="Pump House Excavation",
            discipline="CIVIL",
            planned_start=today - timedelta(days=20),
            planned_finish=today - timedelta(days=10),
            planned_duration=10.0,
        )
        self.act_civ102 = Activity(
            project_id=self.project.id,
            activity_code="CIV-102",
            activity_name="Foundation Reinforcement",
            discipline="CIVIL",
            planned_start=today - timedelta(days=10),
            planned_finish=today - timedelta(days=2),
            planned_duration=8.0,
        )
        self.act_civ103 = Activity(
            project_id=self.project.id,
            activity_code="CIV-103",
            activity_name="Foundation Concreting",
            discipline="CIVIL",
            planned_start=today - timedelta(days=2),
            planned_finish=today + timedelta(days=5),
            planned_duration=7.0,
        )
        self.act_pip201 = Activity(
            project_id=self.project.id,
            activity_code="PIP-201",
            activity_name="Pipeline Fabrication",
            discipline="PIPING",
            planned_start=today - timedelta(days=15),
            planned_finish=today - timedelta(days=5),
            planned_duration=10.0,
        )
        self.db.add_all([self.act_civ101, self.act_civ102, self.act_civ103, self.act_pip201])
        self.db.commit()

        # Create Executions
        self.exec_civ101 = ActivityExecution(
            project_id=self.project.id,
            activity_id=self.act_civ101.id,
            actual_start=today - timedelta(days=20),
            actual_finish=today - timedelta(days=7),  # Completed 3 days late (planned finish was -10)
            progress_percentage=100.0,
            execution_status="COMPLETED",
        )
        self.exec_civ102 = ActivityExecution(
            project_id=self.project.id,
            activity_id=self.act_civ102.id,
            actual_start=today - timedelta(days=10),
            progress_percentage=60.0,
            execution_status="IN_PROGRESS",  # Overdue (planned finish was -2)
        )
        self.exec_civ103 = ActivityExecution(
            project_id=self.project.id,
            activity_id=self.act_civ103.id,
            actual_start=today - timedelta(days=1),
            progress_percentage=20.0,
            execution_status="IN_PROGRESS",
        )
        self.exec_pip201 = ActivityExecution(
            project_id=self.project.id,
            activity_id=self.act_pip201.id,
            actual_start=today - timedelta(days=15),
            actual_finish=today - timedelta(days=1),  # Completed 4 days late (planned finish was -5)
            progress_percentage=100.0,
            execution_status="COMPLETED",
        )
        self.db.add_all([self.exec_civ101, self.exec_civ102, self.exec_civ103, self.exec_pip201])
        self.db.commit()

        # Create ProgressUpdates (Audit trail)
        # CIV-101: START -> COMPLETE (No remarks recorded)
        u1 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=self.act_civ101.id,
            reported_by_id=self.sup_civil.id,
            update_type="START",
            reported_date=today - timedelta(days=20),
            progress_percentage=0.0,
            source_type="MANUAL",
            created_at=datetime.now(timezone.utc) - timedelta(days=20),
        )
        u2 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=self.act_civ101.id,
            reported_by_id=self.sup_civil.id,
            update_type="COMPLETE",
            reported_date=today - timedelta(days=7),
            progress_percentage=100.0,
            source_type="MANUAL",
            created_at=datetime.now(timezone.utc) - timedelta(days=7),
        )
        # CIV-103: START -> PROGRESS
        u3 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=self.act_civ103.id,
            reported_by_id=self.sup_civil.id,
            update_type="START",
            reported_date=today - timedelta(days=1),
            progress_percentage=10.0,
            remarks="Pouring initial foundation concrete in Zone 1",
            source_type="AI_CHAT",
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        # PIP-201: START -> ON_HOLD -> RESUME -> COMPLETE
        u4 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=self.act_pip201.id,
            reported_by_id=self.sup_piping.id,
            update_type="START",
            reported_date=today - timedelta(days=15),
            progress_percentage=10.0,
            source_type="MANUAL",
            created_at=datetime.now(timezone.utc) - timedelta(days=15),
        )
        u5 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=self.act_pip201.id,
            reported_by_id=self.sup_piping.id,
            update_type="ON_HOLD",
            reported_date=today - timedelta(days=10),
            progress_percentage=30.0,
            remarks="Awaiting material clearance from warehouse",
            source_type="REPORT_IMPORT",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        u6 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=self.act_pip201.id,
            reported_by_id=self.sup_piping.id,
            update_type="RESUME",
            reported_date=today - timedelta(days=8),
            progress_percentage=30.0,
            remarks="Material cleared and delivered to site",
            source_type="REPORT_IMPORT",
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
        u7 = ProgressUpdate(
            project_id=self.project.id,
            activity_id=self.act_pip201.id,
            reported_by_id=self.sup_piping.id,
            update_type="COMPLETE",
            reported_date=today - timedelta(days=1),
            progress_percentage=100.0,
            source_type="REPORT_IMPORT",
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        self.db.add_all([u1, u2, u3, u4, u5, u6, u7])
        self.db.commit()

        # Auth tokens
        self.planner_token = create_access_token(self.planner.id)
        self.civil_token = create_access_token(self.sup_civil.id)
        self.piping_token = create_access_token(self.sup_piping.id)
        self.outsider_token = create_access_token(self.unassigned_user.id)

    def tearDown(self):
        self.db.close()

    def test_01_planner_project_history(self):
        """TEST 1: Planner requests Project Memory and sees all authorized project disciplines."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/memory/summary",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_execution_updates"], 7)
        self.assertEqual(data["activities_with_history"], 3)
        self.assertEqual(data["scope"], "Project-wide")

        # Get events
        ev_res = self.client.get(
            f"/api/projects/{self.project.id}/memory/events",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(ev_res.status_code, 200)
        ev_data = ev_res.json()
        self.assertEqual(ev_data["total"], 7)
        disciplines = {e["discipline"] for e in ev_data["events"]}
        self.assertIn("CIVIL", disciplines)
        self.assertIn("PIPING", disciplines)

    def test_02_supervisor_scoping(self):
        """TEST 2: CIVIL supervisor requests Project Memory and sees ONLY CIVIL activity history."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/memory/summary",
            headers={"Authorization": f"Bearer {self.civil_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_execution_updates"], 3)  # Only the 3 CIVIL updates
        self.assertEqual(data["activities_with_history"], 2)  # CIV-101 and CIV-103
        self.assertEqual(data["scope"], "Discipline: CIVIL")

        ev_res = self.client.get(
            f"/api/projects/{self.project.id}/memory/events",
            headers={"Authorization": f"Bearer {self.civil_token}"},
        )
        self.assertEqual(ev_res.status_code, 200)
        ev_data = ev_res.json()
        self.assertEqual(ev_data["total"], 3)
        for e in ev_data["events"]:
            self.assertEqual(e["discipline"], "CIVIL")
            self.assertNotEqual(e["discipline"], "PIPING")

        # Attempt to access PIP-201 timeline as Civil supervisor -> 403 Forbidden
        timeline_res = self.client.get(
            f"/api/projects/{self.project.id}/memory/activities/PIP-201/timeline",
            headers={"Authorization": f"Bearer {self.civil_token}"},
        )
        self.assertEqual(timeline_res.status_code, 403)

    def test_03_cross_project_security(self):
        """TEST 3: User requests an unauthorized project ID -> 403 Forbidden."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/memory/summary",
            headers={"Authorization": f"Bearer {self.outsider_token}"},
        )
        self.assertEqual(res.status_code, 403)

    def test_04_activity_timeline(self):
        """TEST 4: CIV-101 timeline returns events ordered chronologically (oldest -> newest)."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/memory/activities/CIV-101/timeline",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["activity"]["activity_code"], "CIV-101")
        self.assertEqual(data["activity"]["current_status"], "COMPLETED")
        self.assertEqual(data["total_events"], 2)

        events = data["events"]
        self.assertEqual(events[0]["update_type"], "START")
        self.assertEqual(events[1]["update_type"], "COMPLETE")
        self.assertTrue(events[0]["event_date"] <= events[1]["event_date"])

    def test_05_delay_calculation_completed_late(self):
        """TEST 5: Completed activity with actual_finish after planned_finish -> COMPLETED_LATE with exact late_days."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/memory/activities/CIV-101/delay-analysis",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["state"], "COMPLETED_LATE")
        self.assertEqual(data["late_days"], 3)  # Planned -10, Finished -7 -> 3 days late

    def test_06_delay_calculation_currently_overdue(self):
        """TEST 6: Incomplete activity where today > planned_finish -> CURRENTLY_OVERDUE with exact late_days."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/memory/activities/CIV-102/delay-analysis",
            headers={"Authorization": f"Bearer {self.civil_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["state"], "CURRENTLY_OVERDUE")
        self.assertEqual(data["late_days"], 2)  # Planned finish was 2 days ago

    def test_07_no_invented_reason(self):
        """TEST 7: Late activity without recorded remarks/reasons -> states delay and no explicit reason recorded."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/memory/activities/CIV-101/delay-analysis",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("no explicit reason for the delay was recorded", data["summary"])
        self.assertEqual(len(data["recorded_notes"]), 0)

    def test_08_recorded_reason_cited(self):
        """TEST 8: Late activity with recorded ON_HOLD remark -> cites recorded note only."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/memory/activities/PIP-201/delay-analysis",
            headers={"Authorization": f"Bearer {self.piping_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["state"], "COMPLETED_LATE")
        self.assertEqual(data["late_days"], 4)
        self.assertIn("Awaiting material clearance from warehouse", data["recorded_notes"])
        self.assertIn("Awaiting material clearance from warehouse", data["summary"])

    def test_09_discipline_history(self):
        """TEST 9: Query discipline history tool -> returns correct discipline records and evidence."""
        res = ProjectMemoryService.get_project_events(
            db=self.db,
            project_id=self.project.id,
            user_role="PLANNER",
            discipline="CIVIL",
        )
        self.assertEqual(res.total, 3)
        for e in res.events:
            self.assertEqual(e.discipline, "CIVIL")

    def test_10_search_activity_name(self):
        """TEST 10: Search 'Foundation Concreting' -> finds CIV-103 historical records."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/memory/events?q=Foundation Concreting",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(data["total"], 1)
        self.assertEqual(data["events"][0]["activity_code"], "CIV-103")

    def test_11_code_normalization(self):
        """TEST 11: Query with un-hyphenated code 'CIV 103' -> resolves CIV-103."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/memory/activities/CIV 103/timeline",
            headers={"Authorization": f"Bearer {self.civil_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["activity"]["activity_code"], "CIV-103")

    def test_12_project_ai_regression(self):
        """TEST 12: Existing operational AI queries still function seamlessly."""
        res = self.client.post(
            f"/api/projects/{self.project.id}/ai/chat",
            json={"prompt": "What activities are overdue?"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("Overdue Activities", data["assistant_message"]["content"])

    def test_13_general_question_rejection(self):
        """TEST 13: General question rejection behavior preserved."""
        res = self.client.post(
            f"/api/projects/{self.project.id}/ai/chat",
            json={"prompt": "What is the capital of France?"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("I can only assist with information related to the currently selected infrastructure project", data["assistant_message"]["content"])

    def test_14_read_only_safety(self):
        """TEST 14: Historical queries must not modify execution or baseline database tables."""
        initial_updates_count = self.db.query(ProgressUpdate).count()
        initial_exec_count = self.db.query(ActivityExecution).count()

        # Run history queries
        self.client.get(f"/api/projects/{self.project.id}/memory/summary", headers={"Authorization": f"Bearer {self.planner_token}"})
        self.client.get(f"/api/projects/{self.project.id}/memory/events", headers={"Authorization": f"Bearer {self.planner_token}"})
        self.client.get(f"/api/projects/{self.project.id}/memory/activities/CIV-101/timeline", headers={"Authorization": f"Bearer {self.planner_token}"})
        self.client.get(f"/api/projects/{self.project.id}/memory/activities/CIV-101/delay-analysis", headers={"Authorization": f"Bearer {self.planner_token}"})
        self.client.post(f"/api/projects/{self.project.id}/ai/chat", json={"prompt": "Why was CIV-101 delayed?"}, headers={"Authorization": f"Bearer {self.planner_token}"})

        final_updates_count = self.db.query(ProgressUpdate).count()
        final_exec_count = self.db.query(ActivityExecution).count()

        self.assertEqual(initial_updates_count, final_updates_count)
        self.assertEqual(initial_exec_count, final_exec_count)


if __name__ == "__main__":
    unittest.main()

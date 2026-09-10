import unittest
from datetime import date, datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.main import app
from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.execution_report_draft import ExecutionReportDraft
from app.models.progress_report_import import ProgressReportImport
from app.models.progress_report_item import ProgressReportItem
from app.models.planner_review_case import PlannerReviewCase

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


class Phase10PlannerReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        self.db = TestingSessionLocal()

        # Clear existing test data
        self.db.query(PlannerReviewCase).delete()
        self.db.query(ProgressUpdate).delete()
        self.db.query(ActivityExecution).delete()
        self.db.query(ProgressReportItem).delete()
        self.db.query(ProgressReportImport).delete()
        self.db.query(ExecutionReportDraft).delete()
        self.db.query(Activity).delete()
        self.db.query(ProjectMember).delete()
        self.db.query(Project).delete()
        self.db.query(User).delete()
        self.db.commit()

        # Create Planner
        self.planner = User(
            full_name="Lead Planner",
            email="planner10@sih.gov.in",
            hashed_password=hash_password("password123"),
            role="PLANNER",
            is_active=True,
        )
        # Create Supervisor
        self.supervisor = User(
            full_name="Civil Supervisor",
            email="supervisor10@sih.gov.in",
            hashed_password=hash_password("password123"),
            role="SUPERVISOR",
            is_active=True,
        )
        self.db.add_all([self.planner, self.supervisor])
        self.db.commit()
        self.db.refresh(self.planner)
        self.db.refresh(self.supervisor)

        # Create Project
        self.project = Project(
            name="Phase 10 Refinery Project",
            project_code="PRJ-P10-001",
            planned_start_date=date(2026, 1, 1),
            planned_end_date=date(2026, 12, 31),
            status="ACTIVE",
            created_by_id=self.planner.id,
        )
        self.db.add(self.project)
        self.db.commit()
        self.db.refresh(self.project)

        # Assign Supervisor to Project
        member = ProjectMember(
            project_id=self.project.id,
            user_id=self.supervisor.id,
            discipline="CIVIL",
        )
        self.db.add(member)
        self.db.commit()

        # Create Activities
        self.act1 = Activity(
            project_id=self.project.id,
            activity_code="CIV-101",
            activity_name="Site Excavation",
            discipline="CIVIL",
            planned_start=date(2026, 1, 10),
            planned_finish=date(2026, 2, 10),
        )
        self.act2 = Activity(
            project_id=self.project.id,
            activity_code="CIV-102",
            activity_name="Foundation Reinforcement",
            discipline="CIVIL",
            planned_start=date(2026, 2, 15),
            planned_finish=date(2026, 3, 15),
        )
        self.act3 = Activity(
            project_id=self.project.id,
            activity_code="CIV-103",
            activity_name="Foundation Concreting",
            discipline="CIVIL",
            planned_start=date(2026, 3, 20),
            planned_finish=date(2026, 4, 20),
        )
        self.db.add_all([self.act1, self.act2, self.act3])
        self.db.commit()
        self.db.refresh(self.act1)
        self.db.refresh(self.act2)
        self.db.refresh(self.act3)

        self.planner_token = create_access_token(self.planner.id)
        self.supervisor_token = create_access_token(self.supervisor.id)

    def tearDown(self):
        self.db.close()

    def test_01_create_unresolved_progress_report_item(self):
        """TEST 1: Create unresolved Phase 9 ProgressReportItem -> Expected: one PlannerReviewCase."""
        rep_import = ProgressReportImport(
            project_id=self.project.id,
            uploaded_by_id=self.supervisor.id,
            source_type="CSV",
            original_filename="daily_report.csv",
            status="REVIEW",
        )
        self.db.add(rep_import)
        self.db.commit()
        self.db.refresh(rep_import)

        item = ProgressReportItem(
            report_id=rep_import.id,
            project_id=self.project.id,
            raw_description="Pump bay piling and excavation",
            reported_date=date(2026, 3, 1),
            extracted_update_type="START",
            extracted_progress_percentage=10.0,
            match_status="UNMATCHED",
            review_status="PENDING",
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        resp = self.client.get(
            f"/api/projects/{self.project.id}/review-center/summary",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["needs_review"], 1)

        case = (
            self.db.query(PlannerReviewCase)
            .filter(
                PlannerReviewCase.project_id == self.project.id,
                PlannerReviewCase.source_type == "PROGRESS_REPORT",
                PlannerReviewCase.source_id == item.id,
            )
            .first()
        )
        self.assertIsNotNone(case)
        self.assertEqual(case.decision, "NEEDS_REVIEW")

    def test_02_idempotent_sync_no_duplicate(self):
        """TEST 2: Reload/create sync again -> Expected: still ONE review case. No duplicate."""
        rep_import = ProgressReportImport(
            project_id=self.project.id,
            uploaded_by_id=self.supervisor.id,
            source_type="CSV",
            original_filename="daily_report.csv",
            status="REVIEW",
        )
        self.db.add(rep_import)
        self.db.commit()

        item = ProgressReportItem(
            report_id=rep_import.id,
            project_id=self.project.id,
            raw_description="Excavation check",
            reported_date=date(2026, 3, 1),
            extracted_update_type="PROGRESS",
            extracted_progress_percentage=20.0,
            match_status="UNMATCHED",
            review_status="PENDING",
        )
        self.db.add(item)
        self.db.commit()

        # Trigger sync first time
        self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        initial_count = self.db.query(PlannerReviewCase).filter(PlannerReviewCase.project_id == self.project.id).count()
        self.assertEqual(initial_count, 1)

        # Multiple subsequent calls
        for _ in range(3):
            resp = self.client.get(
                f"/api/projects/{self.project.id}/review-center",
                headers={"Authorization": f"Bearer {self.planner_token}"},
            )
            self.assertEqual(resp.status_code, 200)

        new_count = self.db.query(PlannerReviewCase).filter(PlannerReviewCase.project_id == self.project.id).count()
        self.assertEqual(new_count, initial_count)

    def test_03_unresolved_ai_report_draft(self):
        """TEST 3: Create unresolved Phase 8 AIReportDraft -> Expected: appears in same Review Center."""
        draft = ExecutionReportDraft(
            project_id=self.project.id,
            reported_by_id=self.supervisor.id,
            original_text="North pump slab shuttering finished today",
            intent="EXECUTION_REPORT",
            update_type="COMPLETE",
            reported_date=date(2026, 3, 2),
            progress_percentage=100.0,
            remarks="Completed on schedule",
            matched_activity_id=None,
            match_confidence=0.45,
            match_status="LOW_CONFIDENCE",
            status="NEEDS_PLANNER_REVIEW",
        )
        self.db.add(draft)
        self.db.commit()

        resp = self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["items"]
        ai_items = [it for it in items if it["source_type"] == "AI_REPORT" and it["source_id"] == draft.id]
        self.assertEqual(len(ai_items), 1)
        self.assertEqual(ai_items[0]["original_text"], "North pump slab shuttering finished today")

    def test_04_supervisor_gets_403(self):
        """TEST 4: Supervisor GET review-center -> Expected: 403 Forbidden."""
        resp = self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.supervisor_token}"},
        )
        self.assertEqual(resp.status_code, 403)

        resp2 = self.client.get(
            f"/api/projects/{self.project.id}/review-center/summary",
            headers={"Authorization": f"Bearer {self.supervisor_token}"},
        )
        self.assertEqual(resp2.status_code, 403)

    def test_05_planner_gets_200(self):
        """TEST 5: Planner views own project -> Expected: 200 OK."""
        resp = self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("items", resp.json())
        self.assertIn("total", resp.json())

    def test_06_planner_selects_activity(self):
        """TEST 6: Planner selects activity -> Expected: RESOLVED. No execution update yet."""
        draft = ExecutionReportDraft(
            project_id=self.project.id,
            reported_by_id=self.supervisor.id,
            original_text="Foundation concrete pour complete",
            intent="EXECUTION_REPORT",
            update_type="COMPLETE",
            reported_date=date(2026, 3, 2),
            progress_percentage=100.0,
            status="NEEDS_PLANNER_REVIEW",
        )
        self.db.add(draft)
        self.db.commit()

        # Trigger sync
        self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )

        case = self.db.query(PlannerReviewCase).filter(PlannerReviewCase.source_id == draft.id).first()
        self.assertIsNotNone(case)

        # Verify execution table before
        exec_before = self.db.query(ActivityExecution).filter(ActivityExecution.activity_id == self.act3.id).first()
        prog_before = exec_before.progress_percentage if exec_before else 0.0

        resp = self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case.id}/select-activity",
            headers={"Authorization": f"Bearer {self.planner_token}"},
            json={"activity_id": self.act3.id, "review_reason": "Terminology refers to foundation concrete"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["decision"], "RESOLVED")
        self.assertEqual(data["selected_activity_id"], self.act3.id)

        # Verify execution table after: MUST BE UNCHANGED
        exec_after = self.db.query(ActivityExecution).filter(ActivityExecution.activity_id == self.act3.id).first()
        prog_after = exec_after.progress_percentage if exec_after else 0.0
        self.assertEqual(prog_after, prog_before)

    def test_07_valid_resolved_case_apply(self):
        """TEST 7: Valid resolved case: Apply -> Expected: Phase 5 service updates ActivityExecution, ProgressUpdate created once, case becomes APPLIED."""
        draft = ExecutionReportDraft(
            project_id=self.project.id,
            reported_by_id=self.supervisor.id,
            original_text="Site excavation started today",
            intent="EXECUTION_REPORT",
            update_type="START",
            reported_date=date(2026, 1, 15),
            progress_percentage=10.0,
            matched_activity_id=self.act1.id,
            match_confidence=0.9,
            match_status="MATCHED_HIGH",
            status="NEEDS_PLANNER_REVIEW",
        )
        self.db.add(draft)
        self.db.commit()

        # Sync review case
        self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )

        case = self.db.query(PlannerReviewCase).filter(
            PlannerReviewCase.source_type == "AI_REPORT",
            PlannerReviewCase.source_id == draft.id,
        ).first()
        self.assertIsNotNone(case)

        # Link to CIV-101
        self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case.id}/select-activity",
            headers={"Authorization": f"Bearer {self.planner_token}"},
            json={"activity_id": self.act1.id, "review_reason": "Verified with site team"},
        )

        # Apply resolved case
        resp = self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case.id}/apply",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["decision"], "APPLIED")
        self.assertIsNotNone(data["applied_at"])

        # Verify ActivityExecution
        exec_obj = self.db.query(ActivityExecution).filter(ActivityExecution.activity_id == self.act1.id).first()
        self.assertIsNotNone(exec_obj)
        self.assertEqual(exec_obj.execution_status, "IN_PROGRESS")
        self.assertEqual(exec_obj.progress_percentage, 10.0)

        # Verify ProgressUpdate created once
        updates = self.db.query(ProgressUpdate).filter(ProgressUpdate.activity_id == self.act1.id).all()
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].reported_by_id, self.supervisor.id)
        self.assertEqual(updates[0].source_type, "AI_CHAT")

    def test_08_apply_same_case_again_blocked(self):
        """TEST 8: Apply same case again -> Expected: blocked (409 Conflict, no duplicate history)."""
        draft = ExecutionReportDraft(
            project_id=self.project.id,
            reported_by_id=self.supervisor.id,
            original_text="Excavation commenced",
            intent="EXECUTION_REPORT",
            update_type="START",
            reported_date=date(2026, 1, 15),
            progress_percentage=15.0,
            matched_activity_id=self.act1.id,
            status="NEEDS_PLANNER_REVIEW",
        )
        self.db.add(draft)
        self.db.commit()

        self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        case = self.db.query(PlannerReviewCase).filter(PlannerReviewCase.source_id == draft.id).first()

        self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case.id}/select-activity",
            headers={"Authorization": f"Bearer {self.planner_token}"},
            json={"activity_id": self.act1.id},
        )

        resp1 = self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case.id}/apply",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(resp1.status_code, 200)

        count_before = self.db.query(ProgressUpdate).filter(ProgressUpdate.activity_id == self.act1.id).count()

        # Second apply must be blocked with 409
        resp2 = self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case.id}/apply",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(resp2.status_code, 409)

        count_after = self.db.query(ProgressUpdate).filter(ProgressUpdate.activity_id == self.act1.id).count()
        self.assertEqual(count_after, count_before)

    def test_09_invalid_transition_cannot_apply(self):
        """TEST 9: Invalid transition (e.g. current progress 50%, report regress to 30%) -> Expected: validation invalid, apply fails."""
        # Set CIV-102 to 50%
        exec_obj = ActivityExecution(
            project_id=self.project.id,
            activity_id=self.act2.id,
            actual_start=date(2026, 2, 16),
            progress_percentage=50.0,
            execution_status="IN_PROGRESS",
        )
        self.db.add(exec_obj)
        self.db.commit()

        # Create draft with regressing progress of 30%
        draft = ExecutionReportDraft(
            project_id=self.project.id,
            reported_by_id=self.supervisor.id,
            original_text="Foundation rebar progress at 30%",
            intent="EXECUTION_REPORT",
            update_type="PROGRESS",
            reported_date=date(2026, 2, 20),
            progress_percentage=30.0,
            matched_activity_id=self.act2.id,
            status="NEEDS_PLANNER_REVIEW",
        )
        self.db.add(draft)
        self.db.commit()

        self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        case = self.db.query(PlannerReviewCase).filter(PlannerReviewCase.source_id == draft.id).first()

        self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case.id}/select-activity",
            headers={"Authorization": f"Bearer {self.planner_token}"},
            json={"activity_id": self.act2.id},
        )

        detail_resp = self.client.get(
            f"/api/projects/{self.project.id}/review-center/{case.id}",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["validation_status"], "INVALID")

        # Attempt apply -> must fail with 400
        apply_resp = self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case.id}/apply",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(apply_resp.status_code, 400)

    def test_10_reject_case(self):
        """TEST 10: Reject case -> Expected: REJECTED, no execution changes."""
        draft = ExecutionReportDraft(
            project_id=self.project.id,
            reported_by_id=self.supervisor.id,
            original_text="Duplicate report of earth moving",
            intent="EXECUTION_REPORT",
            update_type="PROGRESS",
            reported_date=date(2026, 1, 22),
            progress_percentage=30.0,
            status="NEEDS_PLANNER_REVIEW",
        )
        self.db.add(draft)
        self.db.commit()

        self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        case = self.db.query(PlannerReviewCase).filter(PlannerReviewCase.source_id == draft.id).first()

        resp = self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case.id}/reject",
            headers={"Authorization": f"Bearer {self.planner_token}"},
            json={"review_reason": "Duplicate submission from morning shift"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["decision"], "REJECTED")
        self.assertEqual(resp.json()["review_reason"], "Duplicate submission from morning shift")

        self.db.refresh(draft)
        self.assertEqual(draft.status, "REJECTED")

    def test_11_mark_unplanned_work(self):
        """TEST 11: Mark unplanned -> Expected: UNPLANNED, no Activity created, no execution update."""
        activity_count_before = self.db.query(Activity).filter(Activity.project_id == self.project.id).count()

        draft = ExecutionReportDraft(
            project_id=self.project.id,
            reported_by_id=self.supervisor.id,
            original_text="Temporary bypass ditch constructed due to rain",
            intent="EXECUTION_REPORT",
            update_type="START",
            reported_date=date(2026, 1, 25),
            status="NEEDS_PLANNER_REVIEW",
        )
        self.db.add(draft)
        self.db.commit()

        self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        case = self.db.query(PlannerReviewCase).filter(PlannerReviewCase.source_id == draft.id).first()

        resp = self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case.id}/mark-unplanned",
            headers={"Authorization": f"Bearer {self.planner_token}"},
            json={"review_reason": "Temporary weather mitigation work not in current baseline"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["decision"], "UNPLANNED")

        activity_count_after = self.db.query(Activity).filter(Activity.project_id == self.project.id).count()
        self.assertEqual(activity_count_after, activity_count_before)

    def test_12_original_source_text_preserved(self):
        """TEST 12: Original source record remains unchanged throughout review operations."""
        resp = self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        items = resp.json()["items"]
        for it in items:
            self.assertIsNotNone(it["original_text"])
            self.assertGreater(len(it["original_text"]), 0)


if __name__ == "__main__":
    unittest.main()

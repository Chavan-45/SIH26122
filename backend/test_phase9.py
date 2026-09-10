import unittest
import io
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import pandas as pd

from app.database.database import Base, get_db
from app.main import app
from app.core.dependencies import get_current_user
from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.progress_report_import import ProgressReportImport
from app.models.progress_report_item import ProgressReportItem


class TestPhase9BatchReportIngestion(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()

        # Seed test users
        self.planner = User(
            full_name="Planner User",
            email="planner9@example.com",
            hashed_password=hash_password("password123"),
            role="PLANNER",
        )
        self.piping_supervisor = User(
            full_name="Piping Supervisor",
            email="piping9@example.com",
            hashed_password=hash_password("password123"),
            role="SUPERVISOR",
        )
        self.civil_supervisor = User(
            full_name="Civil Supervisor",
            email="civil9@example.com",
            hashed_password=hash_password("password123"),
            role="SUPERVISOR",
        )
        self.db.add_all([self.planner, self.piping_supervisor, self.civil_supervisor])
        self.db.commit()

        # Seed test project
        self.project = Project(
            name="Pipeline Expansion Phase 9",
            project_code="PRJ-PH9-01",
            planned_start_date=date(2026, 1, 1),
            planned_end_date=date(2026, 12, 31),
            status="ACTIVE",
            created_by_id=self.planner.id,
        )
        self.db.add(self.project)
        self.db.commit()

        # Assign project members
        m2 = ProjectMember(project_id=self.project.id, user_id=self.piping_supervisor.id, discipline="PIPING")
        m3 = ProjectMember(project_id=self.project.id, user_id=self.civil_supervisor.id, discipline="CIVIL")
        self.db.add_all([m2, m3])
        self.db.commit()

        # Seed activities
        self.civ101 = Activity(
            project_id=self.project.id,
            activity_code="CIV-101",
            activity_name="Site excavation and foundation trenching",
            discipline="CIVIL",
            planned_start=date(2026, 2, 1),
            planned_finish=date(2026, 3, 1),
        )
        self.pip201 = Activity(
            project_id=self.project.id,
            activity_code="PIP-201",
            activity_name="Pipeline fabrication and spooling",
            discipline="PIPING",
            planned_start=date(2026, 3, 1),
            planned_finish=date(2026, 5, 1),
        )
        self.ele301 = Activity(
            project_id=self.project.id,
            activity_code="ELE-301",
            activity_name="Substation main transformer cabling",
            discipline="ELECTRICAL",
            planned_start=date(2026, 4, 1),
            planned_finish=date(2026, 6, 1),
        )
        self.db.add_all([self.civ101, self.pip201, self.ele301])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_csv_upload_parsing_and_matching(self):
        """TEST 1: Supervisor uploads CSV containing valid activity progress update."""
        csv_data = "activity_code,description,progress,status,date\nPIP-201,Pipeline fabrication and spooling,40%,PROGRESS,2026-09-10\n"
        
        # Start activity PIP-201 first
        exec_pip = ActivityExecution(
            project_id=self.project.id,
            activity_id=self.pip201.id,
            actual_start=date(2026, 3, 1),
            progress_percentage=10.0,
            execution_status="IN_PROGRESS",
        )
        self.db.add(exec_pip)
        self.db.commit()

        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.piping_supervisor
        client = TestClient(app)

        token = create_access_token(subject=self.piping_supervisor.email)
        headers = {"Authorization": f"Bearer {token}"}

        files = {"file": ("report.csv", csv_data.encode("utf-8"), "text/csv")}
        resp = client.post(f"/api/projects/{self.project.id}/progress-reports/import-spreadsheet", headers=headers, files=files)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["source_type"], "CSV")
        self.assertEqual(len(data["items"]), 1)

        item = data["items"][0]
        self.assertEqual(item["matched_activity_code"], "PIP-201")
        self.assertEqual(item["extracted_update_type"], "PROGRESS")
        self.assertEqual(item["extracted_progress_percentage"], 40.0)
        self.assertEqual(item["match_status"], "MATCHED_HIGH")

        app.dependency_overrides.clear()

    def test_text_dpr_single_item_extraction(self):
        """TEST 4 & 6 & 7: Test status/progress parsing from DPR free text."""
        from app.services.batch_report_service import extract_items_from_text_dpr

        # TEST 4: "Pipeline fabrication reached 40% today."
        items1 = extract_items_from_text_dpr("Pipeline fabrication reached 40% today.")
        self.assertTrue(len(items1) >= 1)
        self.assertEqual(items1[0]["extracted_update_type"], "PROGRESS")
        self.assertEqual(items1[0]["extracted_progress_percentage"], 40.0)

        # TEST 6: "20% completed" -> PROGRESS 20
        items2 = extract_items_from_text_dpr("Civil trenching 20% completed")
        self.assertEqual(items2[0]["extracted_update_type"], "PROGRESS")
        self.assertEqual(items2[0]["extracted_progress_percentage"], 20.0)

        # TEST 7: "100% completed" -> COMPLETE 100
        items3 = extract_items_from_text_dpr("Site excavation 100% completed")
        self.assertEqual(items3[0]["extracted_update_type"], "COMPLETE")
        self.assertEqual(items3[0]["extracted_progress_percentage"], 100.0)

    def test_multi_item_dpr_extraction(self):
        """TEST 5: Paste multiple updates in one DPR."""
        dpr_text = """
Date: 10 Sep 2026

Civil:
Foundation trenching 20% completed.

Piping:
Pipeline fabrication reached 40%.

Electrical:
Main transformer cabling started.
"""
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.piping_supervisor
        client = TestClient(app)

        token = create_access_token(subject=self.piping_supervisor.email)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-text",
            headers=headers,
            json={"raw_text": dpr_text},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["source_type"], "TEXT")
        self.assertTrue(len(data["items"]) >= 3)

        app.dependency_overrides.clear()

    def test_unknown_activity_unmatched(self):
        """TEST 8: Unknown work description -> UNMATCHED."""
        from app.services.batch_report_service import extract_items_from_text_dpr
        items = extract_items_from_text_dpr("Installation of helicopter landing pad 50% done")

        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.piping_supervisor
        client = TestClient(app)

        token = create_access_token(subject=self.piping_supervisor.email)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-text",
            headers=headers,
            json={"raw_text": "Installation of helicopter landing pad 50% done"},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        item = data["items"][0]
        self.assertEqual(item["match_status"], "UNMATCHED")

        app.dependency_overrides.clear()

    def test_progress_regression_invalid(self):
        """TEST 10: Progress regression (current 50%, report 30%) -> INVALID."""
        exec_pip = ActivityExecution(
            project_id=self.project.id,
            activity_id=self.pip201.id,
            actual_start=date(2026, 3, 1),
            progress_percentage=50.0,
            execution_status="IN_PROGRESS",
        )
        self.db.add(exec_pip)
        self.db.commit()

        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.piping_supervisor
        client = TestClient(app)

        token = create_access_token(subject=self.piping_supervisor.email)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-text",
            headers=headers,
            json={"raw_text": "PIP-201 progress 30%"},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        item = data["items"][0]
        self.assertEqual(item["validation_status"], "INVALID")
        self.assertIn("cannot regress", item["error_message"].lower())

        app.dependency_overrides.clear()

    def test_apply_valid_report_and_idempotency(self):
        """TEST 11 & 12: Apply valid report item via Phase 5 service & test idempotency."""
        exec_pip = ActivityExecution(
            project_id=self.project.id,
            activity_id=self.pip201.id,
            actual_start=date(2026, 3, 1),
            progress_percentage=20.0,
            execution_status="IN_PROGRESS",
        )
        self.db.add(exec_pip)
        self.db.commit()

        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.piping_supervisor
        client = TestClient(app)

        token = create_access_token(subject=self.piping_supervisor.email)
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Create report session
        create_resp = client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-text",
            headers=headers,
            json={"raw_text": "PIP-201 progress 45%"},
        )
        report_data = create_resp.json()
        report_id = report_data["id"]
        item_id = report_data["items"][0]["id"]

        # Step 2: Approve item
        rev_resp = client.post(
            f"/api/projects/{self.project.id}/progress-reports/{report_id}/items/{item_id}/review",
            headers=headers,
            json={"action": "APPROVE"},
        )
        self.assertEqual(rev_resp.status_code, 200)

        # Step 3: Apply report
        apply_resp = client.post(
            f"/api/projects/{self.project.id}/progress-reports/{report_id}/apply",
            headers=headers,
        )
        self.assertEqual(apply_resp.status_code, 200)
        apply_data = apply_resp.json()
        self.assertEqual(apply_data["status"], "APPLIED")
        self.assertEqual(apply_data["items"][0]["review_status"], "APPLIED")

        # Verify DB execution state updated
        updated_exec = self.db.query(ActivityExecution).filter(ActivityExecution.activity_id == self.pip201.id).first()
        self.assertEqual(updated_exec.progress_percentage, 45.0)

        # Verify audit log ProgressUpdate created with source_type="REPORT_IMPORT"
        audit = self.db.query(ProgressUpdate).filter(ProgressUpdate.activity_id == self.pip201.id).order_by(ProgressUpdate.id.desc()).first()
        self.assertEqual(audit.source_type, "REPORT_IMPORT")
        self.assertEqual(audit.progress_percentage, 45.0)

        # TEST 12: Try to approve or modify APPLIED item again -> Conflict 409
        rev_again = client.post(
            f"/api/projects/{self.project.id}/progress-reports/{report_id}/items/{item_id}/review",
            headers=headers,
            json={"action": "APPROVE"},
        )
        self.assertEqual(rev_again.status_code, 409)

        app.dependency_overrides.clear()

    def test_planner_view_and_review_permissions(self):
        """TEST 3 & 2: Planner views report and reviews, but cannot execute supervisor updates directly."""
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.planner
        client = TestClient(app)

        planner_token = create_access_token(subject=self.planner.email)
        headers = {"Authorization": f"Bearer {planner_token}"}

        # Planner creates text report for review
        create_resp = client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-text",
            headers=headers,
            json={"raw_text": "PIP-201 progress 60%"},
        )
        self.assertEqual(create_resp.status_code, 201)
        report_id = create_resp.json()["id"]

        # Planner can view report list & details project-wide
        list_resp = client.get(f"/api/projects/{self.project.id}/progress-reports", headers=headers)
        self.assertEqual(list_resp.status_code, 200)

        # Planner CANNOT apply supervisor field execution update (Forbidden 403)
        apply_resp = client.post(f"/api/projects/{self.project.id}/progress-reports/{report_id}/apply", headers=headers)
        self.assertEqual(apply_resp.status_code, 403)

        app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()

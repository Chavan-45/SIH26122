import io
import csv
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import openpyxl

from app.database.database import Base, get_db
from app.main import app
from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.schedule_export import ScheduleExport, ScheduleExportItem
from app.schemas.execution import ProgressReportRequest
from app.services.execution_service import process_progress_update
from app.services.schedule_export_service import CANONICAL_COLUMNS, build_canonical_row, download_export_snapshot

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


class Phase11ScheduleSyncExportTests(unittest.TestCase):
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
        self.db.query(ScheduleExportItem).delete()
        self.db.query(ScheduleExport).delete()
        self.db.query(ProgressUpdate).delete()
        self.db.query(ActivityExecution).delete()
        self.db.query(Activity).delete()
        self.db.query(ProjectMember).delete()
        self.db.query(Project).delete()
        self.db.query(User).delete()
        self.db.commit()

        # Create Planner
        self.planner = User(
            email="planner@infra.com",
            full_name="Lead Planner John",
            hashed_password=hash_password("plannerpass123"),
            role="PLANNER",
            is_active=True,
        )
        self.db.add(self.planner)

        # Create Supervisor
        self.supervisor = User(
            email="supervisor_piping@infra.com",
            full_name="Piping Supervisor Alex",
            hashed_password=hash_password("suppass123"),
            role="SUPERVISOR",
            is_active=True,
        )
        self.db.add(self.supervisor)
        self.db.commit()
        self.db.refresh(self.planner)
        self.db.refresh(self.supervisor)

        # JWT Tokens
        self.planner_token = create_access_token(self.planner.id)
        self.supervisor_token = create_access_token(self.supervisor.id)

        self.planner_headers = {"Authorization": f"Bearer {self.planner_token}"}
        self.supervisor_headers = {"Authorization": f"Bearer {self.supervisor_token}"}

        # Create Project
        self.project = Project(
            name="Refinery Expansion Project",
            project_code="REF-EXP-2026",
            description="L5/L6 Schedule & Actuals sync test",
            location="Gujarat, India",
            planned_start_date=date(2026, 10, 1),
            planned_end_date=date(2027, 3, 31),
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
            discipline="PIPING",
        )
        self.db.add(member)

        # Add Baseline Activities
        self.act1 = Activity(
            project_id=self.project.id,
            activity_code="PIP-101",
            activity_name="Pipe Spool Fabrication & Welding",
            wbs_code="1.2.1",
            wbs_name="Piping Section",
            schedule_level="L5",
            discipline="PIPING",
            planned_start=date(2026, 10, 1),
            planned_finish=date(2026, 10, 15),
            planned_duration=14.0,
        )
        self.act2 = Activity(
            project_id=self.project.id,
            activity_code="PIP-102",
            activity_name="Pipe Hydrostatic Testing",
            wbs_code="1.2.2",
            wbs_name="Piping Section",
            schedule_level="L5",
            discipline="PIPING",
            planned_start=date(2026, 10, 16),
            planned_finish=date(2026, 10, 25),
            planned_duration=9.0,
        )
        self.act3 = Activity(
            project_id=self.project.id,
            activity_code="CIV-101",
            activity_name="Equipment Foundation Concrete Pouring",
            wbs_code="1.1.1",
            wbs_name="Civil Section",
            schedule_level="L5",
            discipline="CIVIL",
            planned_start=date(2026, 9, 1),
            planned_finish=date(2026, 9, 15),
            planned_duration=14.0,
        )
        self.db.add_all([self.act1, self.act2, self.act3])
        self.db.commit()
        self.db.refresh(self.act1)
        self.db.refresh(self.act2)
        self.db.refresh(self.act3)

        # Start act1 (PIP-101) with 30% progress
        process_progress_update(
            db=self.db,
            project_id=self.project.id,
            activity_id=self.act1.id,
            user=self.supervisor,
            report_req=ProgressReportRequest(
                update_type="START",
                reported_date=date(2026, 10, 2),  # started 1 day late
                progress_percentage=30.0,
                remarks="Fabrication started with 3 welders",
            ),
            source_type="MANUAL",
        )

    def tearDown(self):
        self.db.close()

    def test_01_no_previous_export_summary_and_changes_disabled(self):
        """Test 1: Project with activities but no export returns correct summary; CHANGES_ONLY is blocked."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/summary",
            headers=self.planner_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_activities"], 3)
        self.assertEqual(data["activities_with_actuals"], 1)  # act1 has progress
        self.assertEqual(data["changed_since_last_export"], 0)
        self.assertFalse(data["has_previous_export"])
        self.assertIsNone(data["last_export_at"])

        # Attempting CHANGES_ONLY export without previous export should fail with 400
        res_post = self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "CHANGES_ONLY", "file_format": "XLSX"},
        )
        self.assertEqual(res_post.status_code, 400)
        self.assertIn("No previous export exists", res_post.json()["detail"])

    def test_02_full_preview_all_activities_and_fallback(self):
        """Test 2: Preview FULL_SNAPSHOT returns all activities; unexecuted activities fall back to 0% NOT_STARTED."""
        res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/preview?mode=FULL_SNAPSHOT",
            headers=self.planner_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["export_mode"], "FULL_SNAPSHOT")
        self.assertEqual(data["total_activities"], 3)
        self.assertEqual(data["rows_to_export"], 3)
        self.assertEqual(len(data["items"]), 3)

        # Check PIP-101 (executed)
        pip101 = next(item for item in data["items"] if item["activity_code"] == "PIP-101")
        self.assertEqual(pip101["progress_percentage"], 30.0)
        self.assertEqual(pip101["execution_status"], "IN_PROGRESS")
        self.assertEqual(pip101["actual_start"], "2026-10-02")
        self.assertEqual(pip101["start_variance_days"], 1)  # 2026-10-02 - 2026-10-01 = 1

        # Check PIP-102 (not executed)
        pip102 = next(item for item in data["items"] if item["activity_code"] == "PIP-102")
        self.assertEqual(pip102["progress_percentage"], 0.0)
        self.assertEqual(pip102["execution_status"], "NOT_STARTED")
        self.assertEqual(pip102["actual_start"], "")
        self.assertEqual(pip102["actual_finish"], "")
        self.assertIsNone(pip102["start_variance_days"])

    def test_03_first_xlsx_export_generation_and_sheets(self):
        """Test 3: Generate first XLSX export and verify structure and sheets."""
        res = self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "XLSX"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        export_id = data["id"]
        self.assertEqual(data["status"], "GENERATED")
        self.assertEqual(data["row_count"], 3)
        self.assertTrue(data["file_name"].endswith(".xlsx"))
        self.assertIn("REF-EXP-2026", data["file_name"])

        # Check database records
        export_row = self.db.query(ScheduleExport).filter(ScheduleExport.id == export_id).first()
        self.assertIsNotNone(export_row)
        items_count = self.db.query(ScheduleExportItem).filter(ScheduleExportItem.export_id == export_id).count()
        self.assertEqual(items_count, 3)

        # Download and verify Excel workbook structure
        dl_res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/exports/{export_id}/download",
            headers=self.planner_headers,
        )
        self.assertEqual(dl_res.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(dl_res.content))
        sheet_names = wb.sheetnames
        self.assertIn("Activity Actuals", sheet_names)
        self.assertIn("Export Summary", sheet_names)

        # Verify Activity Actuals headers and row count
        ws_act = wb["Activity Actuals"]
        headers = [cell.value for cell in ws_act[1]]
        self.assertEqual(headers, CANONICAL_COLUMNS)
        self.assertEqual(ws_act.max_row, 4)  # 1 header + 3 rows

        # Verify Export Summary sheet contains project name and notice
        ws_sum = wb["Export Summary"]
        summary_text = [ws_sum.cell(row=r, column=2).value for r in range(1, ws_sum.max_row + 1)]
        self.assertTrue(any("Refinery Expansion Project" in str(v) for v in summary_text))
        self.assertTrue(any("does not directly modify Primavera" in str(v) for v in summary_text))

    def test_04_first_csv_export_generation_and_headers(self):
        """Test 4: Generate CSV export, parse back, and assert no internal database IDs."""
        res = self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "CSV"},
        )
        self.assertEqual(res.status_code, 201)
        export_id = res.json()["id"]

        dl_res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/exports/{export_id}/download",
            headers=self.planner_headers,
        )
        self.assertEqual(dl_res.status_code, 200)
        csv_text = dl_res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        header = rows[0]
        self.assertEqual(header, CANONICAL_COLUMNS)
        self.assertEqual(len(rows), 4)  # header + 3 activities

        # Assert no internal database IDs in columns
        for col in header:
            self.assertNotIn("_id", col)
            self.assertNotEqual("id", col)

    def test_05_change_detection_progress(self):
        """Test 5: Progress update triggers change flag PROGRESS_CHANGED and updates summary counter."""
        # 1. First Full Snapshot
        self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "XLSX"},
        )

        # 2. Update PIP-101 progress from 30% to 60%
        process_progress_update(
            db=self.db,
            project_id=self.project.id,
            activity_id=self.act1.id,
            user=self.supervisor,
            report_req=ProgressReportRequest(
                update_type="PROGRESS",
                reported_date=date(2026, 10, 5),
                progress_percentage=60.0,
                remarks="Fit-up completed",
            ),
            source_type="MANUAL",
        )

        # 3. Check Summary: changed_since_last_export == 1
        sum_res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/summary",
            headers=self.planner_headers,
        )
        self.assertEqual(sum_res.status_code, 200)
        self.assertEqual(sum_res.json()["changed_since_last_export"], 1)

        # 4. Check Preview
        prev_res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/preview?mode=CHANGES_ONLY",
            headers=self.planner_headers,
        )
        self.assertEqual(prev_res.status_code, 200)
        data = prev_res.json()
        self.assertEqual(data["rows_to_export"], 1)
        self.assertEqual(data["items"][0]["activity_code"], "PIP-101")
        self.assertIn("PROGRESS_CHANGED", data["items"][0]["change_flags"])

    def test_06_multiple_simultaneous_change_flags(self):
        """Test 6: Activity starting and progressing emits multiple change flags simultaneously."""
        # 1. Create baseline export
        self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "XLSX"},
        )

        # 2. Start PIP-102 (was NOT_STARTED, now IN_PROGRESS with actual_start and 25% progress)
        process_progress_update(
            db=self.db,
            project_id=self.project.id,
            activity_id=self.act2.id,
            user=self.supervisor,
            report_req=ProgressReportRequest(
                update_type="START",
                reported_date=date(2026, 10, 16),
                progress_percentage=25.0,
                remarks="Hydrotest prep started",
            ),
            source_type="MANUAL",
        )

        # 3. Preview CHANGES_ONLY
        prev_res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/preview?mode=CHANGES_ONLY",
            headers=self.planner_headers,
        )
        self.assertEqual(prev_res.status_code, 200)
        item = prev_res.json()["items"][0]
        self.assertEqual(item["activity_code"], "PIP-102")
        flags = item["change_flags"]
        self.assertIn("ACTUAL_START_SET", flags)
        self.assertIn("STATUS_CHANGED", flags)
        self.assertIn("PROGRESS_CHANGED", flags)

    def test_07_dynamic_overdue_not_counted_as_execution_change(self):
        """Test 7: Dynamic overdue calculation does not count as an execution change."""
        # CIV-101 has planned_finish=2026-09-15.
        # Create baseline export
        self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "XLSX"},
        )

        # Calling preview with no execution changes
        prev_res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/preview?mode=CHANGES_ONLY",
            headers=self.planner_headers,
        )
        self.assertEqual(prev_res.status_code, 200)
        self.assertEqual(prev_res.json()["rows_to_export"], 0)
        self.assertEqual(prev_res.json()["changed_activity_count"], 0)

    def test_08_changes_only_export(self):
        """Test 8: CHANGES_ONLY export includes only changed activities."""
        # 1. Full snapshot
        self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "XLSX"},
        )

        # 2. Update PIP-101 to 100% COMPLETE
        process_progress_update(
            db=self.db,
            project_id=self.project.id,
            activity_id=self.act1.id,
            user=self.supervisor,
            report_req=ProgressReportRequest(
                update_type="COMPLETE",
                reported_date=date(2026, 10, 14),
                progress_percentage=100.0,
                remarks="Completed early",
            ),
            source_type="MANUAL",
        )

        # 3. Create CHANGES_ONLY export
        res = self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "CHANGES_ONLY", "file_format": "CSV"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["export_mode"], "CHANGES_ONLY")
        self.assertEqual(data["row_count"], 1)
        self.assertEqual(data["items"][0]["activity_code"], "PIP-101")
        self.assertEqual(data["items"][0]["execution_status"], "COMPLETED")

    def test_09_no_changes_state(self):
        """Test 9: Immediate CHANGES_ONLY preview after export shows 0 changes and blocks export."""
        # 1. Full Snapshot
        self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "XLSX"},
        )

        # 2. Preview CHANGES_ONLY
        prev_res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/preview?mode=CHANGES_ONLY",
            headers=self.planner_headers,
        )
        self.assertEqual(prev_res.status_code, 200)
        self.assertEqual(prev_res.json()["rows_to_export"], 0)
        self.assertEqual(prev_res.json()["changed_activity_count"], 0)

        # 3. Attempting to create CHANGES_ONLY export fails with 400
        post_res = self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "CHANGES_ONLY", "file_format": "XLSX"},
        )
        self.assertEqual(post_res.status_code, 400)
        self.assertIn("No execution changes since last export", post_res.json()["detail"])

    def test_10_historical_snapshot_immutability(self):
        """Test 10: Critical historical snapshot immutability test."""
        # 1. Create Export A (PIP-101 is 30%)
        res_a = self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "CSV"},
        )
        self.assertEqual(res_a.status_code, 201)
        export_a_id = res_a.json()["id"]

        # 2. Update execution to 90%
        process_progress_update(
            db=self.db,
            project_id=self.project.id,
            activity_id=self.act1.id,
            user=self.supervisor,
            report_req=ProgressReportRequest(
                update_type="PROGRESS",
                reported_date=date(2026, 10, 8),
                progress_percentage=90.0,
                remarks="Nearly done",
            ),
            source_type="MANUAL",
        )

        # 3. Create Export B (PIP-101 is 90%)
        res_b = self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "CSV"},
        )
        self.assertEqual(res_b.status_code, 201)
        export_b_id = res_b.json()["id"]

        # 4. Download Export A and parse it
        dl_a = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/exports/{export_a_id}/download",
            headers=self.planner_headers,
        )
        rows_a = list(csv.DictReader(io.StringIO(dl_a.content.decode("utf-8"))))
        pip101_a = next(r for r in rows_a if r["activity_code"] == "PIP-101")
        self.assertEqual(float(pip101_a["progress_percentage"]), 30.0)

        # 5. Download Export B and parse it
        dl_b = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/exports/{export_b_id}/download",
            headers=self.planner_headers,
        )
        rows_b = list(csv.DictReader(io.StringIO(dl_b.content.decode("utf-8"))))
        pip101_b = next(r for r in rows_b if r["activity_code"] == "PIP-101")
        self.assertEqual(float(pip101_b["progress_percentage"]), 90.0)

    def test_11_supervisor_forbidden_rbac(self):
        """Test 11: Field Supervisors receive HTTP 403 Forbidden on all export endpoints."""
        endpoints = [
            ("GET", f"/api/projects/{self.project.id}/schedule-sync/summary"),
            ("GET", f"/api/projects/{self.project.id}/schedule-sync/preview"),
            ("POST", f"/api/projects/{self.project.id}/schedule-sync/exports"),
            ("GET", f"/api/projects/{self.project.id}/schedule-sync/exports"),
            ("GET", f"/api/projects/{self.project.id}/schedule-sync/exports/1"),
            ("GET", f"/api/projects/{self.project.id}/schedule-sync/exports/1/download"),
        ]
        for method, url in endpoints:
            if method == "GET":
                res = self.client.get(url, headers=self.supervisor_headers)
            else:
                res = self.client.post(url, headers=self.supervisor_headers, json={"export_mode": "FULL_SNAPSHOT"})
            self.assertEqual(res.status_code, 403, f"Failed for {method} {url}")

    def test_12_variance_calculations(self):
        """Test 12: Verify start variance (+, 0, -), finish variance, and overdue calculation."""
        # PIP-101: planned_start=2026-10-01, actual_start=2026-10-02 -> start_variance = +1
        # Now add actual_finish = 2026-10-10 (planned_finish=2026-10-15) -> finish_variance = -5 (early)
        process_progress_update(
            db=self.db,
            project_id=self.project.id,
            activity_id=self.act1.id,
            user=self.supervisor,
            report_req=ProgressReportRequest(
                update_type="COMPLETE",
                reported_date=date(2026, 10, 10),
                progress_percentage=100.0,
                remarks="Finished early",
            ),
            source_type="MANUAL",
        )

        res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/preview?mode=FULL_SNAPSHOT",
            headers=self.planner_headers,
        )
        self.assertEqual(res.status_code, 200)
        items = res.json()["items"]
        pip101 = next(item for item in items if item["activity_code"] == "PIP-101")
        self.assertEqual(pip101["start_variance_days"], 1)  # Started 1 day late
        self.assertEqual(pip101["finish_variance_days"], -5)  # Finished 5 days early

    def test_13_export_is_read_only_respecting_execution(self):
        """Test 13: Generating exports does NOT modify Activity, ActivityExecution, or ProgressUpdate."""
        initial_updates_count = self.db.query(ProgressUpdate).count()
        initial_executions_count = self.db.query(ActivityExecution).count()
        initial_activities_count = self.db.query(Activity).count()

        # Generate multiple exports
        self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "XLSX"},
        )
        self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "CSV"},
        )

        self.assertEqual(self.db.query(ProgressUpdate).count(), initial_updates_count)
        self.assertEqual(self.db.query(ActivityExecution).count(), initial_executions_count)
        self.assertEqual(self.db.query(Activity).count(), initial_activities_count)

    def test_14_export_filename_sanitization(self):
        """Test 14: Export file name includes sanitized project code, mode, date, and extension."""
        res = self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "XLSX"},
        )
        self.assertEqual(res.status_code, 201)
        fname = res.json()["file_name"]
        self.assertTrue(fname.startswith("REF-EXP-2026_actuals_full_"))
        self.assertTrue(fname.endswith(".xlsx"))

    def test_15_export_history_listing_and_detail(self):
        """Test 15: Export history list and detail endpoint return complete metadata."""
        # Create 2 exports
        self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "XLSX"},
        )
        res2 = self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "CSV"},
        )
        export_id2 = res2.json()["id"]

        # List history
        hist_res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
        )
        self.assertEqual(hist_res.status_code, 200)
        history = hist_res.json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["id"], export_id2)  # most recent first

        # Detail of export 2
        detail_res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/exports/{export_id2}",
            headers=self.planner_headers,
        )
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertEqual(detail["file_format"], "CSV")
        self.assertEqual(len(detail["items"]), 3)

    def test_16_download_endpoint_headers(self):
        """Test 16: Download endpoint returns correct Content-Disposition and media type headers."""
        res = self.client.post(
            f"/api/projects/{self.project.id}/schedule-sync/exports",
            headers=self.planner_headers,
            json={"export_mode": "FULL_SNAPSHOT", "file_format": "CSV"},
        )
        export_id = res.json()["id"]

        dl_res = self.client.get(
            f"/api/projects/{self.project.id}/schedule-sync/exports/{export_id}/download",
            headers=self.planner_headers,
        )
        self.assertEqual(dl_res.status_code, 200)
        self.assertIn("text/csv", dl_res.headers.get("content-type", ""))
        self.assertIn("attachment; filename=", dl_res.headers.get("content-disposition", ""))


if __name__ == "__main__":
    unittest.main()

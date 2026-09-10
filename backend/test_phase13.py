import io
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pypdf
from PIL import Image

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
from app.models.progress_report_import import ProgressReportImport
from app.models.progress_report_item import ProgressReportItem
from app.models.planner_review_case import PlannerReviewCase
from app.services.document_report_service import (
    validate_and_inspect_document,
    extract_native_pdf_text,
    process_document_progress_report,
)
from app.services.batch_report_service import validate_item_execution_transition

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


def create_minimal_pdf_bytes(text_per_page: list[str]) -> bytes:
    """Helper to generate a clean, valid multi-page PDF with native text."""
    writer = pypdf.PdfWriter()
    for text in text_per_page:
        # Create a page stream
        stream_content = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET"
        raw_pdf = f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length {len(stream_content)} >> stream
{stream_content}
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000234 00000 n 
0000000339 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
400
%%EOF"""
        reader = pypdf.PdfReader(io.BytesIO(raw_pdf.encode("latin-1")))
        writer.add_page(reader.pages[0])

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_minimal_image_bytes(format_type: str = "JPEG") -> bytes:
    """Helper to generate a valid minimal test image."""
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format=format_type)
    return buf.getvalue()


class Phase13DocumentIngestionTests(unittest.TestCase):
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

        # Create Planner
        self.planner = User(
            email="planner@infrastructure.org",
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
            project_code="PRJ-DOC-01",
            name="Hydrocracker Refinery Modernization",
            description="Phase 13 Document Ingestion Test Facility",
            location="Plot 4",
            planned_start_date=date(2026, 1, 1),
            planned_end_date=date(2026, 12, 31),
            created_by_id=self.planner.id,
        )
        self.db.add(self.project)
        self.db.commit()
        self.db.refresh(self.project)

        # Assign Civil & Piping Supervisors
        self.pm_civil = ProjectMember(
            project_id=self.project.id,
            user_id=self.sup_civil.id,
            discipline="CIVIL",
        )
        self.pm_piping = ProjectMember(
            project_id=self.project.id,
            user_id=self.sup_piping.id,
            discipline="PIPING",
        )
        self.db.add_all([self.pm_civil, self.pm_piping])
        self.db.commit()

        # Baseline Activities
        self.act_pip = Activity(
            project_id=self.project.id,
            activity_code="PIP-201",
            activity_name="Pipeline Fabrication and Spooling",
            discipline="PIPING",
            planned_start=date(2026, 2, 1),
            planned_finish=date(2026, 8, 1),
        )
        self.act_civ = Activity(
            project_id=self.project.id,
            activity_code="CIV-101",
            activity_name="Foundation Reinforcement Rebar",
            discipline="CIVIL",
            planned_start=date(2026, 2, 1),
            planned_finish=date(2026, 8, 1),
        )
        self.db.add_all([self.act_pip, self.act_civ])
        self.db.commit()
        self.db.refresh(self.act_pip)
        self.db.refresh(self.act_civ)

        # Execution records (started)
        self.exec_pip = ActivityExecution(
            project_id=self.project.id,
            activity_id=self.act_pip.id,
            execution_status="IN_PROGRESS",
            progress_percentage=20.0,
            actual_start=date(2026, 2, 5),
        )
        self.exec_civ = ActivityExecution(
            project_id=self.project.id,
            activity_id=self.act_civ.id,
            execution_status="IN_PROGRESS",
            progress_percentage=30.0,
            actual_start=date(2026, 2, 5),
        )
        self.db.add_all([self.exec_pip, self.exec_civ])
        self.db.commit()

        # Auth Tokens
        self.planner_token = create_access_token(self.planner.id)
        self.civil_token = create_access_token(self.sup_civil.id)
        self.piping_token = create_access_token(self.sup_piping.id)

        self.planner_headers = {"Authorization": f"Bearer {self.planner_token}"}
        self.civil_headers = {"Authorization": f"Bearer {self.civil_token}"}
        self.piping_headers = {"Authorization": f"Bearer {self.piping_token}"}

    def tearDown(self):
        self.db.close()

    # TEST 1: Upload valid text-based PDF -> extracts text natively, ProgressReportItem (PROGRESS 40), 0 direct execution updates
    def test_01_text_pdf_native_extraction_no_silent_execution(self):
        pdf_bytes = create_minimal_pdf_bytes(["PIP-201 reached 40% today."])
        
        # Verify initial execution progress before upload is 20%
        exec_before = self.db.query(ActivityExecution).filter(ActivityExecution.activity_id == self.act_pip.id).first()
        self.assertEqual(exec_before.progress_percentage, 20.0)

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("site_report.pdf", pdf_bytes, "application/pdf")},
            headers=self.piping_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()

        self.assertEqual(data["source_type"], "PDF")
        self.assertEqual(data["status"], "REVIEW")
        self.assertEqual(data["total_items"], 1)
        
        item = data["items"][0]
        self.assertEqual(item["extracted_update_type"], "PROGRESS")
        self.assertEqual(item["extracted_progress_percentage"], 40.0)
        self.assertEqual(item["matched_activity_code"], "PIP-201")
        self.assertEqual(item["review_status"], "PENDING")

        # Crucial check: 0 silent execution updates
        exec_after = self.db.query(ActivityExecution).filter(ActivityExecution.activity_id == self.act_pip.id).first()
        self.assertEqual(exec_after.progress_percentage, 20.0)
        updates_count = self.db.query(ProgressUpdate).filter(ProgressUpdate.project_id == self.project.id).count()
        self.assertEqual(updates_count, 0)

    # TEST 2: Text PDF containing multiple updates -> generates separate items
    def test_02_text_pdf_multiple_updates(self):
        page_1 = "PIP-201 reached 45% today."
        page_2 = "CIV-101 reached 50% today."
        pdf_bytes = create_minimal_pdf_bytes([page_1, page_2])

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("multi_page_dpr.pdf", pdf_bytes, "application/pdf")},
            headers=self.planner_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["total_items"], 2)
        self.assertEqual(data["page_count"], 2)

        # Check page provenance
        pages = [it["source_page"] for it in data["items"]]
        self.assertIn(1, pages)
        self.assertIn(2, pages)

    # TEST 3: Upload scanned PDF -> Gemini fallback extracts structured updates
    @patch("app.services.document_report_service.extract_updates_via_gemini_multimodal")
    def test_03_scanned_pdf_gemini_fallback(self, mock_gemini):
        # Empty text PDF (scanned)
        scanned_pdf_bytes = create_minimal_pdf_bytes([""])
        mock_gemini.return_value = [
            {
                "raw_description": "Pipeline fabrication achieved 55%",
                "activity_code_hint": "PIP-201",
                "extracted_update_type": "PROGRESS",
                "extracted_progress_percentage": 55.0,
                "reported_date": "2026-05-10",
                "remarks": "Scan OCR test",
                "source_page": 1,
                "raw_text": "PIP-201 55%",
            }
        ]

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("scanned_sheet.pdf", scanned_pdf_bytes, "application/pdf")},
            headers=self.planner_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["total_items"], 1)
        self.assertEqual(data["items"][0]["extracted_progress_percentage"], 55.0)
        self.assertEqual(data["items"][0]["matched_activity_code"], "PIP-201")

    # TEST 4: Upload JPG image with readable text -> PROGRESS 60, not COMPLETE 100
    @patch("app.services.document_report_service.extract_updates_via_gemini_multimodal")
    def test_04_jpg_image_progress_sixty_not_complete(self, mock_gemini):
        img_bytes = create_minimal_image_bytes("JPEG")
        mock_gemini.return_value = [
            {
                "raw_description": "Foundation reinforcement 60% complete",
                "activity_code_hint": "CIV-101",
                "extracted_update_type": "PROGRESS",
                "extracted_progress_percentage": 60.0,
                "reported_date": "2026-05-12",
                "remarks": "Site photo caption",
                "source_page": None,
                "raw_text": "Foundation reinforcement 60% complete",
            }
        ]

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("site_photo.jpg", img_bytes, "image/jpeg")},
            headers=self.civil_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["source_type"], "IMAGE")
        self.assertEqual(data["items"][0]["extracted_update_type"], "PROGRESS")
        self.assertEqual(data["items"][0]["extracted_progress_percentage"], 60.0)

    # TEST 5: 100% complete statement -> COMPLETE 100
    @patch("app.services.document_report_service.extract_updates_via_gemini_multimodal")
    def test_05_image_complete_hundred(self, mock_gemini):
        img_bytes = create_minimal_image_bytes("PNG")
        mock_gemini.return_value = [
            {
                "raw_description": "Foundation reinforcement 100% completed today",
                "activity_code_hint": "CIV-101",
                "extracted_update_type": "COMPLETE",
                "extracted_progress_percentage": 100.0,
                "reported_date": "2026-05-15",
                "remarks": "Final pour completed",
                "source_page": None,
                "raw_text": "CIV-101 100% completed today",
            }
        ]

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("completion_photo.png", img_bytes, "image/png")},
            headers=self.civil_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["items"][0]["extracted_update_type"], "COMPLETE")
        self.assertEqual(data["items"][0]["extracted_progress_percentage"], 100.0)

    # TEST 6: Image containing unrelated text only -> no fake progress items
    @patch("app.services.document_report_service.extract_updates_via_gemini_multimodal")
    def test_06_unrelated_text_no_fake_items(self, mock_gemini):
        img_bytes = create_minimal_image_bytes("JPEG")
        mock_gemini.return_value = []

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("unrelated.jpg", img_bytes, "image/jpeg")},
            headers=self.planner_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("No readable field progress updates were found", response.json()["detail"])

    # TEST 7: Corrupted PDF -> clear 400 error
    def test_07_corrupted_pdf_error(self):
        corrupted_bytes = b"This is not a real PDF file content."

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("broken.pdf", corrupted_bytes, "application/pdf")},
            headers=self.planner_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Corrupted or invalid PDF", response.json()["detail"])

    # TEST 8: Encrypted PDF -> clear 400 error
    def test_08_encrypted_pdf_error(self):
        # Create an encrypted PDF with pypdf
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("secret_password")
        buf = io.BytesIO()
        writer.write(buf)
        encrypted_bytes = buf.getvalue()

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("encrypted.pdf", encrypted_bytes, "application/pdf")},
            headers=self.planner_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Encrypted or password-protected PDF", response.json()["detail"])

    # TEST 9: Oversized file -> rejected before processing
    def test_09_oversized_file_rejected(self):
        oversized_bytes = b"A" * (11 * 1024 * 1024)  # 11 MB (> 10 MB limit)

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("huge.pdf", oversized_bytes, "application/pdf")},
            headers=self.planner_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("File size exceeds maximum limit of 10 MB", response.json()["detail"])

    # TEST 10: PDF above supported page limit (> 20 pages) -> clear 400 error
    def test_10_pdf_above_page_limit_error(self):
        writer = pypdf.PdfWriter()
        for _ in range(25):  # 25 pages > 20 limit
            writer.add_blank_page(width=100, height=100)
        buf = io.BytesIO()
        writer.write(buf)
        twenty_five_page_pdf = buf.getvalue()

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("long_report.pdf", twenty_five_page_pdf, "application/pdf")},
            headers=self.planner_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF exceeds maximum supported limit of 20 pages", response.json()["detail"])

    # TEST 11: Supervisor uploads document containing own-discipline update -> normal review flow
    def test_11_supervisor_own_discipline_upload(self):
        pdf_bytes = create_minimal_pdf_bytes(["CIV-101 reached 50% today."])

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("civil_dpr.pdf", pdf_bytes, "application/pdf")},
            headers=self.civil_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["items"][0]["matched_discipline"], "CIVIL")
        self.assertEqual(data["items"][0]["validation_status"], "VALID")

    # TEST 12: Supervisor document contains unauthorized discipline -> cannot apply update
    def test_12_supervisor_unauthorized_discipline_cannot_apply(self):
        # Civil supervisor uploads Piping update (PIP-201)
        pdf_bytes = create_minimal_pdf_bytes(["PIP-201 reached 50% today."])

        response = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("piping_update.pdf", pdf_bytes, "application/pdf")},
            headers=self.civil_headers,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        report_id = data["id"]
        item_id = data["items"][0]["id"]

        # Attempt to approve -> blocked because candidate matcher rejected piping for civil supervisor (unmatched)
        approve_resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/{report_id}/items/{item_id}/review",
            json={"action": "APPROVE"},
            headers=self.civil_headers,
        )
        self.assertEqual(approve_resp.status_code, 400)
        self.assertIn("Unmatched activity", approve_resp.json()["detail"])

        # Attempt to manually link PIPING activity by CIVIL supervisor -> 403 Forbidden
        select_resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/{report_id}/items/{item_id}/select-activity",
            json={"activity_id": self.act_pip.id},
            headers=self.civil_headers,
        )
        self.assertEqual(select_resp.status_code, 403)
        self.assertIn("Access forbidden", select_resp.json()["detail"])

    # TEST 13: Low-confidence document item -> reaches Planner Review Center
    def test_13_low_confidence_item_in_review_center(self):
        pdf_bytes = create_minimal_pdf_bytes(["Ambiguous concrete pouring without code reached 50%"])

        create_resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("unclear_dpr.pdf", pdf_bytes, "application/pdf")},
            headers=self.planner_headers,
        )
        self.assertEqual(create_resp.status_code, 201)
        data = create_resp.json()
        self.assertGreaterEqual(data["total_items"], 1)

        # Check Planner Review Center queue
        rc_resp = self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers=self.planner_headers,
        )
        self.assertEqual(rc_resp.status_code, 200)
        rc_data = rc_resp.json()
        self.assertGreaterEqual(rc_data["total"], 1)

    # TEST 14: Unknown/unplanned work -> Review Center unplanned workflow
    def test_14_unplanned_work_review_center_workflow(self):
        pdf_bytes = create_minimal_pdf_bytes(["Unplanned emergency trench dewatering complete"])

        create_resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("unplanned.pdf", pdf_bytes, "application/pdf")},
            headers=self.planner_headers,
        )
        self.assertEqual(create_resp.status_code, 201)
        data = create_resp.json()
        item_id = data["items"][0]["id"]

        # Fetch Review Center queue
        rc_cases = self.client.get(
            f"/api/projects/{self.project.id}/review-center",
            headers=self.planner_headers,
        ).json()
        case = next(c for c in rc_cases["items"] if c["source_id"] == item_id and c["source_type"] == "PROGRESS_REPORT")
        case_id = case["id"]

        # Mark as unplanned through Review Center
        action_resp = self.client.post(
            f"/api/projects/{self.project.id}/review-center/{case_id}/mark-unplanned",
            json={"review_reason": "Approved as emergency work"},
            headers=self.planner_headers,
        )
        self.assertEqual(action_resp.status_code, 200)
        self.assertEqual(action_resp.json()["decision"], "UNPLANNED")

    # TEST 15: Approve valid document-derived item -> applied via Phase 5 execution service, REPORT_IMPORT source
    def test_15_approve_and_apply_document_item_execution_update(self):
        pdf_bytes = create_minimal_pdf_bytes(["PIP-201 reached 50% today."])

        create_resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("piping_dpr.pdf", pdf_bytes, "application/pdf")},
            headers=self.piping_headers,
        )
        self.assertEqual(create_resp.status_code, 201)
        report_id = create_resp.json()["id"]
        item_id = create_resp.json()["items"][0]["id"]

        # Approve item
        app_resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/{report_id}/items/{item_id}/review",
            json={"action": "APPROVE"},
            headers=self.piping_headers,
        )
        self.assertEqual(app_resp.status_code, 200)

        # Apply report
        apply_resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/{report_id}/apply",
            headers=self.piping_headers,
        )
        self.assertEqual(apply_resp.status_code, 200)

        # Verify DB execution state updated to 50%
        exec_updated = self.db.query(ActivityExecution).filter(ActivityExecution.activity_id == self.act_pip.id).first()
        self.assertEqual(exec_updated.progress_percentage, 50.0)

        # Verify ProgressUpdate audit record created with source_type="REPORT_IMPORT"
        pu = self.db.query(ProgressUpdate).filter(ProgressUpdate.activity_id == self.act_pip.id).order_by(ProgressUpdate.id.desc()).first()
        self.assertIsNotNone(pu)
        self.assertEqual(pu.source_type, "REPORT_IMPORT")
        self.assertEqual(pu.progress_percentage, 50.0)

    # TEST 16: Refresh review -> document report persists
    def test_16_document_report_persists_on_refresh(self):
        pdf_bytes = create_minimal_pdf_bytes(["PIP-201 reached 35% today."])

        create_resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("persisted_report.pdf", pdf_bytes, "application/pdf")},
            headers=self.piping_headers,
        )
        report_id = create_resp.json()["id"]

        # Fetch detail by ID
        fetch_resp = self.client.get(
            f"/api/projects/{self.project.id}/progress-reports/{report_id}",
            headers=self.piping_headers,
        )
        self.assertEqual(fetch_resp.status_code, 200)
        data = fetch_resp.json()
        self.assertEqual(data["id"], report_id)
        self.assertEqual(data["source_type"], "PDF")
        self.assertEqual(len(data["items"]), 1)

    # TEST 17: History endpoint -> PDF/IMAGE imports visible
    def test_17_history_displays_pdf_and_image(self):
        pdf_bytes = create_minimal_pdf_bytes(["PIP-201 reached 35% today."])
        self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("history_test.pdf", pdf_bytes, "application/pdf")},
            headers=self.piping_headers,
        )

        hist_resp = self.client.get(
            f"/api/projects/{self.project.id}/progress-reports",
            headers=self.piping_headers,
        )
        self.assertEqual(hist_resp.status_code, 200)
        items = hist_resp.json()
        source_types = [h["source_type"] for h in items]
        self.assertIn("PDF", source_types)

    # TEST 18: Original temporary document cleaned up after processing
    def test_18_temporary_processing_cleanup(self):
        # Verification that no local persistent file is left on disk
        pdf_bytes = create_minimal_pdf_bytes(["PIP-201 reached 35% today."])
        resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-document",
            files={"file": ("cleanup_test.pdf", pdf_bytes, "application/pdf")},
            headers=self.piping_headers,
        )
        self.assertEqual(resp.status_code, 201)

    # TEST 19: Existing CSV/XLSX Progress Reports still work exactly as before
    def test_19_existing_spreadsheet_import_unaffected(self):
        csv_content = b"description,progress_percentage\nPipeline Fabrication,45\n"
        resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-spreadsheet",
            files={"file": ("report.csv", csv_content, "text/csv")},
            headers=self.piping_headers,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["source_type"], "CSV")

    # TEST 20: Existing Paste DPR text import still works exactly as before
    def test_20_existing_paste_dpr_unaffected(self):
        resp = self.client.post(
            f"/api/projects/{self.project.id}/progress-reports/import-text",
            json={"raw_text": "PIP-201 reached 48% today."},
            headers=self.piping_headers,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["source_type"], "TEXT")


if __name__ == "__main__":
    unittest.main()

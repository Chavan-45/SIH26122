import os
import sys
import unittest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test DB environment before importing app modules
TEST_DB_FILE = "./test_phase8.db"
if os.path.exists(TEST_DB_FILE):
    os.remove(TEST_DB_FILE)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
os.environ["SECRET_KEY"] = "test-secret-key-phase-8"

from app.database.database import Base
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.ai_chat import AIConversation, AIMessage
from app.models.execution_report_draft import ExecutionReportDraft
from app.core.security import hash_password
from app.services.activity_matching_service import match_activity_for_report
from app.ai.report_extractor import extract_execution_report, parse_execution_report_fallback
from app.services.execution_service import process_progress_update
from app.schemas.execution import ProgressReportRequest, UpdateTypeEnum


class TestPhase8NaturalLanguageReporting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine = create_engine(f"sqlite:///{TEST_DB_FILE}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        cls.db = TestingSessionLocal()

        # 1. Create test users
        cls.planner = User(
            full_name="Planner Alice",
            email="alice.planner@example.com",
            hashed_password=hash_password("password123"),
            role="PLANNER",
            is_active=True,
        )
        cls.civil_sup = User(
            full_name="Civil Supervisor Bob",
            email="bob.civil@example.com",
            hashed_password=hash_password("password123"),
            role="SUPERVISOR",
            is_active=True,
        )
        cls.piping_sup = User(
            full_name="Piping Supervisor Charlie",
            email="charlie.piping@example.com",
            hashed_password=hash_password("password123"),
            role="SUPERVISOR",
            is_active=True,
        )
        cls.db.add_all([cls.planner, cls.civil_sup, cls.piping_sup])
        cls.db.commit()

        # 2. Create test project
        cls.project = Project(
            name="Refinery Expansion Project",
            project_code="OIL-FAC-001",
            created_by_id=cls.planner.id,
            planned_start_date=date.today(),
            planned_end_date=date.today() + timedelta(days=30),
            status="ACTIVE",
        )
        cls.db.add(cls.project)
        cls.db.commit()

        # 3. Create project memberships
        cls.m1 = ProjectMember(project_id=cls.project.id, user_id=cls.civil_sup.id, discipline="CIVIL")
        cls.m2 = ProjectMember(project_id=cls.project.id, user_id=cls.piping_sup.id, discipline="PIPING")
        cls.db.add_all([cls.m1, cls.m2])
        cls.db.commit()

        # 4. Create baseline activities
        cls.act_civ1 = Activity(
            project_id=cls.project.id,
            activity_code="CIV-103",
            activity_name="Foundation Concreting",
            discipline="CIVIL",
            planned_start=date.today(),
            planned_finish=date.today() + timedelta(days=10),
            planned_duration=10,
        )
        cls.act_civ2 = Activity(
            project_id=cls.project.id,
            activity_code="CIV-104",
            activity_name="Foundation Reinforcement",
            discipline="CIVIL",
            planned_start=date.today(),
            planned_finish=date.today() + timedelta(days=5),
            planned_duration=5,
        )
        cls.act_pip1 = Activity(
            project_id=cls.project.id,
            activity_code="PIP-201",
            activity_name="Pipeline Fabrication",
            discipline="PIPING",
            planned_start=date.today(),
            planned_finish=date.today() + timedelta(days=15),
            planned_duration=15,
        )
        cls.db.add_all([cls.act_civ1, cls.act_civ2, cls.act_pip1])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        engine = cls.db.get_bind()
        cls.db.close()
        engine.dispose()
        try:
            if os.path.exists(TEST_DB_FILE):
                os.remove(TEST_DB_FILE)
        except Exception:
            pass

    def test_01_structured_extraction(self):
        """Test extraction of update_type, progress, dates, and code."""
        ext = parse_execution_report_fallback("We started foundation concreting today.")
        self.assertEqual(ext.intent, "EXECUTION_REPORT")
        self.assertEqual(ext.update_type, "START")
        self.assertEqual(ext.reported_date, date.today().isoformat())

        ext2 = parse_execution_report_fallback("Pipeline fabrication reached 60 percent today.")
        self.assertEqual(ext2.intent, "EXECUTION_REPORT")
        self.assertEqual(ext2.update_type, "PROGRESS")
        self.assertEqual(ext2.progress_percentage, 60.0)

        ext3 = parse_execution_report_fallback("We finished CIV-103 this morning.")
        self.assertEqual(ext3.intent, "EXECUTION_REPORT")
        self.assertEqual(ext3.explicit_activity_code, "CIV-103")
        self.assertEqual(ext3.update_type, "COMPLETE")

    def test_02_discipline_scoped_activity_matching(self):
        """Test candidate matching is strictly restricted to Supervisor's assigned discipline."""
        act, conf, status, alts = match_activity_for_report(
            db=self.db,
            project_id=self.project.id,
            user_role="SUPERVISOR",
            user_discipline="CIVIL",
            explicit_activity_code="CIV-103",
        )
        self.assertIsNotNone(act)
        self.assertEqual(act.activity_code, "CIV-103")
        self.assertEqual(conf, 1.0)
        self.assertEqual(status, "MATCHED_HIGH")

        # CIVIL supervisor trying to match PIPING activity code
        act_cross, conf_cross, status_cross, _ = match_activity_for_report(
            db=self.db,
            project_id=self.project.id,
            user_role="SUPERVISOR",
            user_discipline="CIVIL",
            explicit_activity_code="PIP-201",
        )
        self.assertIsNone(act_cross)
        self.assertEqual(status_cross, "UNMATCHED")

    def test_03_fuzzy_description_matching(self):
        """Test description fuzzy matching with confidence thresholds."""
        act, conf, status, alts = match_activity_for_report(
            db=self.db,
            project_id=self.project.id,
            user_role="SUPERVISOR",
            user_discipline="CIVIL",
            activity_description="foundation concreting work",
            update_type="START",
        )
        self.assertIsNotNone(act)
        self.assertEqual(act.activity_code, "CIV-103")
        self.assertGreaterEqual(conf, 0.85)

    def test_04_no_silent_writes_and_draft_creation(self):
        """Test that natural language reporting creates a PENDING draft without changing execution state."""
        exec_before = self.db.query(ActivityExecution).filter(ActivityExecution.activity_id == self.act_civ1.id).first()
        self.assertIsNone(exec_before)

        draft = ExecutionReportDraft(
            project_id=self.project.id,
            reported_by_id=self.civil_sup.id,
            original_text="We started foundation concreting today.",
            intent="EXECUTION_REPORT",
            update_type="START",
            reported_date=date.today(),
            matched_activity_id=self.act_civ1.id,
            match_confidence=0.96,
            match_status="MATCHED_HIGH",
            status="PENDING",
        )
        self.db.add(draft)
        self.db.commit()

        exec_after = self.db.query(ActivityExecution).filter(ActivityExecution.activity_id == self.act_civ1.id).first()
        self.assertIsNone(exec_after)
        self.assertEqual(draft.status, "PENDING")

        from app.routers.ai_chat import build_draft_response
        draft_resp = build_draft_response(self.db, draft)
        self.assertEqual(draft_resp.proposed_status, "IN_PROGRESS")
        self.assertEqual(draft_resp.proposed_progress, 0.0)

    def test_05_confirmation_triggers_phase5_service_with_ai_chat_source(self):
        """Test that confirming draft executes Phase 5 service with source_type='AI_CHAT'."""
        draft = self.db.query(ExecutionReportDraft).filter(ExecutionReportDraft.matched_activity_id == self.act_civ1.id).first()
        self.assertIsNotNone(draft)

        report_req = ProgressReportRequest(
            update_type=UpdateTypeEnum.START,
            reported_date=draft.reported_date,
        )

        exec_obj, update_log = process_progress_update(
            db=self.db,
            project_id=self.project.id,
            activity_id=draft.matched_activity_id,
            user=self.civil_sup,
            report_req=report_req,
            source_type="AI_CHAT",
        )

        draft.status = "CONFIRMED"
        self.db.commit()

        self.assertEqual(exec_obj.execution_status, "IN_PROGRESS")
        self.assertEqual(update_log.source_type, "AI_CHAT")
        self.assertEqual(update_log.reported_by_id, self.civil_sup.id)
        self.assertEqual(draft.status, "CONFIRMED")

    def test_06_progress_update_and_monotonicity(self):
        """Test PROGRESS update to 60% and regression rejection."""
        # 1. Update to 60%
        req_60 = ProgressReportRequest(
            update_type=UpdateTypeEnum.PROGRESS,
            reported_date=date.today(),
            progress_percentage=60.0,
        )
        exec_obj, update_log = process_progress_update(
            db=self.db,
            project_id=self.project.id,
            activity_id=self.act_civ1.id,
            user=self.civil_sup,
            report_req=req_60,
            source_type="AI_CHAT",
        )
        self.assertEqual(exec_obj.progress_percentage, 60.0)

        # 2. Test progress regression (reporting 40% when current is 60%)
        req_reg = ProgressReportRequest(
            update_type=UpdateTypeEnum.PROGRESS,
            reported_date=date.today(),
            progress_percentage=40.0,
        )
        with self.assertRaises(Exception):
            process_progress_update(
                db=self.db,
                project_id=self.project.id,
                activity_id=self.act_civ1.id,
                user=self.civil_sup,
                report_req=req_reg,
                source_type="AI_CHAT",
            )
        self.db.rollback()

    def test_07_completion_and_completed_lock(self):
        """Test completing activity and verifying completed activity lock."""
        req_comp = ProgressReportRequest(
            update_type=UpdateTypeEnum.COMPLETE,
            reported_date=date.today(),
        )
        exec_obj, update_log = process_progress_update(
            db=self.db,
            project_id=self.project.id,
            activity_id=self.act_civ1.id,
            user=self.civil_sup,
            report_req=req_comp,
            source_type="AI_CHAT",
        )
        self.assertEqual(exec_obj.execution_status, "COMPLETED")
        self.assertEqual(exec_obj.progress_percentage, 100.0)

        # Further updates on completed activity must fail
        with self.assertRaises(Exception):
            process_progress_update(
                db=self.db,
                project_id=self.project.id,
                activity_id=self.act_civ1.id,
                user=self.civil_sup,
                report_req=ProgressReportRequest(update_type=UpdateTypeEnum.PROGRESS, reported_date=date.today(), progress_percentage=90.0),
                source_type="AI_CHAT",
            )
        self.db.rollback()

    def test_08_on_hold_and_resume_transitions(self):
        """Test ON_HOLD and RESUME state transitions on CIV-104."""
        # 1. Start CIV-104
        process_progress_update(self.db, self.project.id, self.act_civ2.id, self.civil_sup, ProgressReportRequest(update_type=UpdateTypeEnum.START, reported_date=date.today()))

        # 2. Put ON_HOLD
        exec_hold, _ = process_progress_update(self.db, self.project.id, self.act_civ2.id, self.civil_sup, ProgressReportRequest(update_type=UpdateTypeEnum.ON_HOLD, reported_date=date.today(), remarks="Material delayed"))
        self.assertEqual(exec_hold.execution_status, "ON_HOLD")

        # 3. Resume
        exec_res, _ = process_progress_update(self.db, self.project.id, self.act_civ2.id, self.civil_sup, ProgressReportRequest(update_type=UpdateTypeEnum.RESUME, reported_date=date.today()))
        self.assertEqual(exec_res.execution_status, "IN_PROGRESS")

    def test_09_partial_percentage_normalization_rules(self):
        """Test exact normalization rules for explicit partial percentages and completion phrases."""
        # 1. "PIP-201 is 20% completed" -> PROGRESS 20%
        e1 = parse_execution_report_fallback("PIP-201 is 20% completed")
        self.assertEqual(e1.update_type, "PROGRESS")
        self.assertEqual(e1.progress_percentage, 20.0)

        # 2. "PIP-201 is 20% complete" -> PROGRESS 20%
        e2 = parse_execution_report_fallback("PIP-201 is 20% complete")
        self.assertEqual(e2.update_type, "PROGRESS")
        self.assertEqual(e2.progress_percentage, 20.0)

        # 3. "PIP-201 is 75 percent completed" -> PROGRESS 75%
        e3 = parse_execution_report_fallback("PIP-201 is 75 percent completed")
        self.assertEqual(e3.update_type, "PROGRESS")
        self.assertEqual(e3.progress_percentage, 75.0)

        # 4. "PIP-201 is 99% complete" -> PROGRESS 99%
        e4 = parse_execution_report_fallback("PIP-201 is 99% complete")
        self.assertEqual(e4.update_type, "PROGRESS")
        self.assertEqual(e4.progress_percentage, 99.0)

        # 5. "PIP-201 is 100% complete" -> COMPLETE 100%
        e5 = parse_execution_report_fallback("PIP-201 is 100% complete")
        self.assertEqual(e5.update_type, "COMPLETE")
        self.assertEqual(e5.progress_percentage, 100.0)

        # 6. "PIP-201 completed today" -> COMPLETE 100%
        e6 = parse_execution_report_fallback("PIP-201 completed today")
        self.assertEqual(e6.update_type, "COMPLETE")
        self.assertEqual(e6.progress_percentage, 100.0)

        # 7. "Pipeline fabrication is finished" -> COMPLETE 100%
        e7 = parse_execution_report_fallback("Pipeline fabrication is finished")
        self.assertEqual(e7.update_type, "COMPLETE")
        self.assertEqual(e7.progress_percentage, 100.0)

    def test_10_conversation_draft_reconstruction(self):
        """Test GET conversation restores draft state for PENDING and CONFIRMED drafts."""
        from app.routers.ai_chat import get_ai_conversation, confirm_execution_report_draft

        # Create a conversation
        conv = AIConversation(
            project_id=self.project.id,
            user_id=self.civil_sup.id,
            title="Test Persistence Conv",
        )
        self.db.add(conv)
        self.db.commit()

        # Create a draft
        draft = ExecutionReportDraft(
            project_id=self.project.id,
            reported_by_id=self.civil_sup.id,
            conversation_id=conv.id,
            original_text="CIV-104 is 20% completed",
            intent="EXECUTION_REPORT",
            update_type="PROGRESS",
            reported_date=date.today(),
            progress_percentage=20.0,
            matched_activity_id=self.act_civ2.id,
            match_confidence=1.0,
            match_status="MATCHED_HIGH",
            status="PENDING",
        )
        self.db.add(draft)
        self.db.commit()

        # Create Assistant message referencing draft
        import json
        msg = AIMessage(
            conversation_id=conv.id,
            role="ASSISTANT",
            content="I matched a schedule activity for your field report.",
            metadata_json=json.dumps({"draft_id": draft.id}),
        )
        self.db.add(msg)
        self.db.commit()

        # 1. Test PENDING reconstruction
        conv_resp = get_ai_conversation(
            project_id=self.project.id,
            conversation_id=conv.id,
            current_user=self.civil_sup,
            db=self.db,
        )
        self.assertEqual(len(conv_resp.messages), 1)
        self.assertIsNotNone(conv_resp.messages[0].draft)
        self.assertEqual(conv_resp.messages[0].draft.status, "PENDING")
        self.assertEqual(conv_resp.messages[0].draft.proposed_progress, 20.0)

        # 2. Test confirm draft -> status becomes CONFIRMED
        confirm_resp = confirm_execution_report_draft(
            project_id=self.project.id,
            draft_id=draft.id,
            current_user=self.civil_sup,
            db=self.db,
        )
        self.assertEqual(confirm_resp.status, "CONFIRMED")

        # 3. Test CONFIRMED reconstruction upon reopening conversation
        conv_resp_confirmed = get_ai_conversation(
            project_id=self.project.id,
            conversation_id=conv.id,
            current_user=self.civil_sup,
            db=self.db,
        )
        self.assertEqual(conv_resp_confirmed.messages[0].draft.status, "CONFIRMED")

        # 4. Test idempotency (cannot confirm again)
        with self.assertRaises(Exception):
            confirm_execution_report_draft(
                project_id=self.project.id,
                draft_id=draft.id,
                current_user=self.civil_sup,
                db=self.db,
            )
        self.db.rollback()


if __name__ == "__main__":
    unittest.main()



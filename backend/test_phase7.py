import os
import sys
import unittest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test DB environment before importing app modules
TEST_DB_FILE = "./test_phase7.db"
if os.path.exists(TEST_DB_FILE):
    try:
        os.remove(TEST_DB_FILE)
    except Exception:
        pass

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
os.environ["JWT_SECRET_KEY"] = "test-phase7-super-secure-jwt-secret-key-32-bytes!"

from app.core.config import settings
settings.JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]

from app.main import app
from app.database.database import Base, get_db
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.ai_chat import AIConversation, AIMessage
from app.core.security import hash_password, create_access_token
from app.core.datetime_utils import get_today_date
from app.ai.tools import execute_tool

# Setup Test Database Engine
engine = create_engine(
    f"sqlite:///{TEST_DB_FILE}",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


class TestPhase7AIAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = TestingSessionLocal()

        today = get_today_date()

        # 1. Create Users
        cls.planner = User(
            full_name="Phase7 Lead Planner",
            email="planner7@example.com",
            hashed_password=hash_password("Password123!"),
            role="PLANNER",
            is_active=True,
        )
        cls.other_planner = User(
            full_name="Phase7 Other Planner",
            email="otherplanner7@example.com",
            hashed_password=hash_password("Password123!"),
            role="PLANNER",
            is_active=True,
        )
        cls.civil_sup = User(
            full_name="Phase7 Civil Supervisor",
            email="civil7@example.com",
            hashed_password=hash_password("Password123!"),
            role="SUPERVISOR",
            is_active=True,
        )
        cls.piping_sup = User(
            full_name="Phase7 Piping Supervisor",
            email="piping7@example.com",
            hashed_password=hash_password("Password123!"),
            role="SUPERVISOR",
            is_active=True,
        )
        cls.unassigned_sup = User(
            full_name="Phase7 Unassigned Supervisor",
            email="unassigned7@example.com",
            hashed_password=hash_password("Password123!"),
            role="SUPERVISOR",
            is_active=True,
        )
        db.add_all([cls.planner, cls.other_planner, cls.civil_sup, cls.piping_sup, cls.unassigned_sup])
        db.commit()

        # Tokens
        cls.planner_token = create_access_token(cls.planner.id)
        cls.other_planner_token = create_access_token(cls.other_planner.id)
        cls.civil_token = create_access_token(cls.civil_sup.id)
        cls.piping_token = create_access_token(cls.piping_sup.id)
        cls.unassigned_token = create_access_token(cls.unassigned_sup.id)

        # 2. Create Project
        cls.project = Project(
            name="Refinery Expansion AI Test",
            project_code="PRJ-AI-700",
            description="Testing Phase 7 AI Assistant",
            location="Jamnagar Refinery",
            planned_start_date=today - timedelta(days=10),
            planned_end_date=today + timedelta(days=30),
            status="ACTIVE",
            created_by_id=cls.planner.id,
        )
        db.add(cls.project)
        db.commit()

        # 3. Add Memberships
        cls.mem_civil = ProjectMember(
            project_id=cls.project.id,
            user_id=cls.civil_sup.id,
            discipline="CIVIL",
        )
        cls.mem_piping = ProjectMember(
            project_id=cls.project.id,
            user_id=cls.piping_sup.id,
            discipline="PIPING",
        )
        db.add_all([cls.mem_civil, cls.mem_piping])
        db.commit()

        # 4. Create Activities & Executions
        act1 = Activity(
            project_id=cls.project.id,
            activity_code="ACT-CIV-001",
            activity_name="Excavation & Foundation",
            discipline="CIVIL",
            planned_start=today - timedelta(days=10),
            planned_finish=today - timedelta(days=2),
            planned_duration=8,
            wbs_code="1.1",
        )
        act2 = Activity(
            project_id=cls.project.id,
            activity_code="ACT-CIV-002",
            activity_name="Concrete Pouring",
            discipline="CIVIL",
            planned_start=today - timedelta(days=1),
            planned_finish=today + timedelta(days=3),
            planned_duration=4,
            wbs_code="1.2",
        )
        act3 = Activity(
            project_id=cls.project.id,
            activity_code="ACT-PIP-001",
            activity_name="Main Header Erection",
            discipline="PIPING",
            planned_start=today - timedelta(days=3),
            planned_finish=today + timedelta(days=4),
            planned_duration=7,
            wbs_code="2.1",
        )
        act4 = Activity(
            project_id=cls.project.id,
            activity_code="ACT-PIP-002",
            activity_name="Pressure Hydrotest",
            discipline="PIPING",
            planned_start=today - timedelta(days=8),
            planned_finish=today - timedelta(days=4),
            planned_duration=4,
            wbs_code="2.2",
        )

        db.add_all([act1, act2, act3, act4])
        db.commit()

        # Executions
        exec1 = ActivityExecution(
            project_id=cls.project.id,
            activity_id=act1.id,
            actual_start=today - timedelta(days=9),
            actual_finish=None,
            progress_percentage=40.0,
            execution_status="IN_PROGRESS",
        )
        exec2 = ActivityExecution(
            project_id=cls.project.id,
            activity_id=act2.id,
            actual_start=today,
            actual_finish=None,
            progress_percentage=20.0,
            execution_status="IN_PROGRESS",
        )
        exec3 = ActivityExecution(
            project_id=cls.project.id,
            activity_id=act3.id,
            actual_start=today - timedelta(days=2),
            actual_finish=None,
            progress_percentage=50.0,
            execution_status="IN_PROGRESS",
        )
        exec4 = ActivityExecution(
            project_id=cls.project.id,
            activity_id=act4.id,
            actual_start=today - timedelta(days=8),
            actual_finish=today - timedelta(days=4),
            progress_percentage=100.0,
            execution_status="COMPLETED",
        )
        db.add_all([exec1, exec2, exec3, exec4])
        db.commit()

        # Progress Update Audit Log for ACT-CIV-001
        upd1 = ProgressUpdate(
            project_id=cls.project.id,
            activity_id=act1.id,
            reported_by_id=cls.civil_sup.id,
            update_type="PROGRESS",
            reported_date=today - timedelta(days=1),
            progress_percentage=40.0,
            remarks="40% excavated despite heavy rain",
            source_type="FIELD_SUPERVISOR",
        )
        db.add(upd1)
        db.commit()

        cls.project_id = cls.project.id
        cls.act1_id = act1.id
        cls.act2_id = act2.id
        cls.act3_id = act3.id
        cls.act4_id = act4.id
        db.close()

    def test_01_database_preservation(self):
        """1. Database structure and tables are preserved."""
        db = TestingSessionLocal()
        projs = db.query(Project).all()
        acts = db.query(Activity).all()
        self.assertGreaterEqual(len(projs), 1)
        self.assertGreaterEqual(len(acts), 4)
        db.close()

    def test_02_planner_ai_chat_general_overview(self):
        """2. Planner queries project overview -> receives overview statistics."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "Give me an overview of project status"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("conversation_id", data)
        self.assertIn("Refinery Expansion", data["assistant_message"]["content"])
        self.assertTrue(len(data["sources"]) > 0)

    def test_03_supervisor_discipline_scoping_today_work(self):
        """3. Civil Supervisor asks for today's work -> receives only CIVIL activities."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "What is scheduled for today?"},
            headers={"Authorization": f"Bearer {self.civil_token}"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.json()["assistant_message"]["content"]
        self.assertIn("ACT-CIV-002", content)
        self.assertNotIn("ACT-PIP-001", content)

    def test_04_supervisor_discipline_scoping_overdue(self):
        """4. Civil Supervisor asks for overdue -> receives CIVIL overdue activities."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "List overdue activities"},
            headers={"Authorization": f"Bearer {self.civil_token}"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.json()["assistant_message"]["content"]
        self.assertIn("ACT-CIV-001", content)

    def test_05_upcoming_deadlines_lookahead(self):
        """5. Planner asks for upcoming deadlines -> receives activities due within 7 days."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "Show upcoming deadlines for next week"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.json()["assistant_message"]["content"]
        self.assertIn("ACT-PIP-001", content)

    def test_06_activity_details_lookup(self):
        """6. Planner queries ACT-CIV-001 details -> returns full activity details."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "What is the status of ACT-CIV-001?"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.json()["assistant_message"]["content"]
        self.assertIn("Excavation & Foundation", content)
        self.assertIn("40", content)

    def test_07_activity_progress_history_lookup(self):
        """7. Query progress audit history for ACT-CIV-001 via tool direct call."""
        db = TestingSessionLocal()
        res = execute_tool(db, self.project_id, "PLANNER", None, "get_activity_progress_history", {"activity_code": "ACT-CIV-001"})
        self.assertEqual(res["activity_code"], "ACT-CIV-001")
        self.assertEqual(res["total_updates"], 1)
        self.assertIn("40% excavated", res["history"][0]["remarks"])
        db.close()

    def test_08_discipline_progress_summary(self):
        """8. Query discipline progress breakdown -> returns CIVIL and PIPING summaries."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "Give me discipline progress breakdown"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.json()["assistant_message"]["content"]
        self.assertIn("CIVIL", content)
        self.assertIn("PIPING", content)

    def test_09_recent_progress_updates_audit(self):
        """9. Query recent updates -> returns audit logs."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "Show recent site updates and audit logs"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.json()["assistant_message"]["content"]
        self.assertIn("Phase7 Civil Supervisor", content)

    def test_10_general_knowledge_refusal(self):
        """10. Out-of-scope question receives standard refusal message."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "What is the capital of France?"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.json()["assistant_message"]["content"]
        self.assertIn("I can only assist with information related to the currently selected infrastructure project", content)

    def test_11_read_only_mandate(self):
        """11. AI operations do NOT modify any database records."""
        db = TestingSessionLocal()
        act_before = db.query(ActivityExecution).filter(ActivityExecution.activity_id == self.act1_id).first()
        prog_before = act_before.progress_percentage

        client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "Mark ACT-CIV-001 as 100% completed"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )

        db.refresh(act_before)
        self.assertEqual(act_before.progress_percentage, prog_before)
        db.close()

    def test_12_conversation_creation_and_persistence(self):
        """12. Chat request without conversation_id creates and persists a conversation."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "How is the project progressing overall?"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        cid = response.json()["conversation_id"]
        self.assertIsNotNone(cid)

        # Check DB
        db = TestingSessionLocal()
        conv = db.query(AIConversation).filter(AIConversation.id == cid).first()
        self.assertIsNotNone(conv)
        self.assertEqual(len(conv.messages), 2)
        db.close()

    def test_13_conversation_continuation(self):
        """13. Passing conversation_id appends messages to existing conversation."""
        res1 = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "First message in thread"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        ).json()
        cid = res1["conversation_id"]

        res2 = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"conversation_id": cid, "prompt": "Second follow-up message"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(res2.status_code, 200)

        db = TestingSessionLocal()
        conv = db.query(AIConversation).filter(AIConversation.id == cid).first()
        self.assertEqual(len(conv.messages), 4)
        db.close()

    def test_14_list_user_conversations(self):
        """14. GET /api/projects/{id}/ai/conversations lists conversations."""
        response = client.get(
            f"/api/projects/{self.project_id}/ai/conversations",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        convs = response.json()
        self.assertGreaterEqual(len(convs), 1)

    def test_15_get_conversation_detail(self):
        """15. GET /api/projects/{id}/ai/conversations/{cid} gets full message history."""
        res1 = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "Detail test message"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        ).json()
        cid = res1["conversation_id"]

        response = client.get(
            f"/api/projects/{self.project_id}/ai/conversations/{cid}",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], cid)
        self.assertGreaterEqual(len(data["messages"]), 2)

    def test_16_delete_conversation(self):
        """16. DELETE /api/projects/{id}/ai/conversations/{cid} removes conversation."""
        res1 = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "Conversation to delete"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        ).json()
        cid = res1["conversation_id"]

        del_res = client.delete(
            f"/api/projects/{self.project_id}/ai/conversations/{cid}",
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(del_res.status_code, 200)

        db = TestingSessionLocal()
        conv = db.query(AIConversation).filter(AIConversation.id == cid).first()
        self.assertIsNone(conv)
        db.close()

    def test_17_unassigned_supervisor_rbac(self):
        """17. Unassigned supervisor gets 403 Forbidden."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "Can I see project status?"},
            headers={"Authorization": f"Bearer {self.unassigned_token}"},
        )
        self.assertEqual(response.status_code, 403)

    def test_18_unassigned_planner_rbac(self):
        """18. Non-owner planner gets 403 Forbidden."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "Can I see project status?"},
            headers={"Authorization": f"Bearer {self.other_planner_token}"},
        )
        self.assertEqual(response.status_code, 403)

    def test_19_invalid_conversation_id(self):
        """19. Non-existent conversation ID returns 404 Not Found."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"conversation_id": 99999, "prompt": "Invalid conv test"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 404)

    def test_20_empty_prompt_validation(self):
        """20. Empty string prompt returns 422 Unprocessable Entity."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": ""},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 422)

    def test_21_search_activities_tool(self):
        """21. search_activities tool returns accurate search results."""
        db = TestingSessionLocal()
        res = execute_tool(db, self.project_id, "PLANNER", None, "search_activities", {"query": "Hydrotest"})
        self.assertEqual(res["count"], 1)
        self.assertEqual(res["activities"][0]["activity_code"], "ACT-PIP-002")
        db.close()

    def test_22_tool_execution_sources_metadata(self):
        """22. Response contains sources metadata array."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "Which activities are overdue?"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        sources = response.json()["sources"]
        self.assertTrue(any(s["tool"] == "get_overdue_activities" for s in sources))

    def test_24_get_project_team_tool(self):
        """24. get_project_team tool returns accurate supervisor count and members."""
        db = TestingSessionLocal()
        res = execute_tool(db, self.project_id, "PLANNER", None, "get_project_team", {})
        self.assertIn("supervisor_count", res)
        self.assertEqual(res["supervisor_count"], 2)
        self.assertIn("members", res)
        self.assertTrue(any(m["role"] == "SUPERVISOR" for m in res["members"]))
        db.close()

    def test_25_team_chat_query_routing(self):
        """25. Team queries return project supervisor count and members instead of 0 activity search."""
        response = client.post(
            f"/api/projects/{self.project_id}/ai/chat",
            json={"prompt": "How many supervisors are assigned?"},
            headers={"Authorization": f"Bearer {self.planner_token}"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.json()["assistant_message"]["content"]
        self.assertIn("Assigned Supervisors", content)
        sources = response.json()["sources"]
        self.assertTrue(any(s["tool"] == "get_project_team" for s in sources))


if __name__ == "__main__":
    unittest.main()


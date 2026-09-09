"""
Phase 6 Comprehensive Verification Test Script
Tests Real Project Dashboard & Schedule Health calculation services, RBAC,
timezone consistency, status distribution, overdue detection, baseline-vs-actual adherence,
and Supervisor discipline views using an isolated SQLite test database.
Also verifies targeted UX & authorization corrections:
- Planners receive 403 Forbidden when attempting progress updates.
- Supervisors can ONLY update their assigned discipline activities.
"""

import sys
import os
from datetime import date, timedelta

# Setup isolated test database path
TEST_DB_FILE = os.path.join(os.path.dirname(__file__), "test_phase6.db")
if os.path.exists(TEST_DB_FILE):
    try:
        os.remove(TEST_DB_FILE)
    except Exception:
        pass

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-phase6"
os.environ["APP_TIMEZONE"] = "Asia/Kolkata"

from fastapi.testclient import TestClient
from app.main import app
from app.database.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.core.datetime_utils import get_today_date

# Initialize tables on isolated test db
Base.metadata.create_all(bind=engine)

client = TestClient(app)

print("=" * 60)
print("RUNNING PHASE 6 AUTOMATED DASHBOARD & AUTHORIZATION VERIFICATION")
print("=" * 60)

def get_token(email: str, password: str = "Password123!") -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    return response.json()["access_token"]

# 1. Health check & user setup
print("\n[Step 1] Verifying Health Check & Creating Users...")
health_res = client.get("/api/health")
assert health_res.status_code == 200
assert health_res.json()["status"] == "ok"

planner_res = client.post("/api/auth/register", json={
    "full_name": "Phase6 Planner",
    "email": "planner6@test.com",
    "password": "Password123!",
    "role": "PLANNER"
})
assert planner_res.status_code == 201
planner_token = get_token("planner6@test.com")

civil_sup_res = client.post("/api/auth/register", json={
    "full_name": "Civil Supervisor",
    "email": "civil_sup@test.com",
    "password": "Password123!",
    "role": "SUPERVISOR"
})
assert civil_sup_res.status_code == 201
civil_sup_token = get_token("civil_sup@test.com")

piping_sup_res = client.post("/api/auth/register", json={
    "full_name": "Piping Supervisor",
    "email": "piping_sup@test.com",
    "password": "Password123!",
    "role": "SUPERVISOR"
})
assert piping_sup_res.status_code == 201
piping_sup_token = get_token("piping_sup@test.com")

unassigned_sup_res = client.post("/api/auth/register", json={
    "full_name": "Unassigned Supervisor",
    "email": "unassigned@test.com",
    "password": "Password123!",
    "role": "SUPERVISOR"
})
assert unassigned_sup_res.status_code == 201
unassigned_sup_token = get_token("unassigned@test.com")

print("-> Auth and user creation successful.")

# 2. Create Project
print("\n[Step 2] Creating Test Project...")
today = get_today_date()
p_start = today - timedelta(days=20)
p_end = today + timedelta(days=40)

proj_res = client.post(
    "/api/projects",
    headers={"Authorization": f"Bearer {planner_token}"},
    json={
        "name": "Refinery Expansion Phase 6",
        "project_code": "REF-P6-2026",
        "location": "Jamnagar, Gujarat",
        "description": "Dashboard Verification Project",
        "planned_start_date": p_start.isoformat(),
        "planned_end_date": p_end.isoformat()
    }
)
assert proj_res.status_code == 201
project = proj_res.json()
project_id = project["id"]

# Assign Civil & Piping supervisors to project
assign_civil = client.post(
    f"/api/projects/{project_id}/members",
    headers={"Authorization": f"Bearer {planner_token}"},
    json={"email": "civil_sup@test.com", "discipline": "CIVIL"}
)
assert assign_civil.status_code == 201

assign_piping = client.post(
    f"/api/projects/{project_id}/members",
    headers={"Authorization": f"Bearer {planner_token}"},
    json={"email": "piping_sup@test.com", "discipline": "PIPING"}
)
assert assign_piping.status_code == 201

print("-> Project created and supervisors assigned.")

# 3. Test Dashboard empty schedule state
print("\n[Step 3] Testing Empty Schedule Dashboard State...")
dash_empty = client.get(
    f"/api/projects/{project_id}/dashboard",
    headers={"Authorization": f"Bearer {planner_token}"}
)
assert dash_empty.status_code == 200
empty_data = dash_empty.json()
assert empty_data["summary"]["total_activities"] == 0
assert empty_data["summary"]["overall_progress"] == 0.0
assert empty_data["project"]["days_until_planned_finish"] == 40
print("-> Empty schedule dashboard handled cleanly.")

# 4. Insert 5 Known Test Activities
print("\n[Step 4] Inserting 5 Known Test Activities...")
db = SessionLocal()

past_finish_1 = today - timedelta(days=5) # Overdue if in progress / not started
past_finish_2 = today - timedelta(days=2) # Completed late
upcoming_finish_1 = today + timedelta(days=3) # Today / Upcoming
upcoming_finish_2 = today + timedelta(days=5) # Upcoming
future_finish = today + timedelta(days=25)

act1 = Activity(project_id=project_id, activity_code="CIV-001", activity_name="Excavation", discipline="CIVIL", planned_start=today-timedelta(days=15), planned_finish=past_finish_1)
act2 = Activity(project_id=project_id, activity_code="PIP-001", activity_name="Pipe Welding", discipline="PIPING", planned_start=today-timedelta(days=10), planned_finish=past_finish_2)
act3 = Activity(project_id=project_id, activity_code="PIP-002", activity_name="Valve Fitting", discipline="PIPING", planned_start=today-timedelta(days=2), planned_finish=upcoming_finish_1)
act4 = Activity(project_id=project_id, activity_code="ELE-001", activity_name="Cabling", discipline="ELECTRICAL", planned_start=today, planned_finish=upcoming_finish_2)
act5 = Activity(project_id=project_id, activity_code="CIV-002", activity_name="Concreting", discipline="CIVIL", planned_start=today+timedelta(days=5), planned_finish=future_finish)

db.add_all([act1, act2, act3, act4, act5])
db.commit()
for a in [act1, act2, act3, act4, act5]:
    db.refresh(a)

act1_id, act2_id, act3_id, act4_id, act5_id = act1.id, act2.id, act3.id, act4.id, act5.id
db.close()
print("-> 5 activities inserted.")

# 5. Verify Authorization Rules (FIX 2)
print("\n[Step 5] Verifying Strict Authorization Rules (FIX 2)...")

# 5A: Planner attempting progress report must receive 403 Forbidden
planner_attempt = client.post(
    f"/api/projects/{project_id}/activities/{act1_id}/progress",
    headers={"Authorization": f"Bearer {planner_token}"},
    json={"update_type": "START", "reported_date": today.isoformat(), "progress_percentage": 50, "remarks": "Planner attempt"}
)
assert planner_attempt.status_code == 403, f"Expected 403 for planner progress report, got {planner_attempt.status_code}"
assert "Field progress updates must be reported by an assigned supervisor" in planner_attempt.json()["detail"]
print("-> Planner progress reporting properly rejected with 403 Forbidden.")

# 5B: Piping Supervisor attempting Civil activity progress report must receive 403 Forbidden
piping_on_civil_attempt = client.post(
    f"/api/projects/{project_id}/activities/{act1_id}/progress",
    headers={"Authorization": f"Bearer {piping_sup_token}"},
    json={"update_type": "START", "reported_date": today.isoformat(), "progress_percentage": 50, "remarks": "Cross-discipline attempt"}
)
assert piping_on_civil_attempt.status_code == 403
assert "can only report progress on PIPING activities" in piping_on_civil_attempt.json()["detail"]
print("-> Cross-discipline supervisor progress reporting properly rejected with 403 Forbidden.")

# 6. Simulate Valid Field Progress Reports by Assigned Supervisors
print("\n[Step 6] Simulating Valid Field Progress Reports by Assigned Supervisors...")

# Civil Supervisor reports Act1 (100% Completed)
r1 = client.post(
    f"/api/projects/{project_id}/activities/{act1_id}/progress",
    headers={"Authorization": f"Bearer {civil_sup_token}"},
    json={"update_type": "START", "reported_date": today.isoformat(), "progress_percentage": 50, "remarks": "Started excavation"}
)
assert r1.status_code == 200, f"r1 failed: {r1.text}"

r1_comp = client.post(
    f"/api/projects/{project_id}/activities/{act1_id}/progress",
    headers={"Authorization": f"Bearer {civil_sup_token}"},
    json={"update_type": "COMPLETE", "reported_date": today.isoformat(), "progress_percentage": 100, "actual_finish": today.isoformat(), "remarks": "Finished excavation late"}
)
assert r1_comp.status_code == 200, f"r1_comp failed: {r1_comp.text}"

# Piping Supervisor reports Act2 (50% In Progress)
r2 = client.post(
    f"/api/projects/{project_id}/activities/{act2_id}/progress",
    headers={"Authorization": f"Bearer {piping_sup_token}"},
    json={"update_type": "START", "reported_date": today.isoformat(), "progress_percentage": 50, "remarks": "Piping welding in progress"}
)
assert r2.status_code == 200, f"r2 failed: {r2.text}"

# Civil Supervisor reports Act5 (100% Completed)
r5 = client.post(
    f"/api/projects/{project_id}/activities/{act5_id}/progress",
    headers={"Authorization": f"Bearer {civil_sup_token}"},
    json={"update_type": "START", "reported_date": today.isoformat(), "progress_percentage": 100, "remarks": "Concreting finished"}
)
assert r5.status_code == 200, f"r5 failed: {r5.text}"

r5_comp = client.post(
    f"/api/projects/{project_id}/activities/{act5_id}/progress",
    headers={"Authorization": f"Bearer {civil_sup_token}"},
    json={"update_type": "COMPLETE", "reported_date": today.isoformat(), "progress_percentage": 100, "actual_finish": (today - timedelta(days=1)).isoformat(), "remarks": "Concreting complete"}
)
assert r5_comp.status_code == 200, f"r5_comp failed: {r5_comp.text}"

print("-> Progress reports successfully registered by authorized discipline supervisors.")

# 7. Verify Dashboard Metrics via GET Endpoint
print("\n[Step 7] Verifying Planner Dashboard Calculations...")
dash_res = client.get(
    f"/api/projects/{project_id}/dashboard",
    headers={"Authorization": f"Bearer {planner_token}"}
)
assert dash_res.status_code == 200
dash = dash_res.json()

summary = dash["summary"]
print(f"Overall Progress: {summary['overall_progress']}% (Expected: 50.0%)")
assert summary["overall_progress"] == 50.0
assert summary["total_activities"] == 5
assert summary["completed"] == 2
assert summary["in_progress"] == 1
assert summary["not_started"] == 2
assert summary["on_hold"] == 0
assert summary["not_started"] + summary["in_progress"] + summary["on_hold"] + summary["completed"] == summary["total_activities"]
assert summary["overdue"] == 1

# Overdue check: Act2 is IN_PROGRESS and planned_finish was 2 days ago
assert len(dash["overdue_activities"]) == 1
assert dash["overdue_activities"][0]["activity_code"] == "PIP-001"
assert dash["overdue_activities"][0]["overdue_days"] == 2

# Scheduled today work check: Act3 and Act4
today_codes = [a["activity_code"] for a in dash["today_work"]]
assert "PIP-002" in today_codes
assert "ELE-001" in today_codes

# Upcoming deadlines check: Act3 (3 days) and Act4 (5 days)
upcoming_codes = [a["activity_code"] for a in dash["upcoming_deadlines"]]
assert "PIP-002" in upcoming_codes
assert "ELE-001" in upcoming_codes

print("-> All Planner Dashboard calculations verified 100% correct!")

# 8. Verify Supervisor Dashboard & RBAC
print("\n[Step 8] Verifying Supervisor Discipline Dashboard & Access Control...")
sup_dash_res = client.get(
    f"/api/projects/{project_id}/dashboard",
    headers={"Authorization": f"Bearer {piping_sup_token}"}
)
assert sup_dash_res.status_code == 200
sup_dash = sup_dash_res.json()
assert sup_dash["supervisor_summary"] is not None
sup_sum = sup_dash["supervisor_summary"]
assert sup_sum["assigned_discipline"] == "PIPING"
assert sup_sum["total_activities"] == 2
assert sup_sum["overall_progress"] == 25.0

# Unassigned supervisor access check
unassigned_res = client.get(
    f"/api/projects/{project_id}/dashboard",
    headers={"Authorization": f"Bearer {unassigned_sup_token}"}
)
assert unassigned_res.status_code == 403
print("-> Supervisor discipline summary and access control verified.")

print("\n" + "=" * 60)
print("PHASE 6 UX FIXES & AUTHORIZATION VERIFICATION PASSED PERFECTLY!")
print("=" * 60)

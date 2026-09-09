"""
Phase 5 Comprehensive Verification Test Script
Tests Actual Progress Tracking Foundation, Discipline RBAC, State Machine Rules, Baseline Immutability,
Audit Trail, and Execution Summary metrics against an isolated SQLite test database.
"""

import sys
import os
from datetime import date, datetime

# Setup isolated test database path
TEST_DB_FILE = os.path.join(os.path.dirname(__file__), "test_phase5.db")
if os.path.exists(TEST_DB_FILE):
    try:
        os.remove(TEST_DB_FILE)
    except Exception:
        pass

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-phase5"

from fastapi.testclient import TestClient
from app.main import app
from app.database.database import Base, engine, SessionLocal
from app.models.user import User

from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate

# Initialize tables
Base.metadata.create_all(bind=engine)

client = TestClient(app)

print("=" * 60)
print("RUNNING PHASE 5 COMPREHENSIVE AUTOMATED VERIFICATION")
print("=" * 60)

# Helper function to get token
def get_token(email: str, password: str = "Password123!") -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    return response.json()["access_token"]

# 1. Setup Users
print("\n[Step 1] Creating Test Users...")
reg_planner = client.post("/api/auth/register", json={
    "full_name": "Planner Lead",
    "email": "planner@test.com",
    "password": "Password123!",
    "role": "PLANNER"
})
assert reg_planner.status_code == 201
planner_token = get_token("planner@test.com")

reg_civil_sup = client.post("/api/auth/register", json={
    "full_name": "Civil Supervisor",
    "email": "civil_sup@test.com",
    "password": "Password123!",
    "role": "SUPERVISOR"
})
assert reg_civil_sup.status_code == 201
civil_token = get_token("civil_sup@test.com")

reg_piping_sup = client.post("/api/auth/register", json={
    "full_name": "Piping Supervisor",
    "email": "piping_sup@test.com",
    "password": "Password123!",
    "role": "SUPERVISOR"
})
assert reg_piping_sup.status_code == 201
piping_token = get_token("piping_sup@test.com")

print("[OK] Users registered successfully.")

# 2. Setup Project & Assign Disciplines
print("\n[Step 2] Creating Project & Assigning Supervisor Disciplines...")
proj_res = client.post("/api/projects", json={
    "project_code": "PRJ-PH5",
    "name": "Phase 5 Progress Test Refinery",
    "location": "Jamnagar",
    "planned_start_date": "2026-10-01",
    "planned_end_date": "2026-10-31",
    "description": "Verification project for actual progress tracking"
}, headers={"Authorization": f"Bearer {planner_token}"})
assert proj_res.status_code == 201
project_id = proj_res.json()["id"]

# Assign Civil Supervisor with CIVIL discipline
assign_civil = client.post(f"/api/projects/{project_id}/members", json={
    "email": "civil_sup@test.com",
    "discipline": "CIVIL"
}, headers={"Authorization": f"Bearer {planner_token}"})
assert assign_civil.status_code == 201

# Assign Piping Supervisor with PIPING discipline
assign_piping = client.post(f"/api/projects/{project_id}/members", json={
    "email": "piping_sup@test.com",
    "discipline": "PIPING"
}, headers={"Authorization": f"Bearer {planner_token}"})
assert assign_piping.status_code == 201

print(f"[OK] Project ID {project_id} created and supervisors assigned.")

# 3. Setup Baseline Activities
print("\n[Step 3] Creating Baseline Schedule Activities...")
db = SessionLocal()
act_civil = Activity(
    project_id=project_id,
    activity_code="CIV-101",
    activity_name="Excavation & Foundation Pouring",
    discipline="CIVIL",
    planned_start=date(2026, 10, 1),
    planned_finish=date(2026, 10, 15),
    planned_duration=14.0,
    wbs_code="1.1",
    wbs_name="Civil Works",
    schedule_level="L5"
)
act_piping = Activity(
    project_id=project_id,
    activity_code="PIP-201",
    activity_name="Main Rack Piping Erection",
    discipline="PIPING",
    planned_start=date(2026, 10, 10),
    planned_finish=date(2026, 10, 25),
    planned_duration=15.0,
    wbs_code="1.2",
    wbs_name="Piping Works",
    schedule_level="L5"
)
act_unas = Activity(
    project_id=project_id,
    activity_code="UNA-301",
    activity_name="General Site Cleaning",
    discipline="UNASSIGNED",
    planned_start=date(2026, 10, 5),
    planned_finish=date(2026, 10, 20),
    planned_duration=15.0,
    wbs_code="1.3",
    wbs_name="General Works",
    schedule_level="L6"
)
db.add_all([act_civil, act_piping, act_unas])
db.commit()

civil_act_id = act_civil.id
piping_act_id = act_piping.id
unas_act_id = act_unas.id
db.close()

print(f"[OK] Activities created: CIV-101 ({civil_act_id}), PIP-201 ({piping_act_id}), UNA-301 ({unas_act_id}).")

# 4. Verify Discipline RBAC Authorization Rules
print("\n[Step 4] Testing Discipline RBAC Authorization...")

# Civil supervisor trying to update PIPING activity -> 403 Forbidden
res_rbac_1 = client.post(f"/api/projects/{project_id}/activities/{piping_act_id}/progress", json={
    "update_type": "START",
    "reported_date": "2026-10-10"
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_rbac_1.status_code == 403, f"Expected 403, got {res_rbac_1.status_code}"
print("[OK] Civil supervisor blocked from updating Piping activity (HTTP 403).")

# Civil supervisor trying to update UNASSIGNED activity -> 403 Forbidden
res_rbac_2 = client.post(f"/api/projects/{project_id}/activities/{unas_act_id}/progress", json={
    "update_type": "START",
    "reported_date": "2026-10-05"
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_rbac_2.status_code == 403, f"Expected 403, got {res_rbac_2.status_code}"
print("[OK] Civil supervisor blocked from updating Unassigned activity (HTTP 403).")

# Civil supervisor updating CIVIL activity -> 200 OK
res_rbac_3 = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "START",
    "reported_date": "2026-10-01",
    "remarks": "Site mobilized and excavation started."
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_rbac_3.status_code == 200, f"Expected 200, got {res_rbac_3.status_code}: {res_rbac_3.text}"
print("[OK] Civil supervisor allowed to START Civil activity (HTTP 200).")

# Planner owner updating UNASSIGNED activity -> 200 OK
res_planner_override = client.post(f"/api/projects/{project_id}/activities/{unas_act_id}/progress", json={
    "update_type": "START",
    "reported_date": "2026-10-05",
    "remarks": "Planner override start for general work."
}, headers={"Authorization": f"Bearer {planner_token}"})
assert res_planner_override.status_code == 200
print("[OK] Managing Planner allowed to update Unassigned activity (HTTP 200).")

# 5. Verify State Machine Rules & Validations
print("\n[Step 5] Testing State Machine Transitions & Validation Rules...")

# Rule A: PROGRESS update requires positive percentage > current (current is 0%)
res_invalid_prog1 = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "PROGRESS",
    "reported_date": "2026-10-03",
    "progress_percentage": 0.0
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_invalid_prog1.status_code == 400
print("[OK] Rejected PROGRESS update with 0% progress (HTTP 400).")

# Rule B: Valid PROGRESS update to 25%
res_prog_25 = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "PROGRESS",
    "reported_date": "2026-10-04",
    "progress_percentage": 25.0,
    "remarks": "Trenching 25% complete"
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_prog_25.status_code == 200
assert res_prog_25.json()["progress_percentage"] == 25.0
assert res_prog_25.json()["execution_status"] == "IN_PROGRESS"
print("[OK] Applied valid PROGRESS update to 25% (HTTP 200).")

# Rule C: PROGRESS update with lower/equal percentage (20% <= 25%)
res_invalid_prog2 = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "PROGRESS",
    "reported_date": "2026-10-05",
    "progress_percentage": 20.0
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_invalid_prog2.status_code == 400
print("[OK] Rejected PROGRESS update with lower percentage 20% < 25% (HTTP 400).")

# Rule D: Valid PROGRESS update to 60%
res_prog_60 = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "PROGRESS",
    "reported_date": "2026-10-06",
    "progress_percentage": 60.0,
    "remarks": "Foundation rebar binding in progress"
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_prog_60.status_code == 200
assert res_prog_60.json()["progress_percentage"] == 60.0
print("[OK] Applied valid PROGRESS update to 60% (HTTP 200).")

# Rule E: Transition to ON_HOLD
res_hold = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "ON_HOLD",
    "reported_date": "2026-10-07",
    "remarks": "Delayed due to heavy monsoon rain"
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_hold.status_code == 200
assert res_hold.json()["execution_status"] == "ON_HOLD"
assert res_hold.json()["progress_percentage"] == 60.0
print("[OK] Transitioned activity to ON_HOLD while preserving 60% progress (HTTP 200).")

# Rule F: PROGRESS update while ON_HOLD -> 400 Bad Request
res_invalid_hold_prog = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "PROGRESS",
    "reported_date": "2026-10-08",
    "progress_percentage": 70.0
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_invalid_hold_prog.status_code == 400
print("[OK] Rejected PROGRESS update while activity is ON_HOLD (HTTP 400).")

# Rule G: Transition RESUME
res_resume = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "RESUME",
    "reported_date": "2026-10-09",
    "remarks": "Site dewatered, work resumed"
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_resume.status_code == 200
assert res_resume.json()["execution_status"] == "IN_PROGRESS"
print("[OK] Transitioned activity RESUME back to IN_PROGRESS (HTTP 200).")

# Rule H: COMPLETE with actual_finish before actual_start -> 400 Bad Request
res_invalid_finish = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "COMPLETE",
    "reported_date": "2026-09-25",
    "remarks": "Invalid finish date"
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_invalid_finish.status_code == 400
print("[OK] Rejected COMPLETE date prior to actual_start (HTTP 400).")

# Rule I: Transition to COMPLETE
res_complete = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "COMPLETE",
    "reported_date": "2026-10-14",
    "remarks": "Foundation completed and signed off"
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_complete.status_code == 200
assert res_complete.json()["execution_status"] == "COMPLETED"
assert res_complete.json()["progress_percentage"] == 100.0
assert res_complete.json()["actual_finish"] == "2026-10-14"
print("[OK] Transitioned activity to COMPLETE with 100% progress & actual_finish (HTTP 200).")

# Rule J: Updating progress on COMPLETED activity -> 400 Bad Request
res_invalid_completed = client.post(f"/api/projects/{project_id}/activities/{civil_act_id}/progress", json={
    "update_type": "PROGRESS",
    "reported_date": "2026-10-15",
    "progress_percentage": 100.0
}, headers={"Authorization": f"Bearer {civil_token}"})
assert res_invalid_completed.status_code == 400
print("[OK] Rejected update on COMPLETED activity (HTTP 400).")

# 6. Verify Baseline Date Immutability
print("\n[Step 6] Verifying Baseline Planned Date Immutability...")
db = SessionLocal()
act_check = db.query(Activity).filter(Activity.id == civil_act_id).first()
assert act_check.planned_start == date(2026, 10, 1), f"Planned start mutated! {act_check.planned_start}"
assert act_check.planned_finish == date(2026, 10, 15), f"Planned finish mutated! {act_check.planned_finish}"
db.close()
print("[OK] Baseline planned dates remain 100% untouched & immutable.")

# 7. Verify Audit History
print("\n[Step 7] Checking Progress Audit Trail Endpoint...")
res_history = client.get(
    f"/api/projects/{project_id}/activities/{civil_act_id}/progress-history",
    headers={"Authorization": f"Bearer {civil_token}"}
)
assert res_history.status_code == 200
history_items = res_history.json()
assert len(history_items) == 6  # START, PROGRESS(25), PROGRESS(60), ON_HOLD, RESUME, COMPLETE
assert history_items[0]["update_type"] == "COMPLETE"
assert history_items[-1]["update_type"] == "START"
assert history_items[0]["reported_by_name"] == "Civil Supervisor"
print(f"[OK] Returned {len(history_items)} audit trail records in correct chronological order.")

# 8. Verify Execution Summary Metrics
print("\n[Step 8] Checking Execution Summary Metrics Endpoint...")
res_summary = client.get(
    f"/api/projects/{project_id}/execution-summary",
    headers={"Authorization": f"Bearer {planner_token}"}
)
assert res_summary.status_code == 200
summary_data = res_summary.json()
assert summary_data["total_activities"] == 3
assert summary_data["completed"] == 1       # CIV-101
assert summary_data["in_progress"] == 1     # UNA-301 (started)
assert summary_data["not_started"] == 1     # PIP-201
# Average progress calculation: CIV-101 (100) + UNA-301 (0) + PIP-201 (0) = 100 / 3 = 33.33%
assert abs(summary_data["average_progress"] - 33.33) < 0.1
print(f"[OK] Summary Metrics verified: Total={summary_data['total_activities']}, Completed={summary_data['completed']}, InProgress={summary_data['in_progress']}, NotStarted={summary_data['not_started']}, AvgProgress={summary_data['average_progress']}%.")

# 9. Verify Schedule List API Join
print("\n[Step 9] Checking Activity Listing Endpoint Execution Data Join...")
res_act_list = client.get(
    f"/api/projects/{project_id}/activities",
    headers={"Authorization": f"Bearer {civil_token}"}
)
assert res_act_list.status_code == 200
items = res_act_list.json()["items"]
civ_item = next(i for i in items if i["id"] == civil_act_id)
assert civ_item["execution_status"] == "COMPLETED"
assert civ_item["progress_percentage"] == 100.0
assert civ_item["actual_start"] == "2026-10-01"
assert civ_item["actual_finish"] == "2026-10-14"

print("[OK] Schedule activities list includes live execution fields.")

# Clean up test database file
try:
    os.remove(TEST_DB_FILE)
except Exception:
    pass

print("\n" + "=" * 60)
print("ALL PHASE 5 VERIFICATION CHECKS PASSED SUCCESSFULLY!")
print("=" * 60)

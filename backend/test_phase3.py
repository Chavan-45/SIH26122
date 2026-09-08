import os
import sys

from fastapi.testclient import TestClient
from app.main import app
from app.database.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.core.security import create_access_token

# Initialize database schema safely
Base.metadata.create_all(bind=engine)

client = TestClient(app)

print("==================================================")
print("--- STARTING PHASE 3 AUTOMATED TEST SUITE ---")
print("==================================================")

db = SessionLocal()

# TEST 1: Verify existing users
planner_user = db.query(User).filter(User.role == "PLANNER").first()
supervisor_user = db.query(User).filter(User.role == "SUPERVISOR").first()

assert planner_user is not None, "TEST 1 FAILED: Existing planner user not found in database!"
assert supervisor_user is not None, "TEST 1 FAILED: Existing supervisor user not found in database!"

print(f"TEST 1 PASSED: Found Planner ({planner_user.email}) and Supervisor ({supervisor_user.email})")

# Generate JWT tokens for authenticated requests
planner_token = create_access_token(subject=planner_user.id)
supervisor_token = create_access_token(subject=supervisor_user.id)

planner_headers = {"Authorization": f"Bearer {planner_token}"}
supervisor_headers = {"Authorization": f"Bearer {supervisor_token}"}

# Clean any previous test projects with code OIL-FAC-001
old_project = db.query(Project).filter(Project.project_code == "OIL-FAC-001").first()
if old_project:
    db.delete(old_project)
    db.commit()

# TEST 2: Planner creates project
res2 = client.post(
    "/api/projects",
    headers=planner_headers,
    json={
        "name": "Oil Processing Facility Expansion",
        "project_code": "OIL-FAC-001",
        "description": "SIH26122 test infrastructure project.",
        "location": "Assam",
        "planned_start_date": "2026-10-01",
        "planned_end_date": "2027-12-31",
    },
)
print(f"TEST 2 - Planner creates project: Status {res2.status_code}")
assert res2.status_code == 201, f"Expected 201, got {res2.status_code}: {res2.text}"
proj_data = res2.json()
project_id = proj_data["id"]
assert proj_data["project_code"] == "OIL-FAC-001"
assert proj_data["name"] == "Oil Processing Facility Expansion"
assert proj_data["status"] == "PLANNING"
assert proj_data["created_by_id"] == planner_user.id
print(f"TEST 2 PASSED: Project created with ID {project_id}")

# TEST 3: Project appears in Planner's projects list
res3 = client.get("/api/projects", headers=planner_headers)
print(f"TEST 3 - Planner lists projects: Status {res3.status_code}")
assert res3.status_code == 200
planner_projects = res3.json()
assert any(p["id"] == project_id for p in planner_projects)
print("TEST 3 PASSED: Project appears in Planner's project list.")

# TEST 4: Duplicate project code rejected
res4 = client.post(
    "/api/projects",
    headers=planner_headers,
    json={
        "name": "Duplicate Oil Facility",
        "project_code": "OIL-FAC-001",
        "planned_start_date": "2026-10-01",
        "planned_end_date": "2027-12-31",
    },
)
print(f"TEST 4 - Duplicate project code: Status {res4.status_code}")
assert res4.status_code == 400, f"Expected 400, got {res4.status_code}: {res4.text}"
print("TEST 4 PASSED: Duplicate project code rejected.")

# TEST 5: Supervisor before assignment cannot see or open project
res5_list = client.get("/api/projects", headers=supervisor_headers)
assert res5_list.status_code == 200
supervisor_projects_before = res5_list.json()
assert not any(p["id"] == project_id for p in supervisor_projects_before)

res5_detail = client.get(f"/api/projects/{project_id}", headers=supervisor_headers)
print(f"TEST 5 - Supervisor direct access before assignment: Status {res5_detail.status_code}")
assert res5_detail.status_code == 403, f"Expected 403, got {res5_detail.status_code}"
print("TEST 5 PASSED: Unassigned Supervisor cannot access project.")

# TEST 6: Supervisor cannot create projects
res6 = client.post(
    "/api/projects",
    headers=supervisor_headers,
    json={
        "name": "Supervisor Illegal Project",
        "project_code": "SUP-001",
        "planned_start_date": "2026-10-01",
        "planned_end_date": "2027-12-31",
    },
)
print(f"TEST 6 - Supervisor creates project attempt: Status {res6.status_code}")
assert res6.status_code == 403, f"Expected 403, got {res6.status_code}"
print("TEST 6 PASSED: Supervisor blocked from creating projects (403 Forbidden).")

# TEST 7: Planner assigns Supervisor with PIPING discipline
res7 = client.post(
    f"/api/projects/{project_id}/members",
    headers=planner_headers,
    json={
        "email": supervisor_user.email,
        "discipline": "PIPING",
    },
)
print(f"TEST 7 - Planner assigns Supervisor: Status {res7.status_code}")
assert res7.status_code == 201, f"Expected 201, got {res7.status_code}: {res7.text}"
member_data = res7.json()
assert member_data["user_id"] == supervisor_user.id
assert member_data["discipline"] == "PIPING"
print("TEST 7 PASSED: Supervisor assigned with PIPING discipline.")

# TEST 8: Supervisor project visibility after assignment
res8_list = client.get("/api/projects", headers=supervisor_headers)
assert res8_list.status_code == 200
supervisor_projects_after = res8_list.json()
assigned_p = next((p for p in supervisor_projects_after if p["id"] == project_id), None)
assert assigned_p is not None, "Assigned project missing from Supervisor list!"
assert assigned_p["assigned_discipline"] == "PIPING"

res8_detail = client.get(f"/api/projects/{project_id}", headers=supervisor_headers)
print(f"TEST 8 - Supervisor opens assigned project: Status {res8_detail.status_code}")
assert res8_detail.status_code == 200
assert res8_detail.json()["assigned_discipline"] == "PIPING"
print("TEST 8 PASSED: Supervisor can access assigned project with PIPING discipline.")

# TEST 9: Supervisor permissions blocked (PATCH, POST member, DELETE member)
res9_patch = client.patch(
    f"/api/projects/{project_id}",
    headers=supervisor_headers,
    json={"status": "ACTIVE"},
)
assert res9_patch.status_code == 403, f"Expected 403 on PATCH, got {res9_patch.status_code}"

res9_post_mem = client.post(
    f"/api/projects/{project_id}/members",
    headers=supervisor_headers,
    json={"email": "other@test.com", "discipline": "CIVIL"},
)
assert res9_post_mem.status_code == 403, f"Expected 403 on POST member, got {res9_post_mem.status_code}"

res9_del_mem = client.delete(
    f"/api/projects/{project_id}/members/{supervisor_user.id}",
    headers=supervisor_headers,
)
assert res9_del_mem.status_code == 403, f"Expected 403 on DELETE member, got {res9_del_mem.status_code}"
print("TEST 9 PASSED: Supervisor denied all modification/management actions (403 Forbidden).")

# TEST 10: Planner edits project status to ACTIVE
res10 = client.patch(
    f"/api/projects/{project_id}",
    headers=planner_headers,
    json={"status": "ACTIVE"},
)
print(f"TEST 10 - Planner updates project status to ACTIVE: Status {res10.status_code}")
assert res10.status_code == 200
assert res10.json()["status"] == "ACTIVE"
print("TEST 10 PASSED: Project status updated to ACTIVE.")

# TEST 11: Planner removes supervisor from project
res11 = client.delete(
    f"/api/projects/{project_id}/members/{supervisor_user.id}",
    headers=planner_headers,
)
print(f"TEST 11 - Planner removes supervisor: Status {res11.status_code}")
assert res11.status_code == 200

# Verify Supervisor access is immediately revoked
res11_sup_list = client.get("/api/projects", headers=supervisor_headers)
assert not any(p["id"] == project_id for p in res11_sup_list.json())

res11_sup_detail = client.get(f"/api/projects/{project_id}", headers=supervisor_headers)
assert res11_sup_detail.status_code == 403
print("TEST 11 PASSED: Supervisor removed; project access immediately revoked.")

# TEST 12: Persistence check (verify in database)
db_proj = db.query(Project).filter(Project.id == project_id).first()
assert db_proj is not None
assert db_proj.status == "ACTIVE"
print("TEST 12 PASSED: Project and status verified in SQLite database.")

# TEST 13: Verify health check and auth/me still work
res13_health = client.get("/api/health")
assert res13_health.status_code == 200
assert res13_health.json() == {"status": "ok", "service": "SIH26122 Backend"}

res13_me = client.get("/api/auth/me", headers=planner_headers)
assert res13_me.status_code == 200
assert res13_me.json()["email"] == planner_user.email
print("TEST 13 PASSED: Health check and /api/auth/me operational.")

db.close()
engine.dispose()

print("\n==================================================")
print("--- ALL PHASE 3 BACKEND TESTS PASSED (100%) ---")
print("==================================================")

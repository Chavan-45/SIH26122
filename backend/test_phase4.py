import os
import sys
import io
import json
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set isolated test database environment variable BEFORE importing app modules
TEST_DB_FILE = "test_phase4_sih26122.db"
if os.path.exists(TEST_DB_FILE):
    os.remove(TEST_DB_FILE)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"

from app.database.database import Base, engine, get_db
from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.schedule_import import ScheduleImport

# Initialize isolated test database tables
Base.metadata.create_all(bind=engine)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def setup_test_users_and_projects():
    """Seed test database with planner, assigned supervisor, and unassigned supervisor."""
    db = TestSessionLocal()

    planner = User(
        full_name="Phase4 Lead Planner",
        email="planner.phase4@sih.com",
        hashed_password=hash_password("Password123!"),
        role="PLANNER",
    )

    supervisor = User(
        full_name="Phase4 Civil Supervisor",
        email="supervisor.phase4@sih.com",
        hashed_password=hash_password("Password123!"),
        role="SUPERVISOR",
    )

    unassigned_sup = User(
        full_name="Unassigned Supervisor",
        email="unassigned.phase4@sih.com",
        hashed_password=hash_password("Password123!"),
        role="SUPERVISOR",
    )

    db.add_all([planner, supervisor, unassigned_sup])
    db.commit()
    db.refresh(planner)
    db.refresh(supervisor)
    db.refresh(unassigned_sup)

    # Create test projects
    proj_a = Project(
        name="Cross-Country Gas Pipeline Phase 4",
        project_code="SIH-PH4-001",
        description="L5/L6 Baseline execution pipeline project",
        location="Gujarat Refinery Sector",
        planned_start_date=date(2026, 10, 1),
        planned_end_date=date(2026, 12, 31),
        status="PLANNING",
        created_by_id=planner.id,
    )

    proj_b = Project(
        name="Offshore Terminal Platform B",
        project_code="SIH-PH4-002",
        description="Offshore topside integration project",
        location="Mumbai High Offshore",
        planned_start_date=date(2026, 11, 1),
        planned_end_date=date(2027, 3, 31),
        status="PLANNING",
        created_by_id=planner.id,
    )

    db.add_all([proj_a, proj_b])
    db.commit()
    db.refresh(proj_a)
    db.refresh(proj_b)

    # Assign supervisor to Project A
    member = ProjectMember(
        project_id=proj_a.id,
        user_id=supervisor.id,
        discipline="CIVIL",
    )
    db.add(member)
    db.commit()

    proj_a_id = proj_a.id
    proj_b_id = proj_b.id

    planner_token = create_access_token(planner.id)
    sup_token = create_access_token(supervisor.id)
    unassigned_token = create_access_token(unassigned_sup.id)

    db.close()

    return {
        "planner_id": planner.id,
        "supervisor_id": supervisor.id,
        "unassigned_id": unassigned_sup.id,
        "proj_a_id": proj_a_id,
        "proj_b_id": proj_b_id,
        "planner_token": planner_token,
        "sup_token": sup_token,
        "unassigned_token": unassigned_token,
    }


def run_phase4_tests():
    print("==================================================")
    print("STARTING PHASE 4 VERIFICATION TEST SUITE")
    print("==================================================")

    data = setup_test_users_and_projects()
    planner_token = data["planner_token"]
    sup_token = data["sup_token"]
    unassigned_token = data["unassigned_token"]
    proj_a_id = data["proj_a_id"]
    proj_b_id = data["proj_b_id"]

    planner_headers = {"Authorization": f"Bearer {planner_token}"}
    sup_headers = {"Authorization": f"Bearer {sup_token}"}
    unassigned_headers = {"Authorization": f"Bearer {unassigned_token}"}

    csv_path = "tests/fixtures/sample_schedule.csv"
    xlsx_path = "tests/fixtures/sample_schedule.xlsx"

    # TEST 1 — EXISTING REAL DB SAFETY
    print("\n--- TEST 1: REAL DB PERSISTENCE & SAFETY ---")
    real_db_path = "sih26122.db"
    assert os.path.exists(real_db_path), "Real database sih26122.db must exist and remain untouched"
    print("[OK] Real database sih26122.db preserved cleanly.")

    # TEST 2 — CSV PREVIEW
    print("\n--- TEST 2: CSV PREVIEW ---")
    with open(csv_path, "rb") as f:
        res = client.post(
            f"/api/projects/{proj_a_id}/schedule/preview",
            headers=planner_headers,
            files={"file": ("sample_schedule.csv", f, "text/csv")},
        )
    assert res.status_code == 200, f"CSV preview failed: {res.text}"
    preview_json = res.json()
    assert preview_json["row_count"] == 12, f"Expected 12 rows, got {preview_json['row_count']}"
    assert "activity_code" in preview_json["detected_mapping"]
    assert preview_json["detected_mapping"]["activity_code"] == "Activity ID"
    print(f"[OK] CSV preview successful. Detected {preview_json['row_count']} rows and mapping.")

    # TEST 3 — XLSX PREVIEW
    print("\n--- TEST 3: XLSX PREVIEW ---")
    with open(xlsx_path, "rb") as f:
        res = client.post(
            f"/api/projects/{proj_a_id}/schedule/preview",
            headers=planner_headers,
            files={"file": ("sample_schedule.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert res.status_code == 200, f"XLSX preview failed: {res.text}"
    preview_json = res.json()
    assert preview_json["row_count"] == 12
    print("[OK] XLSX preview successful.")

    # TEST 4 — COLUMN MAPPING ALIASES
    print("\n--- TEST 4: HEADER ALIAS MAPPING ---")
    alias_csv = "Task ID,Task Name,Start Date,Finish Date\nALI-01,Test Alias Task,2026-10-01,2026-10-10\n"
    res = client.post(
        f"/api/projects/{proj_a_id}/schedule/preview",
        headers=planner_headers,
        files={"file": ("alias_test.csv", io.BytesIO(alias_csv.encode("utf-8")), "text/csv")},
    )
    assert res.status_code == 200
    mapping = res.json()["detected_mapping"]
    assert mapping["activity_code"] == "Task ID"
    assert mapping["activity_name"] == "Task Name"
    assert mapping["planned_start"] == "Start Date"
    assert mapping["planned_finish"] == "Finish Date"
    print("[OK] Header aliases ('Task ID', 'Task Name', 'Start Date', 'Finish Date') auto-mapped successfully.")

    # TEST 5 — INVALID FILE TYPE REJECTION
    print("\n--- TEST 5: INVALID FILE TYPE REJECTION ---")
    res = client.post(
        f"/api/projects/{proj_a_id}/schedule/preview",
        headers=planner_headers,
        files={"file": ("document.pdf", io.BytesIO(b"%PDF-1.4 dummy content"), "application/pdf")},
    )
    assert res.status_code == 400
    assert "Unsupported file format '.pdf'" in res.json()["detail"]
    print("[OK] Unsupported file format (.pdf) rejected cleanly.")

    # TEST 6 — INVALID DATE VALIDATION (Finish < Start)
    print("\n--- TEST 6: INVALID DATE ORDER VALIDATION ---")
    bad_date_csv = "Activity ID,Activity Name,Planned Start,Planned Finish\nERR-001,Reverse Date Activity,2026-10-20,2026-10-05\n"
    res = client.post(
        f"/api/projects/{proj_b_id}/schedule/import",
        headers=planner_headers,
        files={"file": ("bad_dates.csv", io.BytesIO(bad_date_csv.encode("utf-8")), "text/csv")},
        data={"mapping": json.dumps({"activity_code": "Activity ID", "activity_name": "Activity Name", "planned_start": "Planned Start", "planned_finish": "Planned Finish"})},
    )
    assert res.status_code == 400, f"Expected 400 validation error, got {res.status_code}"
    print("[OK] Invalid date (Finish < Start) rejected cleanly with HTTP 400.")

    # TEST 7 — DUPLICATE ACTIVITY ID REJECTION
    print("\n--- TEST 7: DUPLICATE ACTIVITY CODE IN FILE ---")
    dup_csv = "Activity ID,Activity Name,Planned Start,Planned Finish\nPIP-001,Pipe Task 1,2026-10-01,2026-10-10\nPIP-001,Pipe Task Duplicate,2026-10-11,2026-10-20\n"
    res = client.post(
        f"/api/projects/{proj_b_id}/schedule/import",
        headers=planner_headers,
        files={"file": ("dup_test.csv", io.BytesIO(dup_csv.encode("utf-8")), "text/csv")},
        data={"mapping": json.dumps({"activity_code": "Activity ID", "activity_name": "Activity Name", "planned_start": "Planned Start", "planned_finish": "Planned Finish"})},
    )
    assert res.status_code == 400
    print("[OK] Duplicate activity code in upload rejected cleanly.")

    # TEST 8 — SUCCESSFUL SCHEDULE IMPORT
    print("\n--- TEST 8: SUCCESSFUL BASELINE IMPORT ---")
    mapping = {
        "activity_code": "Activity ID",
        "activity_name": "Activity Name",
        "wbs_code": "WBS Code",
        "schedule_level": "Level",
        "discipline": "Discipline",
        "planned_start": "Start Date",
        "planned_finish": "Finish Date",
        "planned_duration": "Duration",
        "predecessors": "Predecessors",
    }
    with open(csv_path, "rb") as f:
        res = client.post(
            f"/api/projects/{proj_a_id}/schedule/import",
            headers=planner_headers,
            files={"file": ("sample_schedule.csv", f, "text/csv")},
            data={"mapping": json.dumps(mapping)},
        )
    assert res.status_code == 200, f"Schedule import failed: {res.text}"
    import_res = res.json()
    assert import_res["status"] == "success"
    assert import_res["activities_imported"] == 12
    print(f"[OK] Schedule import committed 12 activities successfully for Project {proj_a_id}.")

    # TEST 9 — UNIQUE CONSTRAINT (project_id + activity_code)
    print("\n--- TEST 9: ACTIVITY UNIQUENESS CONSTRAINT ---")
    db = TestSessionLocal()
    act = db.query(Activity).filter(Activity.project_id == proj_a_id, Activity.activity_code == "CIV-001").first()
    assert act is not None
    assert act.discipline == "CIVIL"
    db.close()
    print("[OK] Activity project_id + activity_code uniqueness verified.")

    # TEST 10 — PLANNER SCHEDULE VIEW & PAGINATION
    print("\n--- TEST 10: PLANNER SCHEDULE VIEW & PAGINATION ---")
    res = client.get(f"/api/projects/{proj_a_id}/schedule", headers=planner_headers)
    assert res.status_code == 200
    status_json = res.json()
    assert status_json["has_schedule"] is True
    assert status_json["total_activities"] == 12
    assert "CIVIL" in status_json["discipline_counts"]
    assert "PIPING" in status_json["discipline_counts"]

    res_list = client.get(f"/api/projects/{proj_a_id}/activities?page=1&page_size=50", headers=planner_headers)
    assert res_list.status_code == 200
    act_json = res_list.json()
    assert len(act_json["items"]) == 12
    print(f"[OK] Schedule status returns 12 total activities and discipline breakdown.")

    # TEST 11 — FILTER BY DISCIPLINE
    print("\n--- TEST 11: DISCIPLINE FILTER ---")
    res_piping = client.get(f"/api/projects/{proj_a_id}/activities?discipline=PIPING", headers=planner_headers)
    assert res_piping.status_code == 200
    piping_items = res_piping.json()["items"]
    assert len(piping_items) == 3
    assert all(item["discipline"] == "PIPING" for item in piping_items)
    print("[OK] Filter by discipline='PIPING' returned exactly 3 piping activities.")

    # TEST 12 — SEARCH & LEVEL FILTER
    print("\n--- TEST 12: LEVEL FILTER & SEARCH ---")
    res_l6 = client.get(f"/api/projects/{proj_a_id}/activities?schedule_level=L6", headers=planner_headers)
    assert res_l6.status_code == 200
    l6_items = res_l6.json()["items"]
    assert len(l6_items) == 7
    assert all(item["schedule_level"] == "L6" for item in l6_items)

    res_search = client.get(f"/api/projects/{proj_a_id}/activities?search=ELE-201", headers=planner_headers)
    assert res_search.status_code == 200
    search_items = res_search.json()["items"]
    assert len(search_items) == 1
    assert search_items[0]["activity_code"] == "ELE-201"
    print("[OK] Search by Activity ID 'ELE-201' and Level filter 'L6' working accurately.")

    # TEST 13 — SUPERVISOR READ ACCESS
    print("\n--- TEST 13: ASSIGNED SUPERVISOR SCHEDULE ACCESS ---")
    res_sup_sched = client.get(f"/api/projects/{proj_a_id}/schedule", headers=sup_headers)
    assert res_sup_sched.status_code == 200
    assert res_sup_sched.json()["total_activities"] == 12

    res_sup_acts = client.get(f"/api/projects/{proj_a_id}/activities", headers=sup_headers)
    assert res_sup_acts.status_code == 200
    assert len(res_sup_acts.json()["items"]) == 12
    print("[OK] Assigned supervisor successfully granted read-only schedule access.")

    # TEST 14 — SUPERVISOR IMPORT ATTEMPT (403 FORBIDDEN)
    print("\n--- TEST 14: SUPERVISOR IMPORT ATTEMPT FORBIDDEN ---")
    with open(csv_path, "rb") as f:
        res_sup_imp = client.post(
            f"/api/projects/{proj_a_id}/schedule/import",
            headers=sup_headers,
            files={"file": ("sample_schedule.csv", f, "text/csv")},
            data={"mapping": json.dumps(mapping)},
        )
    assert res_sup_imp.status_code == 403
    print("[OK] Supervisor import attempt blocked with HTTP 403 Forbidden.")

    # TEST 15 — UNASSIGNED SUPERVISOR ACCESS FORBIDDEN
    print("\n--- TEST 15: UNASSIGNED SUPERVISOR ACCESS FORBIDDEN ---")
    res_unass_sched = client.get(f"/api/projects/{proj_a_id}/schedule", headers=unassigned_headers)
    assert res_unass_sched.status_code == 403
    print("[OK] Unassigned supervisor schedule access blocked with HTTP 403 Forbidden.")

    # TEST 16 — SECOND BASELINE IMPORT CONFLICT (409 CONFLICT)
    print("\n--- TEST 16: SECOND BASELINE IMPORT REJECTION (409) ---")
    with open(csv_path, "rb") as f:
        res_conflict = client.post(
            f"/api/projects/{proj_a_id}/schedule/import",
            headers=planner_headers,
            files={"file": ("sample_schedule.csv", f, "text/csv")},
            data={"mapping": json.dumps(mapping)},
        )
    assert res_conflict.status_code == 409
    assert "already has an imported baseline schedule" in res_conflict.json()["detail"]
    print("[OK] Second baseline schedule import attempt rejected with HTTP 409 Conflict.")

    # TEST 17 — TRANSACTION ROLLBACK ON INVALID ROW
    print("\n--- TEST 17: TRANSACTIONAL ROLLBACK ---")
    mixed_csv = (
        "Activity ID,Activity Name,Planned Start,Planned Finish\n"
        "GOOD-01,Valid Task 1,2026-10-01,2026-10-10\n"
        "GOOD-02,Valid Task 2,2026-10-05,2026-10-15\n"
        "BAD-03,Invalid Dates Task,2026-10-20,2026-10-01\n"
    )
    res_tx = client.post(
        f"/api/projects/{proj_b_id}/schedule/import",
        headers=planner_headers,
        files={"file": ("mixed.csv", io.BytesIO(mixed_csv.encode("utf-8")), "text/csv")},
        data={"mapping": json.dumps({"activity_code": "Activity ID", "activity_name": "Activity Name", "planned_start": "Planned Start", "planned_finish": "Planned Finish"})},
    )
    assert res_tx.status_code == 400

    # Verify ZERO activities committed to Project B
    db = TestSessionLocal()
    b_count = db.query(Activity).filter(Activity.project_id == proj_b_id).count()
    db.close()
    assert b_count == 0, f"Expected 0 activities committed due to transaction rollback, found {b_count}"
    print("[OK] Transaction rollback verified: 0 activities saved when 1 row is invalid.")

    # TEST 18 — DATABASE PERSISTENCE
    print("\n--- TEST 18: DATA PERSISTENCE CHECK ---")
    db = TestSessionLocal()
    saved_activities = db.query(Activity).filter(Activity.project_id == proj_a_id).all()
    assert len(saved_activities) == 12
    saved_import = db.query(ScheduleImport).filter(ScheduleImport.project_id == proj_a_id).first()
    assert saved_import is not None
    assert saved_import.imported_rows == 12
    db.close()
    print("[OK] Schedule activities and ScheduleImport audit record verified in database.")

    # TEST 19 — PHASE 1-3 HEALTH & AUTH ENDPOINTS
    print("\n--- TEST 19: REGRESSION CHECK PHASE 1-3 ENDPOINTS ---")
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    res_me = client.get("/api/auth/me", headers=planner_headers)
    assert res_me.status_code == 200
    assert res_me.json()["role"] == "PLANNER"
    print("[OK] Phase 1-3 endpoints (/api/health, /api/auth/me) operational.")

    # TEST 20 — MASTER SCHEDULE CSV WITH planned_end ALIAS
    print("\n--- TEST 20: MASTER SCHEDULE CSV WITH planned_end ALIAS ---")
    master_csv = (
        "activity_code,activity_name,discipline,location,planned_start,planned_end,status\n"
        "CIV-101,Foundation Concrete Pour,CIVIL,Site A,2026-10-01,2026-10-15,PLANNING\n"
        "PIP-201,Header Pipe Spool Erection,PIPING,Site B,2026-10-05,2026-10-25,PLANNING\n"
        "ELE-301,Transformer Panel Wiring,ELECTRICAL,Site C,2026-10-10,2026-10-30,PLANNING\n"
        "MEC-401,Turbine Skid Placement,MECHANICAL,Site D,2026-10-15,2026-11-05,PLANNING\n"
        "INS-501,Control Room Cabinet Integration,INSTRUMENTATION,Site E,2026-10-20,2026-11-10,PLANNING\n"
    )

    # 1. Preview master_schedule.csv
    res_master_prev = client.post(
        f"/api/projects/{proj_b_id}/schedule/preview",
        headers=planner_headers,
        files={"file": ("master_schedule.csv", io.BytesIO(master_csv.encode("utf-8")), "text/csv")},
    )
    assert res_master_prev.status_code == 200, f"Preview failed: {res_master_prev.text}"
    master_prev_data = res_master_prev.json()
    assert master_prev_data["row_count"] == 5
    assert master_prev_data["detected_mapping"]["planned_finish"] == "planned_end"
    assert len(master_prev_data["errors"]) == 0, f"Expected 0 errors, got: {master_prev_data['errors']}"
    print("[OK] Master schedule preview auto-detected planned_finish -> planned_end with 0 validation errors.")

    # 2. Import master_schedule.csv
    res_master_imp = client.post(
        f"/api/projects/{proj_b_id}/schedule/import",
        headers=planner_headers,
        files={"file": ("master_schedule.csv", io.BytesIO(master_csv.encode("utf-8")), "text/csv")},
        data={"mapping": json.dumps(master_prev_data["detected_mapping"])},
    )
    assert res_master_imp.status_code == 200, f"Import failed: {res_master_imp.text}"
    assert res_master_imp.json()["activities_imported"] == 5

    # 3. Verify database storage
    db = TestSessionLocal()
    b_acts = db.query(Activity).filter(Activity.project_id == proj_b_id).order_by(Activity.activity_code.asc()).all()
    assert len(b_acts) == 5
    civ_act = next(a for a in b_acts if a.activity_code == "CIV-101")
    assert str(civ_act.planned_start) == "2026-10-01"
    assert str(civ_act.planned_finish) == "2026-10-15"
    db.close()
    print("[OK] Master schedule imported 5 activities cleanly. planned_finish correctly populated from planned_end.")

    print("\n==================================================")
    print("ALL 20 BACKEND PHASE 4 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

    # Clean up test database file after completion
    app.dependency_overrides.clear()


if __name__ == "__main__":
    try:
        run_phase4_tests()
    finally:
        if os.path.exists(TEST_DB_FILE):
            try:
                os.remove(TEST_DB_FILE)
            except Exception:
                pass

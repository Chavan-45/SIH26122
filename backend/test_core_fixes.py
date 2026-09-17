"""Focused regression checks for the two core fixes:
1. Planner-review execution writes do not commit before the outer review transaction.
2. Supervisor dashboard data is backend-scoped to the assigned discipline.
"""

import os
from datetime import date, timedelta

TEST_DB_FILE = os.path.join(os.path.dirname(__file__), "test_core_fixes.db")
if os.path.exists(TEST_DB_FILE):
    os.remove(TEST_DB_FILE)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
os.environ["JWT_SECRET_KEY"] = "test-core-fixes-secret"
os.environ["APP_TIMEZONE"] = "Asia/Kolkata"

from app.database.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.schemas.execution import ProgressReportRequest, UpdateTypeEnum
from app.services.execution_service import process_progress_update
from app.services.dashboard_service import get_project_dashboard_data

Base.metadata.create_all(bind=engine)

today = date.today()
db = SessionLocal()

planner = User(
    full_name="Core Fix Planner",
    email="planner-core@test.com",
    hashed_password="unused-test-hash",
    role="PLANNER",
    is_active=True,
)
supervisor = User(
    full_name="Civil Supervisor",
    email="civil-core@test.com",
    hashed_password="unused-test-hash",
    role="SUPERVISOR",
    is_active=True,
)
db.add_all([planner, supervisor])
db.commit()
db.refresh(planner)
db.refresh(supervisor)

project = Project(
    name="Core Fix Test Project",
    project_code="CORE-FIX-001",
    description="Regression test project",
    location="Test Site",
    planned_start_date=today - timedelta(days=10),
    planned_end_date=today + timedelta(days=30),
    status="ACTIVE",
    created_by_id=planner.id,
)
db.add(project)
db.commit()
db.refresh(project)
project_id = project.id

# ---------------------------------------------------------------------------
# FIX 1: planner-review execution changes must stay rollbackable until the
# caller performs the final review/source/execution commit.
# ---------------------------------------------------------------------------
atomic_activity = Activity(
    project_id=project_id,
    activity_code="CIV-ATOMIC-01",
    activity_name="Atomicity Test Activity",
    discipline="CIVIL",
    planned_start=today,
    planned_finish=today + timedelta(days=5),
)
db.add(atomic_activity)
db.commit()
db.refresh(atomic_activity)
atomic_activity_id = atomic_activity.id

request = ProgressReportRequest(
    update_type=UpdateTypeEnum.START,
    reported_date=today,
    progress_percentage=10,
    remarks="Planner review atomicity test",
)

process_progress_update(
    db=db,
    project_id=project_id,
    activity_id=atomic_activity_id,
    user=planner,
    report_req=request,
    source_type="REPORT_IMPORT",
    allow_planner_resolution=True,
    override_reporter=supervisor,
)

# The rows are visible inside the current transaction after flush...
assert db.query(ActivityExecution).filter(ActivityExecution.activity_id == atomic_activity_id).first() is not None
assert db.query(ProgressUpdate).filter(ProgressUpdate.activity_id == atomic_activity_id).count() == 1

# ...but a rollback must remove both because process_progress_update did not commit.
db.rollback()
db.close()

db = SessionLocal()
assert db.query(ActivityExecution).filter(ActivityExecution.activity_id == atomic_activity_id).first() is None
assert db.query(ProgressUpdate).filter(ProgressUpdate.activity_id == atomic_activity_id).count() == 0
print("[PASS] Planner-review execution update remains atomic and rollbackable.")

# ---------------------------------------------------------------------------
# FIX 2: supervisor dashboard response must not contain another discipline.
# ---------------------------------------------------------------------------
project = db.query(Project).filter(Project.id == project_id).first()
planner = db.query(User).filter(User.email == "planner-core@test.com").first()
supervisor = db.query(User).filter(User.email == "civil-core@test.com").first()

membership = ProjectMember(
    project_id=project_id,
    user_id=supervisor.id,
    discipline="CIVIL",
)

civil_activity = Activity(
    project_id=project_id,
    activity_code="CIV-SCOPE-01",
    activity_name="Civil Scoped Activity",
    discipline="CIVIL",
    planned_start=today - timedelta(days=1),
    planned_finish=today + timedelta(days=2),
)
piping_activity = Activity(
    project_id=project_id,
    activity_code="PIP-SCOPE-01",
    activity_name="Piping Hidden Activity",
    discipline="PIPING",
    planned_start=today - timedelta(days=1),
    planned_finish=today + timedelta(days=2),
)

db.add_all([membership, civil_activity, piping_activity])
db.commit()
db.refresh(civil_activity)
db.refresh(piping_activity)

civil_exec = ActivityExecution(
    project_id=project_id,
    activity_id=civil_activity.id,
    actual_start=today - timedelta(days=1),
    progress_percentage=40,
    execution_status="IN_PROGRESS",
    last_updated_by_id=supervisor.id,
)
piping_exec = ActivityExecution(
    project_id=project_id,
    activity_id=piping_activity.id,
    actual_start=today - timedelta(days=1),
    progress_percentage=90,
    execution_status="IN_PROGRESS",
    last_updated_by_id=supervisor.id,
)

db.add_all([civil_exec, piping_exec])
db.commit()

civil_update = ProgressUpdate(
    project_id=project_id,
    activity_id=civil_activity.id,
    reported_by_id=supervisor.id,
    update_type="PROGRESS",
    reported_date=today,
    progress_percentage=40,
    remarks="Civil update",
    source_type="MANUAL",
)
piping_update = ProgressUpdate(
    project_id=project_id,
    activity_id=piping_activity.id,
    reported_by_id=supervisor.id,
    update_type="PROGRESS",
    reported_date=today,
    progress_percentage=90,
    remarks="Piping update should not be visible",
    source_type="MANUAL",
)
db.add_all([civil_update, piping_update])
db.commit()

result = get_project_dashboard_data(
    db=db,
    project=project,
    user=supervisor,
    assigned_discipline="CIVIL",
)

assert result.summary.total_activities == 2  # CIV-ATOMIC-01 + CIV-SCOPE-01
assert all(item.discipline.upper() == "CIVIL" for item in result.discipline_progress)
assert all(item.discipline.upper() == "CIVIL" for item in result.today_work)
assert all(item.discipline.upper() == "CIVIL" for item in result.overdue_activities)
assert all(item.discipline.upper() == "CIVIL" for item in result.upcoming_deadlines)
assert all(item.discipline.upper() == "CIVIL" for item in result.recent_updates)
assert all(item.activity_code != "PIP-SCOPE-01" for item in result.recent_updates)
assert result.supervisor_summary is not None
assert result.supervisor_summary.assigned_discipline == "CIVIL"

print("[PASS] Supervisor dashboard is strictly backend-scoped to CIVIL.")
print("ALL CORE FIX REGRESSION CHECKS PASSED")

db.close()

try:
    os.remove(TEST_DB_FILE)
except OSError:
    pass

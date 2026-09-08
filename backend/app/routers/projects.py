from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectMemberAdd,
    ProjectMemberResponse,
)
from app.core.dependencies import get_current_user, require_planner
from app.services.project_service import (
    verify_project_planner_owner,
    verify_project_access,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new infrastructure project (Planner only)",
)
def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Create a new project baseline managed by the authenticated planner."""
    normalized_code = project_in.project_code.strip().upper()

    # Check for duplicate project code
    existing = db.query(Project).filter(Project.project_code == normalized_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project code '{normalized_code}' is already in use by another project",
        )

    new_project = Project(
        name=project_in.name.strip(),
        project_code=normalized_code,
        description=project_in.description.strip() if project_in.description else None,
        location=project_in.location.strip() if project_in.location else None,
        planned_start_date=project_in.planned_start_date,
        planned_end_date=project_in.planned_end_date,
        status="PLANNING",
        created_by_id=current_user.id,
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    response_data = ProjectResponse.model_validate(new_project)
    response_data.creator_name = current_user.full_name
    response_data.is_owner = True
    return response_data


@router.get(
    "",
    response_model=List[ProjectResponse],
    summary="List projects accessible to current authenticated user",
)
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Planners see all projects they created.
    Supervisors see only projects where they are assigned members.
    """
    results: List[ProjectResponse] = []

    if current_user.role == "PLANNER":
        projects = (
            db.query(Project)
            .filter(Project.created_by_id == current_user.id)
            .order_by(Project.created_at.desc())
            .all()
        )
        for proj in projects:
            res = ProjectResponse.model_validate(proj)
            res.creator_name = current_user.full_name
            res.is_owner = True
            results.append(res)

    elif current_user.role == "SUPERVISOR":
        memberships = (
            db.query(ProjectMember, Project)
            .join(Project, ProjectMember.project_id == Project.id)
            .filter(ProjectMember.user_id == current_user.id)
            .order_by(Project.created_at.desc())
            .all()
        )
        for mem, proj in memberships:
            res = ProjectResponse.model_validate(proj)
            res.assigned_discipline = mem.discipline
            res.creator_name = proj.creator.full_name if proj.creator else None
            res.is_owner = False
            results.append(res)

    return results


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get single project details (Authorized users only)",
)
def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed project baseline if caller is owner planner or assigned supervisor."""
    project, assigned_discipline = verify_project_access(project_id, current_user, db)

    res = ProjectResponse.model_validate(project)
    res.creator_name = project.creator.full_name if project.creator else None
    res.assigned_discipline = assigned_discipline
    res.is_owner = (project.created_by_id == current_user.id)
    return res


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project metadata (Planner owner only)",
)
def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Update project fields such as name, description, location, dates, or status."""
    project = verify_project_planner_owner(project_id, current_user, db)

    update_data = project_update.model_dump(exclude_unset=True)

    # Validate updated dates against existing dates if only one is updated
    new_start = update_data.get("planned_start_date", project.planned_start_date)
    new_end = update_data.get("planned_end_date", project.planned_end_date)
    if new_end < new_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planned end date cannot be earlier than planned start date",
        )

    for field, value in update_data.items():
        if value is not None:
            if isinstance(value, str):
                setattr(project, field, value.strip())
            else:
                setattr(project, field, value)

    db.commit()
    db.refresh(project)

    res = ProjectResponse.model_validate(project)
    res.creator_name = current_user.full_name
    res.is_owner = True
    return res


@router.get(
    "/{project_id}/members",
    response_model=List[ProjectMemberResponse],
    summary="List team members of a project (Authorized project users)",
)
def get_project_members(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List assigned supervisors and disciplines for an authorized project."""
    verify_project_access(project_id, current_user, db)

    members = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.added_at.asc())
        .all()
    )

    result: List[ProjectMemberResponse] = []
    for mem in members:
        result.append(
            ProjectMemberResponse(
                id=mem.id,
                user_id=mem.user_id,
                full_name=mem.user.full_name,
                email=mem.user.email,
                role=mem.user.role,
                discipline=mem.discipline,
                added_at=mem.added_at,
            )
        )
    return result


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a registered supervisor to a project (Planner owner only)",
)
def add_project_member(
    project_id: int,
    member_in: ProjectMemberAdd,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Assign an existing registered supervisor with an assigned discipline."""
    verify_project_planner_owner(project_id, current_user, db)

    normalized_email = member_in.email.strip().lower()
    supervisor = db.query(User).filter(User.email == normalized_email).first()

    if not supervisor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No registered account found with email '{normalized_email}'. Supervisors must register before assignment.",
        )

    if supervisor.role != "SUPERVISOR":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{supervisor.full_name}' has role '{supervisor.role}'. Only registered SUPERVISORS can be assigned to project teams.",
        )

    # Check if supervisor already assigned
    existing = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == supervisor.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Supervisor '{supervisor.full_name}' is already assigned to this project with discipline '{existing.discipline}'.",
        )

    new_member = ProjectMember(
        project_id=project_id,
        user_id=supervisor.id,
        discipline=member_in.discipline.value,
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    return ProjectMemberResponse(
        id=new_member.id,
        user_id=supervisor.id,
        full_name=supervisor.full_name,
        email=supervisor.email,
        role=supervisor.role,
        discipline=new_member.discipline,
        added_at=new_member.added_at,
    )


@router.delete(
    "/{project_id}/members/{user_id}",
    summary="Remove a supervisor from a project (Planner owner only)",
)
def remove_project_member(
    project_id: int,
    user_id: int,
    current_user: User = Depends(require_planner),
    db: Session = Depends(get_db),
):
    """Remove a supervisor from project membership."""
    verify_project_planner_owner(project_id, current_user, db)

    member = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assigned supervisor member not found in this project",
        )

    db.delete(member)
    db.commit()

    return {
        "status": "success",
        "message": "Supervisor successfully removed from project",
    }

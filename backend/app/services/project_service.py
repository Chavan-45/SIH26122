from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember


def get_project_or_404(project_id: int, db: Session) -> Project:
    """Retrieve project by ID or raise 404 Not Found."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )
    return project


def verify_project_planner_owner(project_id: int, user: User, db: Session) -> Project:
    """Ensure current user has PLANNER role and owns the project."""
    if user.role != "PLANNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Planner role required for project management",
        )

    project = get_project_or_404(project_id, db)
    if project.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You are not the managing planner for this project",
        )
    return project


def verify_project_access(project_id: int, user: User, db: Session) -> Tuple[Project, Optional[str]]:
    """
    Ensure the user is authorized to view this project.
    Returns (Project, assigned_discipline).
    """
    project = get_project_or_404(project_id, db)

    if user.role == "PLANNER":
        if project.created_by_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have access to this project",
            )
        return project, None

    if user.role == "SUPERVISOR":
        membership = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            )
            .first()
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You are not assigned to this project",
            )
        return project, membership.discipline

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access forbidden: Role not authorized for project access",
    )

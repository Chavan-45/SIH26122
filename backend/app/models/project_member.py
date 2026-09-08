from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.database import Base


class ProjectMember(Base):
    """Associates registered supervisors with a project and specifies their discipline."""
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    discipline = Column(String(50), nullable=False)  # CIVIL, PIPING, ELECTRICAL, MECHANICAL, INSTRUMENTATION, HSE, OTHER
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Unique constraint: a supervisor can only be added to a project once
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )

    # Relationships
    project = relationship("Project", back_populates="memberships")
    user = relationship("User", back_populates="project_memberships")

    def __repr__(self) -> str:
        return f"<ProjectMember id={self.id} project_id={self.project_id} user_id={self.user_id} discipline={self.discipline}>"

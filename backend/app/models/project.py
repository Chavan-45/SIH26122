from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class Project(Base):
    """Project entity model representing infrastructure projects."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    project_code = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    planned_start_date = Column(Date, nullable=False)
    planned_end_date = Column(Date, nullable=False)
    status = Column(String(50), default="PLANNING", nullable=False)  # PLANNING, ACTIVE, ON_HOLD, COMPLETED
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    creator = relationship("User", back_populates="created_projects")
    memberships = relationship(
        "ProjectMember",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    activities = relationship(
        "Activity",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    schedule_imports = relationship(
        "ScheduleImport",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    executions = relationship(
        "ActivityExecution",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    progress_updates = relationship(
        "ProgressUpdate",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    progress_report_imports = relationship(
        "ProgressReportImport",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ai_conversations = relationship(
        "AIConversation",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} code={self.project_code} name={self.name}>"

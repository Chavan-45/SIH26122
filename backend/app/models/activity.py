from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.database import Base


class Activity(Base):
    """Database model representing L5/L6 execution schedule activities."""
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_code = Column(String(100), nullable=False, index=True)
    activity_name = Column(Text, nullable=False)
    wbs_code = Column(String(100), nullable=True)
    wbs_name = Column(String(255), nullable=True)
    schedule_level = Column(String(50), nullable=True)
    discipline = Column(String(50), nullable=False, default="UNASSIGNED")
    planned_start = Column(Date, nullable=False)
    planned_finish = Column(Date, nullable=False)
    planned_duration = Column(Float, nullable=True)
    predecessors = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "activity_code", name="uq_project_activity_code"),
    )

    # Relationship
    project = relationship("Project", back_populates="activities")
    execution = relationship(
        "ActivityExecution",
        back_populates="activity",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    progress_updates = relationship(
        "ProgressUpdate",
        back_populates="activity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Activity id={self.id} project_id={self.project_id} code={self.activity_code} name={self.activity_name[:20]}>"

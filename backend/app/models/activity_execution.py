from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Date, DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.database import Base


class ActivityExecution(Base):
    """Stores the current actual execution state of a project activity."""
    __tablename__ = "activity_executions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    actual_start = Column(Date, nullable=True)
    actual_finish = Column(Date, nullable=True)
    progress_percentage = Column(Float, default=0.0, nullable=False)
    execution_status = Column(String(50), default="NOT_STARTED", nullable=False)  # NOT_STARTED, IN_PROGRESS, ON_HOLD, COMPLETED
    last_updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)

    __table_args__ = (
        UniqueConstraint("activity_id", name="uq_activity_execution"),
    )

    # Relationships
    project = relationship("Project", back_populates="executions")
    activity = relationship("Activity", back_populates="execution")
    last_updated_by = relationship("User")

    def __repr__(self) -> str:
        return f"<ActivityExecution activity_id={self.activity_id} status={self.execution_status} progress={self.progress_percentage}%>"

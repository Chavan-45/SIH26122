from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class ProgressUpdate(Base):
    """Append-only audit trail logging every progress event reported for an activity."""
    __tablename__ = "progress_updates"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    reported_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    update_type = Column(String(50), nullable=False)  # START, PROGRESS, COMPLETE, ON_HOLD, RESUME
    reported_date = Column(Date, nullable=False)
    progress_percentage = Column(Float, nullable=True)
    remarks = Column(Text, nullable=True)
    source_type = Column(String(50), default="MANUAL", nullable=False)  # MANUAL, AI_CHAT, VOICE, SPREADSHEET, DAILY_REPORT
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="progress_updates")
    activity = relationship("Activity", back_populates="progress_updates")
    reported_by = relationship("User")

    def __repr__(self) -> str:
        return f"<ProgressUpdate id={self.id} act_id={self.activity_id} type={self.update_type} date={self.reported_date}>"

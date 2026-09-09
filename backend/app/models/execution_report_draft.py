from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class ExecutionReportDraft(Base):
    """
    Persisted draft execution report proposals extracted from natural-language AI interactions.
    Requires explicit human Supervisor confirmation before triggering actual database progress updates.
    """
    __tablename__ = "execution_report_drafts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    reported_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True)

    original_text = Column(Text, nullable=False)
    intent = Column(String(50), default="EXECUTION_REPORT", nullable=False)
    update_type = Column(String(50), nullable=False)  # START, PROGRESS, COMPLETE, ON_HOLD, RESUME
    reported_date = Column(Date, nullable=False)
    progress_percentage = Column(Float, nullable=True)
    remarks = Column(Text, nullable=True)

    matched_activity_id = Column(Integer, ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    match_confidence = Column(Float, nullable=True)  # 0.00 to 1.00
    match_status = Column(String(50), default="UNMATCHED", nullable=False)  # MATCHED_HIGH, MATCHED_MEDIUM, LOW_CONFIDENCE, UNMATCHED, MANUALLY_SELECTED
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, CONFIRMED, REJECTED, NEEDS_PLANNER_REVIEW

    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    project = relationship("Project")
    reported_by = relationship("User")
    conversation = relationship("AIConversation")
    matched_activity = relationship("Activity")

    def __repr__(self) -> str:
        return f"<ExecutionReportDraft id={self.id} project_id={self.project_id} update_type={self.update_type} status={self.status}>"

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database.database import Base


class PlannerReviewCase(Base):
    """
    Persistent entity tracking an unresolved, low-confidence, or ambiguous field progress update
    sent to the Planner Review Center for human Planner resolution.
    
    Uniquely binds to a source update from either Phase 8 (AI_REPORT) or Phase 9 (PROGRESS_REPORT).
    """
    __tablename__ = "planner_review_cases"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False)  # "AI_REPORT", "PROGRESS_REPORT"
    source_id = Column(Integer, nullable=False, index=True)  # ID in execution_report_drafts or progress_report_items

    original_activity_id = Column(Integer, ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    original_confidence = Column(Float, nullable=True)

    selected_activity_id = Column(Integer, ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    decision = Column(String(50), default="NEEDS_REVIEW", nullable=False)  # "NEEDS_REVIEW", "RESOLVED", "REJECTED", "UNPLANNED", "APPLIED"
    review_reason = Column(Text, nullable=True)

    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    applied_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("project_id", "source_type", "source_id", name="uq_planner_review_case_source"),
    )

    # Relationships
    project = relationship("Project", back_populates="planner_review_cases")
    original_activity = relationship("Activity", foreign_keys=[original_activity_id])
    selected_activity = relationship("Activity", foreign_keys=[selected_activity_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])

    def __repr__(self) -> str:
        return f"<PlannerReviewCase id={self.id} project_id={self.project_id} source={self.source_type}#{self.source_id} decision={self.decision}>"

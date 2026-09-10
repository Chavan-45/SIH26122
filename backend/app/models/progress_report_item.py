from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class ProgressReportItem(Base):
    """Child entity representing an individual extracted work update item within a batch progress report."""
    __tablename__ = "progress_report_items"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("progress_report_imports.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_description = Column(Text, nullable=False)
    reported_date = Column(Date, nullable=True)
    extracted_update_type = Column(String(50), nullable=True)  # START, PROGRESS, COMPLETE, ON_HOLD, RESUME
    extracted_progress_percentage = Column(Float, nullable=True)
    remarks = Column(Text, nullable=True)
    matched_activity_id = Column(Integer, ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    match_confidence = Column(Float, nullable=True)
    match_status = Column(String(50), default="UNMATCHED", nullable=False)  # MATCHED_HIGH, MATCHED_MEDIUM, UNMATCHED, MANUALLY_SELECTED
    review_status = Column(String(50), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED, APPLIED, INVALID
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    report = relationship("ProgressReportImport", back_populates="items")
    project = relationship("Project")
    matched_activity = relationship("Activity")

    def __repr__(self) -> str:
        return f"<ProgressReportItem id={self.id} report_id={self.report_id} desc='{self.raw_description[:20]}' match={self.match_status} status={self.review_status}>"

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class ProgressReportImport(Base):
    """Persistent entity tracking a batch progress report upload or pasted DPR session."""
    __tablename__ = "progress_report_imports"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    source_type = Column(String(50), nullable=False)  # CSV, XLSX, TEXT
    original_filename = Column(String(255), nullable=True)
    raw_text = Column(Text, nullable=True)
    status = Column(String(50), default="DRAFT", nullable=False)  # DRAFT, REVIEW, APPLIED, PARTIALLY_APPLIED, CANCELLED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project = relationship("Project", back_populates="progress_report_imports")
    uploaded_by = relationship("User")
    items = relationship(
        "ProgressReportItem",
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<ProgressReportImport id={self.id} project_id={self.project_id} source={self.source_type} status={self.status}>"

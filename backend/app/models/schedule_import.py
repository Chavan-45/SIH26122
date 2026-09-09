from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class ScheduleImport(Base):
    """Audit table logging schedule baseline imports."""
    __tablename__ = "schedule_imports"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    imported_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    total_rows = Column(Integer, nullable=False)
    imported_rows = Column(Integer, nullable=False)
    status = Column(String(50), default="COMPLETED", nullable=False)
    imported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="schedule_imports")
    imported_by = relationship("User")

    def __repr__(self) -> str:
        return f"<ScheduleImport id={self.id} project_id={self.project_id} file={self.original_filename} rows={self.imported_rows}>"

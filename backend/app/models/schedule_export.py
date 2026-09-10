from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database.database import Base


class ScheduleExport(Base):
    """
    Persistent entity tracking an export generation event of project schedule actuals.
    Acts as an auditable export snapshot record.
    """
    __tablename__ = "schedule_exports"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    exported_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    export_mode = Column(String(30), nullable=False)  # "FULL_SNAPSHOT", "CHANGES_ONLY"
    file_format = Column(String(10), nullable=False)  # "CSV", "XLSX"
    status = Column(String(20), default="GENERATED", nullable=False)  # "GENERATED", "FAILED"
    row_count = Column(Integer, default=0, nullable=False)
    changed_activity_count = Column(Integer, default=0, nullable=False)
    file_name = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_schedule_export_project_status", "project_id", "status"),
    )

    # Relationships
    project = relationship("Project", back_populates="schedule_exports")
    exported_by = relationship("User")
    items = relationship(
        "ScheduleExportItem",
        back_populates="export",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<ScheduleExport id={self.id} project_id={self.project_id} mode={self.export_mode} format={self.file_format} status={self.status} rows={self.row_count}>"


class ScheduleExportItem(Base):
    """
    Persistent snapshot of a single canonical activity actuals row at the time of export.
    Enables immutable historical downloads without recalculating from live state.
    """
    __tablename__ = "schedule_export_items"

    id = Column(Integer, primary_key=True, index=True)
    export_id = Column(Integer, ForeignKey("schedule_exports.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="SET NULL"), nullable=True, index=True)
    activity_code = Column(String(100), nullable=False, index=True)
    snapshot_json = Column(Text, nullable=False)  # JSON-serialized dictionary of canonical export columns
    change_flags_json = Column(Text, nullable=True)  # JSON-serialized list of change flags e.g. ["PROGRESS_CHANGED"]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    export = relationship("ScheduleExport", back_populates="items")
    activity = relationship("Activity")

    def __repr__(self) -> str:
        return f"<ScheduleExportItem id={self.id} export_id={self.export_id} code={self.activity_code}>"

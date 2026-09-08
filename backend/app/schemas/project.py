from enum import Enum
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator


class ProjectStatus(str, Enum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"


class Discipline(str, Enum):
    CIVIL = "CIVIL"
    PIPING = "PIPING"
    ELECTRICAL = "ELECTRICAL"
    MECHANICAL = "MECHANICAL"
    INSTRUMENTATION = "INSTRUMENTATION"
    HSE = "HSE"
    OTHER = "OTHER"


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project title")
    project_code: str = Field(..., min_length=1, max_length=100, description="Unique project identifier code")
    description: Optional[str] = Field(None, max_length=2000, description="Project scope and description")
    location: Optional[str] = Field(None, max_length=255, description="Project physical site / geographical location")
    planned_start_date: date = Field(..., description="Target execution baseline start date")
    planned_end_date: date = Field(..., description="Target execution baseline end date")

    @model_validator(mode="after")
    def validate_dates(self):
        if self.planned_end_date < self.planned_start_date:
            raise ValueError("Planned end date cannot be earlier than planned start date")
        return self


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, max_length=255)
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    status: Optional[ProjectStatus] = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.planned_start_date and self.planned_end_date:
            if self.planned_end_date < self.planned_start_date:
                raise ValueError("Planned end date cannot be earlier than planned start date")
        return self


class ProjectResponse(BaseModel):
    id: int
    name: str
    project_code: str
    description: Optional[str] = None
    location: Optional[str] = None
    planned_start_date: date
    planned_end_date: date
    status: str
    created_by_id: int
    creator_name: Optional[str] = None
    assigned_discipline: Optional[str] = None
    is_owner: Optional[bool] = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectMemberAdd(BaseModel):
    email: EmailStr = Field(..., description="Corporate email of registered supervisor")
    discipline: Discipline = Field(..., description="Engineering discipline assignment")


class ProjectMemberResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: EmailStr
    role: str
    discipline: str
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupervisorSummary(BaseModel):
    id: int
    full_name: str
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)

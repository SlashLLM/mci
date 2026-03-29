from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants.job_types import ALLOWED_JOB_TYPES


class ShiftBlock(BaseModel):
    starts_at: datetime
    ends_at: datetime
    workers_required: int = 1


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    starts_at: datetime
    ends_at: datetime
    workers_required: int


class JobOrderCreate(BaseModel):
    title: str
    job_type: str
    location_address: str
    location_lat: float
    location_lng: float
    workers_required_total: int = 1
    hourly_rate: Optional[float] = None
    per_shift_rate: Optional[float] = None
    pay_model: str = "hourly"
    required_skills: list[str] = []
    required_certifications: list[str] = []
    uniform_notes: Optional[str] = None
    special_instructions: Optional[str] = None
    geofence_radius_m: int = 200
    dispatch_mode: str = "fcfs"
    acceptance_window_minutes: int = 120
    shifts: list[ShiftBlock] = Field(default_factory=list)

    @field_validator("job_type")
    @classmethod
    def job_type_must_be_catalogue(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in ALLOWED_JOB_TYPES:
            raise ValueError("job_type must be one of the allowed catalogue values")
        return s


class JobOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_org_id: int
    title: str
    job_type: str
    status: str
    location_address: str
    location_lat: float
    location_lng: float
    workers_required_total: int
    pay_model: str
    dispatch_mode: str
    geofence_radius_m: int
    filled_slots: int = 0
    total_slots: int = 0


class JobAssignmentWorkerOut(BaseModel):
    """Worker on this job shift: confirmed, waitlisted (from offer), or applied (marketplace waitlist)."""

    assignment_id: int
    shift_id: int
    shift_starts_at: datetime
    shift_ends_at: datetime
    worker_profile_id: int
    worker_name: str
    assignment_status: str
    match_score: Optional[float] = None


class JobDeclinedWorkerOut(BaseModel):
    """Worker declined a shift offer for this job."""

    offer_id: int
    shift_id: int
    shift_starts_at: datetime
    shift_ends_at: datetime
    worker_profile_id: int
    worker_name: str


class JobRejectedWorkerOut(BaseModel):
    """Employer rejected this worker for a shift on this job."""

    assignment_id: int
    shift_id: int
    shift_starts_at: datetime
    shift_ends_at: datetime
    worker_profile_id: int
    worker_name: str
    assignment_status: str = "rejected"
    match_score: Optional[float] = None


class JobOrderDetail(JobOrderOut):
    hourly_rate: Optional[float] = None
    per_shift_rate: Optional[float] = None
    required_skills: list[str] = []
    required_certifications: list[str] = []
    uniform_notes: Optional[str] = None
    special_instructions: Optional[str] = None
    acceptance_window_minutes: int = 120
    published_at: Optional[datetime] = None
    shifts: list[ShiftOut] = Field(default_factory=list)
    accepted_workers: list[JobAssignmentWorkerOut] = Field(default_factory=list)
    declined_workers: list[JobDeclinedWorkerOut] = Field(default_factory=list)
    rejected_workers: list[JobRejectedWorkerOut] = Field(default_factory=list)

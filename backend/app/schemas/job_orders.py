from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.constants.job_types import ALLOWED_JOB_TYPES
from app.constants.skills import canonicalize_skill


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


class MatchWeightConfig(BaseModel):
    weight_proximity: float = Field(ge=0.0)
    weight_rating: float = Field(ge=0.0)
    weight_job_type: float = Field(ge=0.0)
    weight_completion: float = Field(ge=0.0)
    weight_tier: float = Field(ge=0.0)

    @model_validator(mode="after")
    def at_least_one_weight_positive(self) -> "MatchWeightConfig":
        total = (
            self.weight_proximity
            + self.weight_rating
            + self.weight_job_type
            + self.weight_completion
            + self.weight_tier
        )
        if total <= 0:
            raise ValueError("At least one match weight must be greater than zero")
        return self


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
    acceptance_window_minutes: int = 120
    shifts: list[ShiftBlock] = Field(default_factory=list)
    match_weights: Optional[MatchWeightConfig] = None

    @field_validator("job_type")
    @classmethod
    def job_type_must_be_catalogue(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in ALLOWED_JOB_TYPES:
            raise ValueError("job_type must be one of the allowed catalogue values")
        return s

    @field_validator("required_skills")
    @classmethod
    def required_skills_must_be_catalogue(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for item in v:
            canonical = canonicalize_skill(item)
            if not canonical:
                raise ValueError(f"Invalid required skill: {item!r}")
            if canonical not in out:
                out.append(canonical)
        return out


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
    geofence_radius_m: int
    filled_slots: int = 0
    total_slots: int = 0
    match_weights: MatchWeightConfig
    match_weight_overrides: Optional[MatchWeightConfig] = None


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
    applied_at: Optional[datetime] = None
    rating_avg: float = 0.0
    certifications_count: int = 0
    worker_skills: list[str] = []
    worker_certifications: list[str] = []
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    is_preferred: bool = False
    tier: str = "standard"


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


class JobOverlapAssignmentOut(BaseModel):
    """Confirmed worker assignment on this job that overlaps another confirmed job."""

    current_assignment_id: int
    current_shift_id: int
    current_shift_starts_at: datetime
    current_shift_ends_at: datetime
    worker_profile_id: int
    worker_name: str
    overlap_assignment_id: int
    overlap_shift_id: int
    overlap_shift_starts_at: datetime
    overlap_shift_ends_at: datetime
    overlap_job_id: int
    overlap_job_title: str


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
    overlapping_assignments: list[JobOverlapAssignmentOut] = Field(default_factory=list)
    has_ta_payroll: bool = False
    viewer_can_vet_assignments: bool = True
    all_confirmed_workers_clocked_out: bool = False


class JobOrderMatchWeightsUpdate(BaseModel):
    match_weights: Optional[MatchWeightConfig] = None


class JobAssignmentRejectRequest(BaseModel):
    reason: Optional[Literal["schedule_conflict"]] = None

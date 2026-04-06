from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.constants.job_types import ALLOWED_JOB_TYPES
from app.constants.skills import canonicalize_skill


class WorkerProfileIn(BaseModel):
    full_name: str = ""
    nric: Optional[str] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    languages: list[str] = []
    job_type_preferences: list[str] = []
    skills: list[str] = []
    certifications: list[str] = []
    availability: dict = {}
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    work_pass_not_applicable: Optional[bool] = None

    @field_validator("job_type_preferences")
    @classmethod
    def job_prefs_must_be_catalogue(cls, v: list[str]) -> list[str]:
        for item in v:
            if item not in ALLOWED_JOB_TYPES:
                raise ValueError(f"Invalid job type preference: {item!r}")
        return v

    @field_validator("skills")
    @classmethod
    def skills_must_be_catalogue(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for item in v:
            canonical = canonicalize_skill(item)
            if not canonical:
                raise ValueError(f"Invalid skill: {item!r}")
            if canonical not in out:
                out.append(canonical)
        return out


class WorkerProfileOut(BaseModel):
    id: int
    full_name: str
    nric_masked: Optional[str]
    phone: str = ""
    email: Optional[str] = None
    languages: list
    job_type_preferences: list
    skills: list
    certifications: list
    availability: dict
    location_lat: Optional[float]
    location_lng: Optional[float]
    bank_name: Optional[str] = None
    work_pass_not_applicable: bool = False
    rating_avg: float
    tier: str
    status: str
    profile_completeness_pct: int
    pdpa_consent: bool
    terms_accepted: bool = False
    onboarding_completed: bool = False

    class Config:
        from_attributes = True


class OnboardingCompleteIn(BaseModel):
    terms_accepted: bool = Field(..., description="Must be true to complete onboarding")


class WorkerRatingItemOut(BaseModel):
    stars: int
    comment: Optional[str] = None
    created_at: datetime
    client_org_id: Optional[int] = None
    client_org_name: Optional[str] = None
    job_title: Optional[str] = None
    shift_starts_at: Optional[datetime] = None


class PreferredClientOut(BaseModel):
    client_org_id: int
    name: str


class WorkerReputationOut(BaseModel):
    rating_avg: float
    tier: str
    ratings: list[WorkerRatingItemOut]
    preferred_by_clients: list[PreferredClientOut]


class ProfileCompletenessItemOut(BaseModel):
    id: str
    done: bool
    required_for_compliance: bool


class ProfileCompletenessDetailOut(BaseModel):
    profile_completeness_pct: int
    items: list[ProfileCompletenessItemOut]

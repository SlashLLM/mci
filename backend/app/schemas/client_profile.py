from pydantic import BaseModel, Field


class ClientProfileIn(BaseModel):
    company_name: str = ""
    contact_name: str = ""
    contact_email: str | None = None
    contact_phone: str | None = None
    address_line: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    billing_notes: str | None = None


class ClientProfileOut(BaseModel):
    id: int
    company_name: str
    contact_name: str
    contact_email: str | None = None
    contact_phone: str | None = None
    address_line: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    billing_notes: str | None = None
    profile_completeness_pct: int
    pdpa_consent: bool
    terms_accepted: bool
    onboarding_completed: bool

    class Config:
        from_attributes = True


class ClientOnboardingCompleteIn(BaseModel):
    terms_accepted: bool = Field(..., description="Must be true to complete onboarding")

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class OtpRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=32)


class OtpVerify(BaseModel):
    phone: str
    code: str = Field(..., min_length=4, max_length=10)
    role: str | None = Field(default=None, description="worker|ta|client|admin — used on first signup")
    locale: str | None = Field(default=None, description="en|zh — optional; used on first signup")
    client_org_name: str | None = Field(
        default=None,
        max_length=255,
        description="Required when role=client and user is signing up for the first time.",
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    locale: str

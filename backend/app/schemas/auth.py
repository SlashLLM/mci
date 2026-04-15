from pydantic import BaseModel, EmailStr, Field


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


class WorkerEmailOtpRequest(BaseModel):
    email: EmailStr
    locale: str | None = Field(default=None, description="en|zh — stored on new accounts")
    login_only: bool = Field(default=False, description="If true, reject unknown emails instead of allowing signup")


class WorkerEmailOtpVerify(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=10)
    locale: str | None = Field(default=None, description="en|zh — used when creating a new account")
    login_only: bool = Field(default=False, description="If true, reject unknown emails instead of creating an account")


class ClientEmailOtpRequest(BaseModel):
    email: EmailStr
    locale: str | None = Field(default=None, description="en|zh — stored on new accounts")
    login_only: bool = Field(default=False, description="If true, reject unknown emails instead of allowing signup")


class ClientEmailOtpVerify(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=10)
    locale: str | None = Field(default=None, description="en|zh — used when creating a new account")
    login_only: bool = Field(default=False, description="If true, reject unknown emails instead of creating an account")

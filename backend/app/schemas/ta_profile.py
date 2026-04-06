from pydantic import BaseModel, Field


class TaStaffProfileOut(BaseModel):
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    username: str | None = None


class TaStaffProfileUpdate(BaseModel):
    display_name: str | None = Field(
        default=None,
        description="Display name; omit to leave unchanged. Empty string clears.",
    )
    email: str | None = Field(
        default=None,
        description="New account email; omit to leave unchanged. Empty string clears email.",
    )

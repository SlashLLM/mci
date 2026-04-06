from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import TaClientContractStatus


class TaContractRequestBody(BaseModel):
    ta_user_id: int = Field(..., ge=1)
    message: Optional[str] = Field(None, max_length=2000)


class ClientOrganizationCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TaClientContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_org_id: int
    ta_user_id: int
    status: TaClientContractStatus
    requested_by_user_id: int
    requested_at: datetime
    responded_at: Optional[datetime] = None
    message: Optional[str] = None
    ta_display_name: Optional[str] = None
    ta_username: Optional[str] = None


class TalentAgentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: Optional[str] = None
    display_name: Optional[str] = None


class ClientContractContextOut(BaseModel):
    has_ta_payroll: bool
    active_ta_user_id: Optional[int] = None
    active_ta_display_name: Optional[str] = None
    active_ta_username: Optional[str] = None
    active_contract_id: Optional[int] = None
    pending_contracts: list[TaClientContractOut] = []

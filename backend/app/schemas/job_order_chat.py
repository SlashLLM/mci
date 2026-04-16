from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatJobRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    last_message_at: Optional[datetime] = None


class ChatParticipantOut(BaseModel):
    user_id: int
    role: str
    display_name: str


class ChatParticipantKeyOut(BaseModel):
    user_id: int
    x25519_public_key_b64: str


class ChatIdentityStatusOut(BaseModel):
    registered: bool


class ChatIdentityPut(BaseModel):
    x25519_public_key_b64: str = Field(..., min_length=1, max_length=128)


class ChatWrapperOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    wrapped_key_b64: str


class ChatWrapperPut(BaseModel):
    target_user_id: int = Field(..., ge=1)
    wrapped_key_b64: str = Field(..., min_length=4, max_length=4096)


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_user_id: int
    ciphertext_b64: str
    iv_b64: str
    created_at: datetime


class ChatMessageCreate(BaseModel):
    ciphertext_b64: str = Field(..., min_length=1, max_length=65536)
    iv_b64: str = Field(..., min_length=1, max_length=128)

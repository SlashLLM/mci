from pydantic import BaseModel, ConfigDict


class ClientOrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str

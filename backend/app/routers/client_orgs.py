from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import ClientOrganization, User, UserRole
from app.schemas.client_orgs import ClientOrganizationOut
from app.services.ta_client_contracts import list_client_org_ids_visible_to_ta

router = APIRouter(prefix="/client-organizations", tags=["client-organizations"])


@router.get("", response_model=list[ClientOrganizationOut])
async def list_client_organizations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    if user.role == UserRole.admin:
        r = await db.execute(select(ClientOrganization).order_by(ClientOrganization.name))
    else:
        ids = await list_client_org_ids_visible_to_ta(db, user.id)
        if not ids:
            return []
        r = await db.execute(
            select(ClientOrganization)
            .where(ClientOrganization.id.in_(ids))
            .order_by(ClientOrganization.name)
        )
    orgs = r.scalars().all()
    return [ClientOrganizationOut.model_validate(o) for o in orgs]

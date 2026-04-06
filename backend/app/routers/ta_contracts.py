from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_roles
from app.db.session import get_db
from app.models import (
    ClientOrganization,
    TaClientContract,
    TaClientContractStatus,
    User,
    UserRole,
)
from app.schemas.client_orgs import ClientOrganizationOut
from app.schemas.ta_contracts import (
    ClientContractContextOut,
    ClientOrganizationCreateBody,
    TaClientContractOut,
    TaContractRequestBody,
    TalentAgentListItem,
)
from app.services.audit import log_audit
from app.services.ta_client_contracts import get_active_contract_for_org

router = APIRouter(prefix="/ta-contracts", tags=["ta-contracts"])


@router.get("/directory/talent-agents", response_model=list[TalentAgentListItem])
async def directory_talent_agents(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client, UserRole.admin))],
):
    r = await db.execute(
        select(User).where(User.role == UserRole.ta, User.is_active.is_(True)).order_by(User.id)
    )
    return [TalentAgentListItem.model_validate(u) for u in r.scalars().all()]


def _contract_out(c: TaClientContract, ta_user: User | None = None) -> TaClientContractOut:
    base = TaClientContractOut.model_validate(c)
    disp = None
    uname = None
    if ta_user is not None:
        disp = (ta_user.display_name or "").strip() or None
        uname = ta_user.username
    return base.model_copy(update={"ta_display_name": disp, "ta_username": uname})


@router.get("/client/context", response_model=ClientContractContextOut)
async def client_contract_context(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    if not user.client_org_id:
        raise HTTPException(400, detail="No client organization")
    active = await get_active_contract_for_org(db, user.client_org_id)
    r_pending = await db.execute(
        select(TaClientContract).where(
            TaClientContract.client_org_id == user.client_org_id,
            TaClientContract.status == TaClientContractStatus.pending_ta,
        )
    )
    pending = r_pending.scalars().all()
    active_display: str | None = None
    active_username: str | None = None
    if active:
        ta_u = await db.get(User, active.ta_user_id)
        if ta_u:
            active_display = (ta_u.display_name or "").strip() or None
            active_username = ta_u.username

    pending_ta_ids = list({p.ta_user_id for p in pending})
    users_by_id: dict[int, User] = {}
    if pending_ta_ids:
        ru = await db.execute(select(User).where(User.id.in_(pending_ta_ids)))
        users_by_id = {u.id: u for u in ru.scalars().all()}

    return ClientContractContextOut(
        has_ta_payroll=active is not None,
        active_ta_user_id=active.ta_user_id if active else None,
        active_ta_display_name=active_display,
        active_ta_username=active_username,
        active_contract_id=active.id if active else None,
        pending_contracts=[_contract_out(p, users_by_id.get(p.ta_user_id)) for p in pending],
    )


@router.post("/client/request", response_model=TaClientContractOut)
async def client_request_contract(
    body: TaContractRequestBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    if not user.client_org_id:
        raise HTTPException(400, detail="No client organization")
    active = await get_active_contract_for_org(db, user.client_org_id)
    if active:
        raise HTTPException(400, detail="Organization already has an active TA contract")
    ta = await db.get(User, body.ta_user_id)
    if not ta or ta.role != UserRole.ta:
        raise HTTPException(400, detail="Invalid talent agent user")
    r_dup = await db.execute(
        select(TaClientContract).where(
            TaClientContract.client_org_id == user.client_org_id,
            TaClientContract.ta_user_id == body.ta_user_id,
            TaClientContract.status == TaClientContractStatus.pending_ta,
        )
    )
    if r_dup.scalar_one_or_none():
        raise HTTPException(400, detail="A pending request to this TA already exists")
    c = TaClientContract(
        client_org_id=user.client_org_id,
        ta_user_id=body.ta_user_id,
        status=TaClientContractStatus.pending_ta,
        requested_by_user_id=user.id,
        message=body.message,
    )
    db.add(c)
    await db.flush()
    await log_audit(
        db,
        actor_user_id=user.id,
        action="ta_contract_requested",
        entity_type="TaClientContract",
        entity_id=str(c.id),
        new_values={"ta_user_id": body.ta_user_id},
    )
    return _contract_out(c)


@router.post("/client/pending/{contract_id}/cancel")
async def client_cancel_pending(
    contract_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.client))],
):
    if not user.client_org_id:
        raise HTTPException(400, detail="No client organization")
    c = await db.get(TaClientContract, contract_id)
    if not c or c.client_org_id != user.client_org_id:
        raise HTTPException(404)
    if c.status != TaClientContractStatus.pending_ta:
        raise HTTPException(400, detail="Only pending requests can be cancelled")
    await db.delete(c)
    await log_audit(
        db,
        actor_user_id=user.id,
        action="ta_contract_request_cancelled",
        entity_type="TaClientContract",
        entity_id=str(contract_id),
    )
    return {"ok": True}


@router.get("/ta/incoming", response_model=list[TaClientContractOut])
async def ta_list_incoming(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta))],
):
    r = await db.execute(
        select(TaClientContract).where(
            TaClientContract.ta_user_id == user.id,
            TaClientContract.status == TaClientContractStatus.pending_ta,
        )
    )
    return [_contract_out(c) for c in r.scalars().all()]


@router.get("/ta/all", response_model=list[TaClientContractOut])
async def ta_list_all_contract_rows(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta))],
):
    r = await db.execute(
        select(TaClientContract)
        .where(TaClientContract.ta_user_id == user.id)
        .order_by(TaClientContract.id.desc())
    )
    return [_contract_out(c) for c in r.scalars().all()]


@router.post("/{contract_id}/accept", response_model=TaClientContractOut)
async def ta_accept_contract(
    contract_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta))],
):
    now = datetime.now(timezone.utc)
    c = await db.get(TaClientContract, contract_id)
    if not c or c.ta_user_id != user.id:
        raise HTTPException(404)
    if c.status != TaClientContractStatus.pending_ta:
        raise HTTPException(400, detail="Contract is not pending")
    active_other = await get_active_contract_for_org(db, c.client_org_id)
    if active_other:
        raise HTTPException(400, detail="Client organization already has an active contract")
    r_others = await db.execute(
        select(TaClientContract).where(
            TaClientContract.client_org_id == c.client_org_id,
            TaClientContract.status == TaClientContractStatus.pending_ta,
            TaClientContract.id != c.id,
        )
    )
    for other in r_others.scalars().all():
        other.status = TaClientContractStatus.declined
        other.responded_at = now
    c.status = TaClientContractStatus.active
    c.responded_at = now
    await db.flush()
    await log_audit(
        db,
        actor_user_id=user.id,
        action="ta_contract_accepted",
        entity_type="TaClientContract",
        entity_id=str(contract_id),
    )
    return _contract_out(c)


@router.post("/{contract_id}/decline", response_model=TaClientContractOut)
async def ta_decline_contract(
    contract_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta))],
):
    now = datetime.now(timezone.utc)
    c = await db.get(TaClientContract, contract_id)
    if not c or c.ta_user_id != user.id:
        raise HTTPException(404)
    if c.status != TaClientContractStatus.pending_ta:
        raise HTTPException(400, detail="Contract is not pending")
    c.status = TaClientContractStatus.declined
    c.responded_at = now
    await db.flush()
    await log_audit(
        db,
        actor_user_id=user.id,
        action="ta_contract_declined",
        entity_type="TaClientContract",
        entity_id=str(contract_id),
    )
    return _contract_out(c)


@router.post("/{contract_id}/terminate", response_model=TaClientContractOut)
async def ta_terminate_contract(
    contract_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta, UserRole.admin))],
):
    now = datetime.now(timezone.utc)
    c = await db.get(TaClientContract, contract_id)
    if not c:
        raise HTTPException(404)
    if user.role == UserRole.ta and c.ta_user_id != user.id:
        raise HTTPException(404)
    if c.status != TaClientContractStatus.active:
        raise HTTPException(400, detail="Only active contracts can be terminated")
    c.status = TaClientContractStatus.terminated
    c.responded_at = now
    await db.flush()
    await log_audit(
        db,
        actor_user_id=user.id,
        action="ta_contract_terminated",
        entity_type="TaClientContract",
        entity_id=str(contract_id),
    )
    return _contract_out(c)


@router.post("/enroll-client-organization", response_model=ClientOrganizationOut)
async def ta_enroll_client_organization(
    body: ClientOrganizationCreateBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles(UserRole.ta))],
):
    now = datetime.now(timezone.utc)
    org = ClientOrganization(name=body.name.strip())
    db.add(org)
    await db.flush()
    c = TaClientContract(
        client_org_id=org.id,
        ta_user_id=user.id,
        status=TaClientContractStatus.active,
        requested_by_user_id=user.id,
        requested_at=now,
        responded_at=now,
    )
    db.add(c)
    await db.flush()
    await log_audit(
        db,
        actor_user_id=user.id,
        action="ta_client_org_created_with_contract",
        entity_type="ClientOrganization",
        entity_id=str(org.id),
    )
    return ClientOrganizationOut.model_validate(org)

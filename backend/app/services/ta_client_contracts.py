from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobOrder, TaClientContract, TaClientContractStatus, User, UserRole

async def get_active_contract_for_org(db: AsyncSession, client_org_id: int) -> TaClientContract | None:
    r = await db.execute(
        select(TaClientContract).where(
            TaClientContract.client_org_id == client_org_id,
            TaClientContract.status == TaClientContractStatus.active,
        )
    )
    return r.scalar_one_or_none()


async def ta_has_active_contract_with_org(db: AsyncSession, ta_user_id: int, client_org_id: int) -> bool:
    r = await db.execute(
        select(TaClientContract.id)
        .where(
            TaClientContract.client_org_id == client_org_id,
            TaClientContract.ta_user_id == ta_user_id,
            TaClientContract.status == TaClientContractStatus.active,
        )
        .limit(1)
    )
    return r.scalar_one_or_none() is not None


async def list_client_org_ids_visible_to_ta(db: AsyncSession, ta_user_id: int) -> set[int]:
    """Orgs where this TA has an active contract or a pending request addressed to them."""
    r = await db.execute(
        select(TaClientContract.client_org_id).where(
            TaClientContract.ta_user_id == ta_user_id,
            TaClientContract.status.in_(
                (TaClientContractStatus.active, TaClientContractStatus.pending_ta),
            ),
        )
    )
    return set(r.scalars().all())


async def list_contracted_org_ids_for_ta(db: AsyncSession, ta_user_id: int) -> set[int]:
    """Orgs with an active TA contract (job access and payroll)."""
    r = await db.execute(
        select(TaClientContract.client_org_id).where(
            TaClientContract.ta_user_id == ta_user_id,
            TaClientContract.status == TaClientContractStatus.active,
        )
    )
    return set(r.scalars().all())


async def user_can_vet_shift_assignments(db: AsyncSession, user: User, job: JobOrder) -> bool:
    """Under active TA contract, only the contracted TA (or admin) vets. Otherwise client org (or admin)."""
    if user.role == UserRole.admin:
        return True
    contract = await get_active_contract_for_org(db, job.client_org_id)
    if contract:
        return user.role == UserRole.ta and user.id == contract.ta_user_id
    return user.role == UserRole.client and user.client_org_id == job.client_org_id


async def org_uses_ta_payroll(db: AsyncSession, client_org_id: int) -> bool:
    c = await get_active_contract_for_org(db, client_org_id)
    return c is not None

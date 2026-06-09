from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Household
from app.services.households import get_household

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_household(household_id: str, session: SessionDep) -> Household:
    household = await get_household(session, household_id)
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
    return household


HouseholdDep = Annotated[Household, Depends(require_household)]

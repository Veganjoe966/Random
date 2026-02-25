"""
Tenant (Masjid) management endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Role
from app.middleware.tenant import (
    CurrentUser,
    get_current_user,
    require_role,
    set_tenant_context,
)
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreateRequest, TenantResponse, TenantUpdateRequest

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post(
    "/",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.SUPER_ADMIN))],
)
async def create_tenant(
    request: TenantCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new masjid/tenant. Super admin only."""
    # Check slug uniqueness
    result = await db.execute(select(Tenant).where(Tenant.slug == request.slug))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slug '{request.slug}' is already taken",
        )

    tenant = Tenant(
        name=request.name,
        slug=request.slug,
        email=request.email,
        phone=request.phone,
        address=request.address,
        city=request.city,
        country=request.country,
        timezone=request.timezone,
        data_region=request.data_region,
    )
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)

    return tenant


@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get the current user's masjid info."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tenant assigned")

    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


@router.patch(
    "/{tenant_id}",
    response_model=TenantResponse,
    dependencies=[Depends(require_role(Role.MASJID_ADMIN))],
)
async def update_tenant(
    tenant_id: uuid.UUID,
    request: TenantUpdateRequest,
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update masjid settings. Masjid admin or above."""
    # Admins can only update their own tenant (super admin can update any)
    if current_user.role != Role.SUPER_ADMIN and current_user.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Only allow updating whitelisted fields (prevent mass assignment)
    ALLOWED_UPDATE_FIELDS = {
        "name", "email", "phone", "address", "city",
        "country", "timezone", "billing_email", "settings",
    }
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key in ALLOWED_UPDATE_FIELDS:
            setattr(tenant, key, value)

    await db.flush()
    await db.refresh(tenant)
    return tenant


@router.get(
    "/",
    dependencies=[Depends(require_role(Role.SUPER_ADMIN))],
)
async def list_tenants(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all tenants. Super admin only."""
    page_size = min(page_size, 100)
    query = (
        select(Tenant)
        .where(Tenant.deleted_at.is_(None))
        .order_by(Tenant.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    tenants = list(result.scalars().all())

    return {"items": tenants, "page": page, "page_size": page_size}

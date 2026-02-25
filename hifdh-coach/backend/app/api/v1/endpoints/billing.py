"""
Billing endpoints: subscription management, webhook receiver.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Role
from app.middleware.tenant import (
    CurrentUser,
    get_current_user,
    require_role,
    set_tenant_context,
)
from app.services.billing.stripe_service import (
    SUBSCRIPTION_TIERS,
    StripeService,
)

router = APIRouter(prefix="/billing", tags=["Billing"])
stripe_service = StripeService()


@router.get("/tiers")
async def get_subscription_tiers(country: str = "US"):
    """Get available subscription tiers with regional pricing."""
    tiers = {}
    for tier_key, tier_info in SUBSCRIPTION_TIERS.items():
        regional_price = stripe_service.get_regional_price(tier_key, country)
        tiers[tier_key] = {
            **tier_info,
            "regional_price_cents": regional_price,
            "currency": "usd",
        }
    return {"tiers": tiers, "country": country}


@router.post(
    "/subscribe",
    dependencies=[Depends(require_role(Role.MASJID_ADMIN))],
)
async def create_subscription(
    tier: str,
    country: str = "US",
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create or upgrade a subscription. Masjid admin only."""
    from app.models.tenant import Tenant

    if tier not in SUBSCRIPTION_TIERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown tier: {tier}",
        )

    # Look up tenant's Stripe customer ID
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Create Stripe customer if needed
    if not tenant.stripe_customer_id:
        customer_id = await stripe_service.create_customer(
            tenant_id=tenant.id,
            name=tenant.name,
            email=tenant.billing_email or tenant.email,
            country=tenant.country,
        )
        tenant.stripe_customer_id = customer_id
        await db.flush()
    else:
        customer_id = tenant.stripe_customer_id

    sub_result = await stripe_service.create_subscription(
        customer_id=customer_id,
        tier=tier,
        country=country,
    )

    # Persist subscription tier to tenant record
    tenant.subscription_tier = tier
    tenant.subscription_status = sub_result.get("status", "active")
    tier_info = SUBSCRIPTION_TIERS[tier]
    tenant.max_students = tier_info["max_students"]
    tenant.max_teachers = tier_info["max_teachers"]
    tenant.max_monthly_recitations = tier_info["max_monthly_recitations"]
    tenant.max_audio_storage_gb = tier_info["max_audio_storage_gb"]
    await db.flush()

    return sub_result


@router.post(
    "/cancel",
    dependencies=[Depends(require_role(Role.MASJID_ADMIN))],
)
async def cancel_subscription(
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Cancel subscription at end of billing period."""
    from app.models.tenant import Tenant

    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if not tenant.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found",
        )

    # Cancel via Stripe (at period end)
    cancel_result = await stripe_service.cancel_subscription_for_tenant(
        tenant.stripe_customer_id
    )

    # Update tenant record
    tenant.subscription_status = "cancelling"
    await db.flush()

    return {
        "message": "Subscription will be cancelled at end of billing period",
        **cancel_result,
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="stripe-signature"),
):
    """
    Stripe webhook receiver.
    Verifies signature and processes events.
    """
    payload = await request.body()
    result = await stripe_service.handle_webhook(payload, stripe_signature)
    return result


@router.get(
    "/usage",
    dependencies=[Depends(require_role(Role.MASJID_ADMIN))],
)
async def get_usage(
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get current billing period usage metrics."""
    from datetime import UTC, datetime, timedelta
    from app.models.recitation import Recitation
    from app.models.user import User
    from app.models.tenant import Tenant

    # Get tenant limits
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    # Count recitations this month
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rec_count_result = await db.execute(
        select(func.count()).select_from(Recitation).where(
            Recitation.tenant_id == current_user.tenant_id,
            Recitation.created_at >= month_start,
        )
    )
    recitations_used = rec_count_result.scalar() or 0

    # Count active students
    student_count_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.tenant_id == current_user.tenant_id,
            User.role == "student",
            User.is_active.is_(True),
        )
    )
    students_active = student_count_result.scalar() or 0

    # Sum audio storage
    storage_result = await db.execute(
        select(func.coalesce(func.sum(Recitation.audio_size_bytes), 0)).where(
            Recitation.tenant_id == current_user.tenant_id,
        )
    )
    storage_bytes = storage_result.scalar() or 0

    return {
        "tenant_id": str(current_user.tenant_id),
        "current_period": {
            "recitations_used": recitations_used,
            "recitations_limit": tenant.max_monthly_recitations if tenant else 500,
            "students_active": students_active,
            "students_limit": tenant.max_students if tenant else 25,
            "storage_used_gb": round(storage_bytes / (1024**3), 2),
            "storage_limit_gb": tenant.max_audio_storage_gb if tenant else 5,
        },
    }

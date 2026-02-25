"""
Billing endpoints: subscription management, webhook receiver.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status

from app.core.security import Role
from app.middleware.tenant import (
    CurrentUser,
    get_current_user,
    require_role,
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
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create or upgrade a subscription. Masjid admin only."""
    if tier not in SUBSCRIPTION_TIERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown tier: {tier}",
        )

    # In production: look up tenant's stripe_customer_id from DB
    # For now, return the subscription info
    result = await stripe_service.create_subscription(
        customer_id="cus_placeholder",  # From tenant record
        tier=tier,
        country=country,
    )
    return result


@router.post(
    "/cancel",
    dependencies=[Depends(require_role(Role.MASJID_ADMIN))],
)
async def cancel_subscription(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Cancel subscription at end of billing period."""
    # In production: look up subscription_id from tenant record
    return {"message": "Subscription will be cancelled at end of billing period"}


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
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get current billing period usage metrics."""
    # In production: query from DB
    return {
        "tenant_id": str(current_user.tenant_id),
        "current_period": {
            "recitations_used": 0,
            "recitations_limit": 500,
            "students_active": 0,
            "students_limit": 25,
            "storage_used_gb": 0,
            "storage_limit_gb": 5,
        },
    }

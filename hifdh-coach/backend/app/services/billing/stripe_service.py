"""
Stripe billing integration.
Handles subscriptions, metered usage, and webhook processing.

IMPORTANT: Never log or expose Stripe keys. All keys from environment only.
"""

from datetime import UTC, datetime
from uuid import UUID

import stripe
from structlog import get_logger

from app.core.config import get_settings

logger = get_logger()
settings = get_settings()

stripe.api_key = settings.stripe_secret_key


# ── Subscription Tiers ──────────────────────────────────────────────────

SUBSCRIPTION_TIERS = {
    "free": {
        "name": "Free",
        "max_students": 25,
        "max_teachers": 3,
        "max_monthly_recitations": 500,
        "max_audio_storage_gb": 5,
        "features": ["basic_analytics", "ai_scoring"],
        "price_monthly_usd": 0,
    },
    "starter": {
        "name": "Starter",
        "max_students": 100,
        "max_teachers": 10,
        "max_monthly_recitations": 2000,
        "max_audio_storage_gb": 25,
        "features": ["basic_analytics", "ai_scoring", "tajweed_analysis", "revision_scheduling"],
        "price_monthly_usd": 49,
    },
    "professional": {
        "name": "Professional",
        "max_students": 500,
        "max_teachers": 50,
        "max_monthly_recitations": 10000,
        "max_audio_storage_gb": 100,
        "features": [
            "advanced_analytics", "ai_scoring", "tajweed_analysis",
            "revision_scheduling", "parent_portal", "export_data",
            "priority_processing",
        ],
        "price_monthly_usd": 149,
    },
    "enterprise": {
        "name": "Enterprise",
        "max_students": -1,  # unlimited
        "max_teachers": -1,
        "max_monthly_recitations": -1,
        "max_audio_storage_gb": -1,
        "features": [
            "advanced_analytics", "ai_scoring", "tajweed_analysis",
            "revision_scheduling", "parent_portal", "export_data",
            "priority_processing", "custom_branding", "api_access",
            "dedicated_support", "data_region_selection", "sla",
        ],
        "price_monthly_usd": None,  # custom pricing
    },
}

# Regional pricing multipliers
REGION_PRICE_MULTIPLIERS = {
    "US": 1.0,
    "EU": 1.0,
    "UK": 0.95,
    "CA": 0.9,
    "AU": 0.9,
    "MY": 0.4,
    "PK": 0.2,
    "EG": 0.25,
    "SA": 0.7,
    "AE": 0.8,
    "TR": 0.3,
    "ID": 0.25,
    "BD": 0.15,
    "NG": 0.2,
    "IN": 0.2,
    "DEFAULT": 0.5,
}


class StripeService:
    """
    Manages Stripe integration for the SaaS platform.

    Responsibilities:
    - Customer creation/management
    - Subscription lifecycle (create, upgrade, downgrade, cancel)
    - Metered usage reporting (recitation count)
    - Webhook processing
    - Invoice management
    """

    async def create_customer(
        self, tenant_id: UUID, name: str, email: str, country: str | None = None
    ) -> str:
        """Create a Stripe customer for a tenant."""
        customer = stripe.Customer.create(
            name=name,
            email=email,
            metadata={
                "tenant_id": str(tenant_id),
                "platform": "hifdh_coach",
            },
        )
        logger.info("Stripe customer created", customer_id=customer.id, tenant_id=str(tenant_id))
        return customer.id

    async def create_subscription(
        self,
        customer_id: str,
        tier: str,
        country: str = "US",
    ) -> dict:
        """
        Create a subscription for a tier.
        Applies regional pricing if applicable.
        """
        tier_info = SUBSCRIPTION_TIERS.get(tier)
        if not tier_info:
            raise ValueError(f"Unknown tier: {tier}")

        if tier == "free":
            return {
                "subscription_id": None,
                "tier": "free",
                "status": "active",
            }

        if tier_info["price_monthly_usd"] is None:
            raise ValueError("Enterprise tier requires custom pricing")

        # Apply regional pricing
        multiplier = REGION_PRICE_MULTIPLIERS.get(
            country, REGION_PRICE_MULTIPLIERS["DEFAULT"]
        )
        price_cents = int(tier_info["price_monthly_usd"] * multiplier * 100)

        # Create a price object (or use pre-created price IDs in production)
        price = stripe.Price.create(
            unit_amount=price_cents,
            currency="usd",
            recurring={"interval": "month"},
            product_data={
                "name": f"Hifdh Coach - {tier_info['name']}",
                "metadata": {"tier": tier},
            },
        )

        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price.id}],
            metadata={"tier": tier, "region": country},
        )

        logger.info(
            "Subscription created",
            subscription_id=subscription.id,
            tier=tier,
            price_cents=price_cents,
        )

        return {
            "subscription_id": subscription.id,
            "tier": tier,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
        }

    async def report_usage(
        self, subscription_item_id: str, quantity: int, timestamp: int | None = None
    ) -> None:
        """
        Report metered usage (recitation count) to Stripe.
        Called periodically by the meter_usage Celery task.
        """
        if timestamp is None:
            timestamp = int(datetime.now(UTC).timestamp())

        stripe.SubscriptionItem.create_usage_record(
            subscription_item_id,
            quantity=quantity,
            timestamp=timestamp,
            action="increment",
        )
        logger.info(
            "Usage reported", subscription_item_id=subscription_item_id, quantity=quantity
        )

    async def cancel_subscription(self, subscription_id: str) -> dict:
        """Cancel a subscription at period end."""
        subscription = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True,
        )
        logger.info("Subscription cancelled", subscription_id=subscription_id)
        return {"status": subscription.status, "cancel_at": subscription.cancel_at}

    async def cancel_subscription_for_tenant(self, customer_id: str) -> dict:
        """Cancel all active subscriptions for a customer."""
        subscriptions = stripe.Subscription.list(customer=customer_id, status="active")
        results = []
        for sub in subscriptions.data:
            result = await self.cancel_subscription(sub.id)
            results.append(result)
        if not results:
            return {"message": "No active subscriptions found"}
        return results[0]

    async def handle_webhook(self, payload: bytes, sig_header: str) -> dict:
        """
        Process Stripe webhook events.
        Verifies signature, then dispatches to handler.
        """
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )

        event_type = event["type"]
        data = event["data"]["object"]

        handlers = {
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_succeeded": self._handle_payment_succeeded,
            "invoice.payment_failed": self._handle_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            return await handler(data)

        logger.info("Unhandled webhook event", event_type=event_type)
        return {"status": "ignored", "event_type": event_type}

    async def _handle_subscription_created(self, data: dict) -> dict:
        logger.info("Subscription created via webhook", subscription_id=data["id"])
        await self._persist_subscription_change(data, "active")
        return {"status": "processed", "action": "subscription_created"}

    async def _handle_subscription_updated(self, data: dict) -> dict:
        logger.info("Subscription updated", subscription_id=data["id"], status=data["status"])
        await self._persist_subscription_change(data, data.get("status", "active"))
        return {"status": "processed", "action": "subscription_updated"}

    async def _handle_subscription_deleted(self, data: dict) -> dict:
        logger.info("Subscription deleted", subscription_id=data["id"])
        await self._persist_subscription_change(data, "cancelled")
        return {"status": "processed", "action": "subscription_deleted"}

    async def _handle_payment_succeeded(self, data: dict) -> dict:
        logger.info("Payment succeeded", invoice_id=data["id"])
        return {"status": "processed", "action": "payment_succeeded"}

    async def _handle_payment_failed(self, data: dict) -> dict:
        logger.warning("Payment failed", invoice_id=data["id"])
        # Persist payment failure: mark tenant subscription as past_due
        customer_id = data.get("customer")
        if customer_id:
            await self._update_tenant_status(customer_id, "past_due")
        return {"status": "processed", "action": "payment_failed"}

    async def _persist_subscription_change(self, data: dict, new_status: str) -> None:
        """Persist subscription status changes to the tenant record."""
        from app.core.database import async_session_factory
        from app.models.tenant import Tenant
        from sqlalchemy import select

        customer_id = data.get("customer")
        if not customer_id:
            logger.warning("Webhook data missing customer ID", subscription_id=data.get("id"))
            return

        tier = data.get("metadata", {}).get("tier", "free")

        async with async_session_factory() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.stripe_customer_id == customer_id)
            )
            tenant = result.scalar_one_or_none()
            if tenant:
                tenant.subscription_status = new_status
                if tier in SUBSCRIPTION_TIERS:
                    tier_info = SUBSCRIPTION_TIERS[tier]
                    tenant.subscription_tier = tier
                    tenant.max_students = tier_info["max_students"]
                    tenant.max_teachers = tier_info["max_teachers"]
                    tenant.max_monthly_recitations = tier_info["max_monthly_recitations"]
                    tenant.max_audio_storage_gb = tier_info["max_audio_storage_gb"]
                await session.commit()
                logger.info("Tenant subscription updated", customer_id=customer_id, status=new_status)
            else:
                logger.warning("No tenant found for customer", customer_id=customer_id)

    async def _update_tenant_status(self, customer_id: str, new_status: str) -> None:
        """Update tenant subscription status by Stripe customer ID."""
        from app.core.database import async_session_factory
        from app.models.tenant import Tenant
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.stripe_customer_id == customer_id)
            )
            tenant = result.scalar_one_or_none()
            if tenant:
                tenant.subscription_status = new_status
                await session.commit()

    def get_tier_info(self, tier: str) -> dict:
        """Get tier configuration."""
        return SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["free"])

    def get_regional_price(self, tier: str, country: str) -> int | None:
        """Get price in cents for a tier in a specific country."""
        tier_info = SUBSCRIPTION_TIERS.get(tier)
        if not tier_info or tier_info["price_monthly_usd"] is None:
            return None
        multiplier = REGION_PRICE_MULTIPLIERS.get(
            country, REGION_PRICE_MULTIPLIERS["DEFAULT"]
        )
        return int(tier_info["price_monthly_usd"] * multiplier * 100)

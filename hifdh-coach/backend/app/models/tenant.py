"""
Tenant (Masjid) model — the root of multi-tenant isolation.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin


class Tenant(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Contact
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Billing
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_tier: Mapped[str] = mapped_column(
        String(50), default="free"
    )  # free, starter, professional, enterprise
    subscription_status: Mapped[str] = mapped_column(String(50), default="active")
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Limits
    max_students: Mapped[int] = mapped_column(default=25)
    max_teachers: Mapped[int] = mapped_column(default=3)
    max_audio_storage_gb: Mapped[int] = mapped_column(default=5)
    max_monthly_recitations: Mapped[int] = mapped_column(default=500)

    # Settings
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    data_region: Mapped[str] = mapped_column(String(20), default="us-east-1")

    # Relationships
    users = relationship("User", back_populates="tenant", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"

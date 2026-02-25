"""
Pydantic schemas for tenant/masjid endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern="^[a-z0-9-]+$")
    email: EmailStr
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    timezone: str = "UTC"
    data_region: str = "us-east-1"


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    email: str
    phone: str | None
    city: str | None
    country: str | None
    timezone: str
    subscription_tier: str
    subscription_status: str
    max_students: int
    max_teachers: int
    max_monthly_recitations: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    timezone: str | None = None


class TenantAnalyticsResponse(BaseModel):
    tenant_id: UUID
    total_students: int
    total_teachers: int
    total_recitations: int
    recitations_this_month: int
    average_accuracy: float
    average_retention: float
    active_students_7d: int
    top_students: list[dict]
    surah_distribution: list[dict]
    daily_activity: list[dict]

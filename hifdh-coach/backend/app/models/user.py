"""
User model with role-based access control.
Supports: super_admin, masjid_admin, teacher, student, parent.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin


class User(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Profile
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # For students: link to parent
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Metadata
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    # Relationships
    tenant = relationship("Tenant", back_populates="users", lazy="selectin")
    parent = relationship("User", remote_side="User.id", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"


class TeacherProfile(Base, TimestampMixin, TenantMixin):
    """Extended profile for teachers with their specializations."""
    __tablename__ = "teacher_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialization: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # e.g., "tajweed", "hifdh", "qira'at"
    ijazah_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_students: Mapped[int] = mapped_column(default=30)
    is_accepting_students: Mapped[bool] = mapped_column(Boolean, default=True)

    user = relationship("User", lazy="selectin")


class StudentProfile(Base, TimestampMixin, TenantMixin):
    """Extended profile for students with memorization progress."""
    __tablename__ = "student_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    date_of_birth: Mapped[str | None] = mapped_column(String(10), nullable=True)  # encrypted
    enrollment_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Memorization progress
    current_surah: Mapped[int] = mapped_column(default=1)
    current_ayah: Mapped[int] = mapped_column(default=1)
    total_ayahs_memorized: Mapped[int] = mapped_column(default=0)
    total_juz_completed: Mapped[int] = mapped_column(default=0)

    # Performance aggregates (updated by background tasks)
    average_retention_score: Mapped[float] = mapped_column(default=0.0)
    average_accuracy_score: Mapped[float] = mapped_column(default=0.0)
    streak_days: Mapped[int] = mapped_column(default=0)

    # Settings
    daily_revision_target_minutes: Mapped[int] = mapped_column(default=30)
    preferred_revision_time: Mapped[str | None] = mapped_column(String(5), nullable=True)

    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    teacher = relationship("User", foreign_keys=[teacher_id], lazy="selectin")

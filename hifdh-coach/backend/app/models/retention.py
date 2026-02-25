"""
Retention and spaced repetition models.
Implements Ebbinghaus forgetting curve with per-ayah tracking.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin


class RetentionRecord(Base, TimestampMixin, TenantMixin):
    """
    Tracks memory stability for each ayah a student has memorized.
    Updated after every recitation. Drives the revision schedule.

    Ebbinghaus model parameters:
        R(t) = e^(-t / S)
    Where:
        R = retention probability (0-1)
        t = time since last review (days)
        S = stability (higher = slower forgetting)
    """
    __tablename__ = "retention_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    surah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ayah_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Ebbinghaus Parameters ────────────────────────────────────────
    stability: Mapped[float] = mapped_column(
        Float, default=1.0
    )  # S: memory stability in days (higher = better retained)
    difficulty: Mapped[float] = mapped_column(
        Float, default=0.3
    )  # D: inherent difficulty (0-1, higher = harder to remember)
    last_retention: Mapped[float] = mapped_column(
        Float, default=1.0
    )  # R: retention at last review

    # ── Review History ───────────────────────────────────────────────
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_score: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Computed Fields ──────────────────────────────────────────────
    current_retention: Mapped[float] = mapped_column(
        Float, default=1.0
    )  # predicted R right now
    days_until_threshold: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # days until R drops below 0.85

    # ── Streak ───────────────────────────────────────────────────────
    consecutive_correct: Mapped[int] = mapped_column(Integer, default=0)
    mastery_level: Mapped[str] = mapped_column(
        String(20), default="new"
    )  # new, learning, reviewing, mastered

    def __repr__(self) -> str:
        return (
            f"<RetentionRecord {self.surah_number}:{self.ayah_number} "
            f"S={self.stability:.2f} R={self.current_retention:.2f}>"
        )


class RevisionSchedule(Base, TimestampMixin, TenantMixin):
    """
    Daily revision schedule generated for each student.
    Prioritized queue of ayahs to review, sorted by predicted retention drop.
    """
    __tablename__ = "revision_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    schedule_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Scheduled items (JSONB array of ayah references with priority)
    items: Mapped[list] = mapped_column(
        "items",
        type_=__import__("sqlalchemy").dialects.postgresql.JSONB,
        default=list,
    )
    # Example item:
    # {
    #     "surah": 2, "ayah_start": 255, "ayah_end": 257,
    #     "predicted_retention": 0.72, "priority": "high",
    #     "reason": "retention_below_threshold",
    #     "estimated_minutes": 5
    # }

    total_items: Mapped[int] = mapped_column(Integer, default=0)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, in_progress, completed, skipped

    def __repr__(self) -> str:
        return f"<RevisionSchedule {self.schedule_date} items={self.total_items}>"


class AuditLog(Base, TimestampMixin, TenantMixin):
    """
    Immutable audit trail for all significant actions.
    Required for compliance and teacher override tracking.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict | None] = mapped_column(
        type_=__import__("sqlalchemy").dialects.postgresql.JSONB, nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.resource_type}>"

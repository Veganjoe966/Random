"""
Recitation and analysis models.
Core of the AI pipeline — stores audio, transcription, alignment, scores.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin


class Recitation(Base, TimestampMixin, TenantMixin):
    """
    A single recitation session — one audio upload from a student.
    Contains the surah/ayah range recited and links to analysis results.
    """
    __tablename__ = "recitations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # What was recited
    surah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ayah_start: Mapped[int] = mapped_column(Integer, nullable=False)
    ayah_end: Mapped[int] = mapped_column(Integer, nullable=False)
    recitation_type: Mapped[str] = mapped_column(
        String(20), default="new_lesson"
    )  # new_lesson, revision, test

    # Audio
    audio_file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    audio_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_format: Mapped[str] = mapped_column(String(10), default="webm")
    audio_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Processing status
    status: Mapped[str] = mapped_column(
        String(30), default="uploaded"
    )  # uploaded, processing, completed, failed, reviewed
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # AI Results (aggregate)
    overall_accuracy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_tajweed_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_error_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correct_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Teacher review
    teacher_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    teacher_override_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    teacher_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Raw AI output
    whisper_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    alignment_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tajweed_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    student = relationship("User", foreign_keys=[student_id], lazy="selectin")
    teacher_reviewer = relationship("User", foreign_keys=[teacher_id], lazy="selectin")
    ayah_scores = relationship("AyahScore", back_populates="recitation", lazy="selectin")
    word_analyses = relationship("WordAnalysis", back_populates="recitation", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Recitation {self.id} surah={self.surah_number} status={self.status}>"


class AyahScore(Base, TimestampMixin, TenantMixin):
    """
    Per-ayah scoring from a recitation.
    Links to retention model for spaced repetition.
    """
    __tablename__ = "ayah_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recitation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recitations.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    surah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ayah_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Scores
    accuracy_score: Mapped[float] = mapped_column(Float, default=0.0)
    tajweed_score: Mapped[float] = mapped_column(Float, default=0.0)
    combined_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Error details
    total_words: Mapped[int] = mapped_column(Integer, default=0)
    correct_words: Mapped[int] = mapped_column(Integer, default=0)
    missing_words: Mapped[int] = mapped_column(Integer, default=0)
    added_words: Mapped[int] = mapped_column(Integer, default=0)
    substituted_words: Mapped[int] = mapped_column(Integer, default=0)

    # Teacher override
    teacher_override_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    recitation = relationship("Recitation", back_populates="ayah_scores")

    def __repr__(self) -> str:
        return f"<AyahScore {self.surah_number}:{self.ayah_number} = {self.combined_score}>"


class WordAnalysis(Base, TimestampMixin, TenantMixin):
    """
    Word-level analysis from alignment engine.
    Each row = one word position in the reference text.
    """
    __tablename__ = "word_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recitation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recitations.id", ondelete="CASCADE"), index=True
    )
    surah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ayah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    word_position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Reference vs recited
    reference_word: Mapped[str] = mapped_column(String(200), nullable=False)
    recited_word: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Classification
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # correct, substituted, missing, added

    # Timing
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Tajweed
    expected_tajweed_rule: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tajweed_duration_expected: Mapped[float | None] = mapped_column(Float, nullable=True)
    tajweed_duration_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    tajweed_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    recitation = relationship("Recitation", back_populates="word_analyses")

    def __repr__(self) -> str:
        return f"<WordAnalysis {self.reference_word} → {self.recited_word} [{self.status}]>"

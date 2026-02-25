"""
Pydantic schemas for student endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StudentProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    email: str
    teacher_id: UUID | None
    current_surah: int
    current_ayah: int
    total_ayahs_memorized: int
    total_juz_completed: int
    average_retention_score: float
    average_accuracy_score: float
    streak_days: int
    daily_revision_target_minutes: int
    enrollment_date: datetime | None

    model_config = {"from_attributes": True}


class StudentProgressResponse(BaseModel):
    student_id: UUID
    total_ayahs_memorized: int
    total_juz_completed: int
    memorization_map: list[dict]  # [{surah: 1, ayahs_memorized: 7, total: 7, pct: 100}]
    retention_summary: dict  # {mastered: 50, reviewing: 30, learning: 15, new: 5}
    recent_scores: list[dict]
    streak_days: int
    this_week_minutes: int
    predictions: dict  # {projected_completion_juz: "2025-06-01", ...}


class RevisionScheduleResponse(BaseModel):
    schedule_date: datetime
    items: list["ScheduleItemResponse"]
    total_items: int
    total_ayahs: int
    estimated_minutes: int
    critical_count: int
    high_count: int


class ScheduleItemResponse(BaseModel):
    surah_number: int
    ayah_start: int
    ayah_end: int
    predicted_retention: float
    priority: str
    reason: str
    estimated_seconds: int
    mastery_level: str


class RetentionHeatmapResponse(BaseModel):
    """Per-surah retention data for heatmap visualization."""
    student_id: UUID
    surahs: list["SurahRetentionResponse"]


class SurahRetentionResponse(BaseModel):
    surah_number: int
    surah_name: str
    ayahs: list["AyahRetentionResponse"]
    average_retention: float


class AyahRetentionResponse(BaseModel):
    ayah_number: int
    retention: float
    stability: float
    mastery_level: str
    last_reviewed: datetime | None
    next_review: datetime | None

"""
Pydantic schemas for recitation endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RecitationUploadRequest(BaseModel):
    surah_number: int = Field(ge=1, le=114)
    ayah_start: int = Field(ge=1)
    ayah_end: int = Field(ge=1)
    recitation_type: str = Field(default="new_lesson", pattern="^(new_lesson|revision|test)$")


class RecitationResponse(BaseModel):
    id: UUID
    student_id: UUID
    surah_number: int
    ayah_start: int
    ayah_end: int
    recitation_type: str
    status: str
    audio_duration_seconds: float | None
    overall_accuracy_score: float | None
    overall_tajweed_score: float | None
    word_error_rate: float | None
    total_words: int | None
    correct_words: int | None
    error_count: int | None
    teacher_reviewed: bool
    teacher_override_score: float | None
    teacher_notes: str | None
    created_at: datetime
    processing_completed_at: datetime | None

    model_config = {"from_attributes": True}


class RecitationDetailResponse(RecitationResponse):
    ayah_scores: list["AyahScoreResponse"]
    word_analyses: list["WordAnalysisResponse"]
    error_details: list[dict] | None = None


class AyahScoreResponse(BaseModel):
    id: UUID
    surah_number: int
    ayah_number: int
    accuracy_score: float
    tajweed_score: float
    combined_score: float
    total_words: int
    correct_words: int
    missing_words: int
    added_words: int
    substituted_words: int
    teacher_override_score: float | None

    model_config = {"from_attributes": True}


class WordAnalysisResponse(BaseModel):
    id: UUID
    surah_number: int
    ayah_number: int
    word_position: int
    reference_word: str
    recited_word: str | None
    status: str
    start_time: float | None
    end_time: float | None
    duration: float | None
    tajweed_score: float | None

    model_config = {"from_attributes": True}


class TeacherReviewRequest(BaseModel):
    override_score: float | None = Field(None, ge=0.0, le=1.0)
    notes: str | None = Field(None, max_length=2000)
    ayah_overrides: list["AyahOverride"] | None = None


class AyahOverride(BaseModel):
    ayah_score_id: UUID
    override_score: float = Field(ge=0.0, le=1.0)


class RecitationListResponse(BaseModel):
    items: list[RecitationResponse]
    total: int
    page: int
    page_size: int
    has_next: bool

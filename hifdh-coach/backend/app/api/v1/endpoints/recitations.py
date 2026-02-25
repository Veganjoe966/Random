"""
Recitation endpoints: upload audio, get results, teacher review.
"""

import uuid
from datetime import UTC, datetime

import boto3
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.middleware.tenant import (
    CurrentUser,
    get_current_user,
    require_permission,
    set_tenant_context,
)
from app.models.recitation import AyahScore, Recitation, WordAnalysis
from app.models.retention import AuditLog
from app.schemas.recitation import (
    RecitationDetailResponse,
    RecitationListResponse,
    RecitationResponse,
    TeacherReviewRequest,
)
from app.tasks.audio_processing import process_recitation_task

router = APIRouter(prefix="/recitations", tags=["Recitations"])
settings = get_settings()


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


@router.post(
    "/upload",
    response_model=RecitationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("upload_recitation"))],
)
async def upload_recitation(
    surah_number: int = Form(ge=1, le=114),
    ayah_start: int = Form(ge=1),
    ayah_end: int = Form(ge=1),
    recitation_type: str = Form(default="new_lesson"),
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Upload a recitation audio file for AI analysis.

    The audio is stored in S3 and a Celery task is queued for processing.
    Processing includes: Whisper transcription → alignment → tajweed → scoring.

    Accepted formats: webm, wav, mp3, m4a, ogg
    Max size: 50MB
    Max duration: 10 minutes
    """
    # Validate audio file
    allowed_types = {"audio/webm", "audio/wav", "audio/mpeg", "audio/mp4", "audio/ogg",
                     "audio/x-wav", "audio/x-m4a", "video/webm"}
    if audio.content_type and audio.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format: {audio.content_type}",
        )

    # Read and check size
    contents = await audio.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.max_audio_file_size_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file too large: {size_mb:.1f}MB (max {settings.max_audio_file_size_mb}MB)",
        )

    # Generate S3 key: tenant_id/student_id/YYYY-MM/uuid.ext
    ext = audio.filename.rsplit(".", 1)[-1] if audio.filename and "." in audio.filename else "webm"
    now = datetime.now(UTC)
    s3_key = (
        f"{current_user.tenant_id}/{current_user.user_id}/"
        f"{now.strftime('%Y-%m')}/{uuid.uuid4()}.{ext}"
    )

    # Upload to S3 (encrypted at rest via server-side encryption)
    s3 = _get_s3_client()
    s3.put_object(
        Bucket=settings.s3_bucket_audio,
        Key=s3_key,
        Body=contents,
        ContentType=audio.content_type or "audio/webm",
        ServerSideEncryption="AES256",
        Metadata={
            "tenant_id": str(current_user.tenant_id),
            "student_id": str(current_user.user_id),
            "surah": str(surah_number),
        },
    )

    # Create recitation record
    recitation = Recitation(
        student_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        surah_number=surah_number,
        ayah_start=ayah_start,
        ayah_end=ayah_end,
        recitation_type=recitation_type,
        audio_file_key=s3_key,
        audio_format=ext,
        audio_size_bytes=len(contents),
        status="uploaded",
    )
    db.add(recitation)
    await db.flush()
    await db.refresh(recitation)

    # Queue processing task
    task = process_recitation_task.delay(
        recitation_id=str(recitation.id),
        tenant_id=str(current_user.tenant_id),
    )
    recitation.celery_task_id = task.id
    recitation.status = "processing"
    recitation.processing_started_at = datetime.now(UTC)
    await db.flush()

    return recitation


@router.get("/{recitation_id}", response_model=RecitationDetailResponse)
async def get_recitation(
    recitation_id: uuid.UUID,
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get detailed recitation results including per-word analysis."""
    result = await db.execute(
        select(Recitation).where(Recitation.id == recitation_id)
    )
    recitation = result.scalar_one_or_none()

    if not recitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recitation not found")

    # Students can only see their own; teachers/admins can see all in tenant
    if current_user.role.value == "student" and recitation.student_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return recitation


@router.get("/", response_model=RecitationListResponse)
async def list_recitations(
    student_id: uuid.UUID | None = None,
    surah_number: int | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List recitations with filtering and pagination."""
    query = select(Recitation)

    # Students see only their own
    if current_user.role.value == "student":
        query = query.where(Recitation.student_id == current_user.user_id)
    elif student_id:
        query = query.where(Recitation.student_id == student_id)

    if surah_number:
        query = query.where(Recitation.surah_number == surah_number)
    if status_filter:
        query = query.where(Recitation.status == status_filter)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.order_by(Recitation.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    items = list(result.scalars().all())

    return RecitationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.post(
    "/{recitation_id}/review",
    response_model=RecitationResponse,
    dependencies=[Depends(require_permission("override_scores"))],
)
async def teacher_review(
    recitation_id: uuid.UUID,
    review: TeacherReviewRequest,
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Teacher reviews and optionally overrides AI scores.
    This is a critical feature: teachers ALWAYS have final say over AI.
    All overrides are audit-logged.
    """
    result = await db.execute(
        select(Recitation).where(Recitation.id == recitation_id)
    )
    recitation = result.scalar_one_or_none()

    if not recitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recitation not found")

    # Store old values for audit
    old_score = recitation.overall_accuracy_score

    # Apply teacher review
    recitation.teacher_reviewed = True
    recitation.teacher_id = current_user.user_id
    recitation.teacher_notes = review.notes
    recitation.teacher_reviewed_at = datetime.now(UTC)

    if review.override_score is not None:
        recitation.teacher_override_score = review.override_score

    # Apply per-ayah overrides
    if review.ayah_overrides:
        for override in review.ayah_overrides:
            ayah_result = await db.execute(
                select(AyahScore).where(AyahScore.id == override.ayah_score_id)
            )
            ayah_score = ayah_result.scalar_one_or_none()
            if ayah_score:
                ayah_score.teacher_override_score = override.override_score

    recitation.status = "reviewed"
    await db.flush()

    # Audit log
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="teacher_review",
        resource_type="recitation",
        resource_id=str(recitation_id),
        details={
            "old_score": old_score,
            "override_score": review.override_score,
            "notes": review.notes,
            "ayah_overrides_count": len(review.ayah_overrides) if review.ayah_overrides else 0,
        },
    )
    db.add(audit)
    await db.flush()

    return recitation

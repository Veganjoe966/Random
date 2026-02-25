"""
Student endpoints: progress, schedules, retention data.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.tenant import (
    CurrentUser,
    get_current_user,
    require_role,
    set_tenant_context,
)
from app.core.security import Role
from app.models.retention import RetentionRecord, RevisionSchedule
from app.models.user import StudentProfile, User
from app.schemas.student import (
    RevisionScheduleResponse,
    RetentionHeatmapResponse,
    StudentProfileResponse,
    StudentProgressResponse,
)
from app.services.scheduling.revision_scheduler import RevisionScheduler

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("/me/profile", response_model=StudentProfileResponse)
async def get_my_profile(
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get the current student's profile and progress summary."""
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == current_user.user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    user_result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = user_result.scalar_one()

    return StudentProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        teacher_id=profile.teacher_id,
        current_surah=profile.current_surah,
        current_ayah=profile.current_ayah,
        total_ayahs_memorized=profile.total_ayahs_memorized,
        total_juz_completed=profile.total_juz_completed,
        average_retention_score=profile.average_retention_score,
        average_accuracy_score=profile.average_accuracy_score,
        streak_days=profile.streak_days,
        daily_revision_target_minutes=profile.daily_revision_target_minutes,
        enrollment_date=profile.enrollment_date,
    )


@router.get("/me/schedule", response_model=RevisionScheduleResponse)
async def get_my_schedule(
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Get today's personalized revision schedule.
    Generated using spaced repetition based on retention predictions.
    """
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    # Check for existing schedule
    result = await db.execute(
        select(RevisionSchedule).where(
            RevisionSchedule.student_id == current_user.user_id,
            RevisionSchedule.schedule_date >= today,
        ).order_by(RevisionSchedule.schedule_date.asc()).limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing:
        return RevisionScheduleResponse(
            schedule_date=existing.schedule_date,
            items=existing.items,
            total_items=existing.total_items,
            total_ayahs=sum(
                i.get("ayah_end", i.get("ayah_start", 0)) - i.get("ayah_start", 0) + 1
                for i in existing.items
            ),
            estimated_minutes=existing.estimated_minutes,
            critical_count=sum(1 for i in existing.items if i.get("priority") == "critical"),
            high_count=sum(1 for i in existing.items if i.get("priority") == "high"),
        )

    # Generate new schedule
    retention_result = await db.execute(
        select(RetentionRecord).where(
            RetentionRecord.student_id == current_user.user_id
        )
    )
    records = list(retention_result.scalars().all())

    if not records:
        return RevisionScheduleResponse(
            schedule_date=today,
            items=[],
            total_items=0,
            total_ayahs=0,
            estimated_minutes=0,
            critical_count=0,
            high_count=0,
        )

    # Get student's daily budget
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == current_user.user_id)
    )
    profile = profile_result.scalar_one_or_none()
    budget = profile.daily_revision_target_minutes if profile else 30

    scheduler = RevisionScheduler()
    schedule = scheduler.generate_schedule(
        student_id=current_user.user_id,
        retention_records=[
            {
                "surah_number": r.surah_number,
                "ayah_number": r.ayah_number,
                "stability": r.stability,
                "difficulty": r.difficulty,
                "last_reviewed_at": r.last_reviewed_at,
                "review_count": r.review_count,
            }
            for r in records
        ],
        daily_budget_minutes=budget,
        schedule_date=today,
    )

    # Persist schedule
    db_schedule = RevisionSchedule(
        tenant_id=current_user.tenant_id,
        student_id=current_user.user_id,
        schedule_date=today,
        items=[
            {
                "surah_number": item.surah_number,
                "ayah_start": item.ayah_start,
                "ayah_end": item.ayah_end,
                "predicted_retention": item.predicted_retention,
                "priority": item.priority,
                "reason": item.reason,
                "estimated_seconds": item.estimated_seconds,
                "mastery_level": item.mastery_level,
            }
            for item in schedule.items
        ],
        total_items=schedule.total_items,
        estimated_minutes=schedule.estimated_minutes,
    )
    db.add(db_schedule)
    await db.flush()

    return RevisionScheduleResponse(
        schedule_date=today,
        items=[
            {
                "surah_number": i.surah_number,
                "ayah_start": i.ayah_start,
                "ayah_end": i.ayah_end,
                "predicted_retention": i.predicted_retention,
                "priority": i.priority,
                "reason": i.reason,
                "estimated_seconds": i.estimated_seconds,
                "mastery_level": i.mastery_level,
            }
            for i in schedule.items
        ],
        total_items=schedule.total_items,
        total_ayahs=schedule.total_ayahs,
        estimated_minutes=schedule.estimated_minutes,
        critical_count=schedule.critical_count,
        high_count=schedule.high_count,
    )


@router.get(
    "/{student_id}/profile",
    response_model=StudentProfileResponse,
    dependencies=[Depends(require_role(Role.TEACHER))],
)
async def get_student_profile(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(set_tenant_context),
):
    """Get a student's profile (teacher/admin view)."""
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == student_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    user_result = await db.execute(select(User).where(User.id == student_id))
    user = user_result.scalar_one()

    return StudentProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        teacher_id=profile.teacher_id,
        current_surah=profile.current_surah,
        current_ayah=profile.current_ayah,
        total_ayahs_memorized=profile.total_ayahs_memorized,
        total_juz_completed=profile.total_juz_completed,
        average_retention_score=profile.average_retention_score,
        average_accuracy_score=profile.average_accuracy_score,
        streak_days=profile.streak_days,
        daily_revision_target_minutes=profile.daily_revision_target_minutes,
        enrollment_date=profile.enrollment_date,
    )


@router.get(
    "/",
    dependencies=[Depends(require_role(Role.TEACHER))],
)
async def list_students(
    teacher_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(set_tenant_context),
):
    """List students in the tenant (teacher/admin view)."""
    query = select(User).where(User.role == "student")
    if teacher_id:
        # Filter by teacher's assigned students
        subquery = select(StudentProfile.user_id).where(
            StudentProfile.teacher_id == teacher_id
        )
        query = query.where(User.id.in_(subquery))

    query = query.order_by(User.last_name, User.first_name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    students = list(result.scalars().all())

    return {
        "items": [
            {
                "id": s.id,
                "email": s.email,
                "first_name": s.first_name,
                "last_name": s.last_name,
                "is_active": s.is_active,
            }
            for s in students
        ],
        "page": page,
        "page_size": page_size,
    }

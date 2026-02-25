"""
Analytics endpoints: masjid-level and teacher-level analytics.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Role
from app.middleware.tenant import (
    CurrentUser,
    get_current_user,
    require_role,
    set_tenant_context,
)
from app.models.recitation import Recitation
from app.models.retention import RetentionRecord
from app.models.user import StudentProfile, User
from app.schemas.tenant import TenantAnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/masjid",
    response_model=TenantAnalyticsResponse,
    dependencies=[Depends(require_role(Role.MASJID_ADMIN))],
)
async def get_masjid_analytics(
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Get masjid-level analytics dashboard data.
    Available to masjid admins and above.
    """
    tenant_id = current_user.tenant_id
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Total students
    student_count = await db.execute(
        select(func.count()).select_from(User).where(
            User.role == "student", User.is_active.is_(True)
        )
    )
    total_students = student_count.scalar() or 0

    # Total teachers
    teacher_count = await db.execute(
        select(func.count()).select_from(User).where(
            User.role == "teacher", User.is_active.is_(True)
        )
    )
    total_teachers = teacher_count.scalar() or 0

    # Total recitations
    recitation_count = await db.execute(
        select(func.count()).select_from(Recitation)
    )
    total_recitations = recitation_count.scalar() or 0

    # Recitations this month
    monthly_count = await db.execute(
        select(func.count()).select_from(Recitation).where(
            Recitation.created_at >= month_start
        )
    )
    recitations_this_month = monthly_count.scalar() or 0

    # Average accuracy
    avg_accuracy = await db.execute(
        select(func.avg(Recitation.overall_accuracy_score)).where(
            Recitation.overall_accuracy_score.isnot(None)
        )
    )
    average_accuracy = round(avg_accuracy.scalar() or 0.0, 3)

    # Average retention
    avg_retention = await db.execute(
        select(func.avg(RetentionRecord.current_retention))
    )
    average_retention = round(avg_retention.scalar() or 0.0, 3)

    # Active students (7 days)
    active_students = await db.execute(
        select(func.count(func.distinct(Recitation.student_id))).where(
            Recitation.created_at >= week_ago
        )
    )
    active_7d = active_students.scalar() or 0

    # Top students by accuracy
    top_query = await db.execute(
        select(
            StudentProfile.user_id,
            User.first_name,
            User.last_name,
            StudentProfile.average_accuracy_score,
            StudentProfile.total_ayahs_memorized,
        )
        .join(User, User.id == StudentProfile.user_id)
        .order_by(StudentProfile.average_accuracy_score.desc())
        .limit(10)
    )
    top_students = [
        {
            "user_id": str(row[0]),
            "name": f"{row[1]} {row[2]}",
            "accuracy": round(row[3], 3),
            "ayahs_memorized": row[4],
        }
        for row in top_query.all()
    ]

    # Surah distribution
    surah_dist = await db.execute(
        select(
            Recitation.surah_number,
            func.count(Recitation.id).label("count"),
        )
        .group_by(Recitation.surah_number)
        .order_by(func.count(Recitation.id).desc())
        .limit(20)
    )
    surah_distribution = [
        {"surah": row[0], "count": row[1]} for row in surah_dist.all()
    ]

    # Daily activity (last 30 days)
    thirty_days_ago = now - timedelta(days=30)
    daily_query = await db.execute(
        select(
            func.date(Recitation.created_at).label("date"),
            func.count(Recitation.id).label("count"),
        )
        .where(Recitation.created_at >= thirty_days_ago)
        .group_by(func.date(Recitation.created_at))
        .order_by(func.date(Recitation.created_at))
    )
    daily_activity = [
        {"date": str(row[0]), "count": row[1]} for row in daily_query.all()
    ]

    return TenantAnalyticsResponse(
        tenant_id=tenant_id,
        total_students=total_students,
        total_teachers=total_teachers,
        total_recitations=total_recitations,
        recitations_this_month=recitations_this_month,
        average_accuracy=average_accuracy,
        average_retention=average_retention,
        active_students_7d=active_7d,
        top_students=top_students,
        surah_distribution=surah_distribution,
        daily_activity=daily_activity,
    )


@router.get(
    "/teacher/summary",
    dependencies=[Depends(require_role(Role.TEACHER))],
)
async def get_teacher_summary(
    db: AsyncSession = Depends(set_tenant_context),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get summary analytics for the current teacher's students."""
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)

    # Get teacher's students
    student_ids_result = await db.execute(
        select(StudentProfile.user_id).where(
            StudentProfile.teacher_id == current_user.user_id
        )
    )
    student_ids = [row[0] for row in student_ids_result.all()]

    if not student_ids:
        return {
            "total_students": 0,
            "pending_reviews": 0,
            "this_week_recitations": 0,
            "students_needing_attention": [],
        }

    # Pending reviews
    pending = await db.execute(
        select(func.count()).select_from(Recitation).where(
            Recitation.student_id.in_(student_ids),
            Recitation.status == "completed",
            Recitation.teacher_reviewed.is_(False),
        )
    )

    # This week's recitations
    weekly = await db.execute(
        select(func.count()).select_from(Recitation).where(
            Recitation.student_id.in_(student_ids),
            Recitation.created_at >= week_ago,
        )
    )

    # Students with low retention (need attention)
    low_retention = await db.execute(
        select(
            StudentProfile.user_id,
            User.first_name,
            User.last_name,
            StudentProfile.average_retention_score,
        )
        .join(User, User.id == StudentProfile.user_id)
        .where(
            StudentProfile.user_id.in_(student_ids),
            StudentProfile.average_retention_score < 0.75,
        )
        .order_by(StudentProfile.average_retention_score.asc())
        .limit(10)
    )

    return {
        "total_students": len(student_ids),
        "pending_reviews": pending.scalar() or 0,
        "this_week_recitations": weekly.scalar() or 0,
        "students_needing_attention": [
            {
                "user_id": str(row[0]),
                "name": f"{row[1]} {row[2]}",
                "retention_score": round(row[3], 3),
            }
            for row in low_retention.all()
        ],
    }

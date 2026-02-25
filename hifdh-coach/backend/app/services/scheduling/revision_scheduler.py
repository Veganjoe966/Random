"""
Revision schedule generation engine.
Uses retention predictions to build daily prioritized review queues.

The scheduler:
1. Queries all retention records for a student
2. Predicts current retention for each ayah
3. Sorts by urgency (lowest predicted R first)
4. Groups into review blocks that fit the student's daily time budget
5. Generates a structured schedule with estimated durations
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from structlog import get_logger

from app.services.ai.retention_model import (
    RETENTION_THRESHOLD,
    RetentionModel,
    RetentionPrediction,
)

logger = get_logger()


# ── Configuration ────────────────────────────────────────────────────────

# Estimated time to review one ayah (seconds)
SECONDS_PER_AYAH_REVIEW = 45

# Maximum ayahs in a single revision session
MAX_AYAHS_PER_SESSION = 40

# How many days ahead to look for upcoming reviews
LOOKAHEAD_DAYS = 3

# Minimum predicted retention to still schedule (below this → always include)
ALWAYS_INCLUDE_THRESHOLD = 0.7

# Priority weights
PRIORITY_WEIGHT_RETENTION = 0.5
PRIORITY_WEIGHT_DIFFICULTY = 0.2
PRIORITY_WEIGHT_DAYS_OVERDUE = 0.3


@dataclass
class ScheduleItem:
    """A single item in the revision schedule."""
    surah_number: int
    ayah_start: int
    ayah_end: int
    predicted_retention: float
    priority: str  # critical, high, medium, low
    priority_score: float
    reason: str
    estimated_seconds: int
    mastery_level: str


@dataclass
class DailySchedule:
    """A complete daily revision schedule for a student."""
    student_id: UUID
    schedule_date: datetime
    items: list[ScheduleItem]
    total_items: int
    total_ayahs: int
    estimated_minutes: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


class RevisionScheduler:
    """
    Generates personalized revision schedules using spaced repetition.

    Algorithm:
    1. Get all retention records for the student
    2. For each, predict current retention R(t)
    3. Score priority = weighted combination of:
       - How far below threshold R is
       - Difficulty of the ayah
       - How many days overdue the review is
    4. Sort by priority score (descending)
    5. Group consecutive ayahs into blocks
    6. Trim to fit time budget
    """

    def __init__(self) -> None:
        self.retention_model = RetentionModel()

    def generate_schedule(
        self,
        student_id: UUID,
        retention_records: list[dict],
        daily_budget_minutes: int = 30,
        schedule_date: datetime | None = None,
    ) -> DailySchedule:
        """
        Generate a daily revision schedule.

        Args:
            student_id: Student UUID
            retention_records: List of retention record dicts with fields:
                surah_number, ayah_number, stability, difficulty,
                last_reviewed_at, review_count
            daily_budget_minutes: Student's daily time budget
            schedule_date: Date to generate schedule for (default: today)

        Returns:
            DailySchedule with prioritized items.
        """
        if schedule_date is None:
            schedule_date = datetime.now(UTC)

        # 1. Predict retention for each record
        predictions: list[RetentionPrediction] = []
        for record in retention_records:
            prediction = self.retention_model.predict_retention(
                stability=record["stability"],
                difficulty=record["difficulty"],
                last_reviewed=record.get("last_reviewed_at"),
                surah=record["surah_number"],
                ayah=record["ayah_number"],
                now=schedule_date,
            )
            predictions.append(prediction)

        # 2. Filter and score
        scored_items: list[tuple[float, RetentionPrediction]] = []
        for pred in predictions:
            if pred.current_retention >= 0.98 and pred.urgency == "low":
                continue  # skip recently reviewed, high-retention ayahs

            score = self._calculate_priority_score(pred)
            scored_items.append((score, pred))

        # 3. Sort by priority score (highest first)
        scored_items.sort(key=lambda x: x[0], reverse=True)

        # 4. Build schedule items and group consecutive ayahs
        items: list[ScheduleItem] = []
        budget_seconds = daily_budget_minutes * 60
        used_seconds = 0

        for score, pred in scored_items:
            ayah_seconds = SECONDS_PER_AYAH_REVIEW
            if used_seconds + ayah_seconds > budget_seconds:
                # Still include critical items even if over budget
                if pred.urgency != "critical":
                    continue

            item = ScheduleItem(
                surah_number=pred.surah_number,
                ayah_start=pred.ayah_number,
                ayah_end=pred.ayah_number,
                predicted_retention=pred.current_retention,
                priority=pred.urgency,
                priority_score=score,
                reason=self._get_reason(pred),
                estimated_seconds=ayah_seconds,
                mastery_level=pred.mastery_level,
            )
            items.append(item)
            used_seconds += ayah_seconds

            if len(items) >= MAX_AYAHS_PER_SESSION:
                break

        # 5. Group consecutive ayahs in same surah
        grouped_items = self._group_consecutive(items)

        # 6. Build schedule
        schedule = DailySchedule(
            student_id=student_id,
            schedule_date=schedule_date,
            items=grouped_items,
            total_items=len(grouped_items),
            total_ayahs=sum(i.ayah_end - i.ayah_start + 1 for i in grouped_items),
            estimated_minutes=max(1, used_seconds // 60),
            critical_count=sum(1 for i in grouped_items if i.priority == "critical"),
            high_count=sum(1 for i in grouped_items if i.priority == "high"),
            medium_count=sum(1 for i in grouped_items if i.priority == "medium"),
            low_count=sum(1 for i in grouped_items if i.priority == "low"),
        )

        logger.info(
            "Schedule generated",
            student_id=str(student_id),
            total_items=schedule.total_items,
            total_ayahs=schedule.total_ayahs,
            estimated_minutes=schedule.estimated_minutes,
            critical=schedule.critical_count,
        )

        return schedule

    def _calculate_priority_score(self, pred: RetentionPrediction) -> float:
        """
        Calculate composite priority score for scheduling.
        Higher score = higher priority for review.
        """
        # Retention factor: how far below threshold
        if pred.current_retention < RETENTION_THRESHOLD:
            retention_score = (RETENTION_THRESHOLD - pred.current_retention) / RETENTION_THRESHOLD
        else:
            retention_score = 0.0

        # Difficulty factor
        difficulty_score = pred.difficulty

        # Overdue factor: days past the threshold crossing
        if pred.days_until_threshold <= 0:
            overdue_days = abs(pred.days_until_threshold)
            overdue_score = min(overdue_days / 7.0, 1.0)  # cap at 7 days
        else:
            overdue_score = 0.0

        return (
            PRIORITY_WEIGHT_RETENTION * retention_score
            + PRIORITY_WEIGHT_DIFFICULTY * difficulty_score
            + PRIORITY_WEIGHT_DAYS_OVERDUE * overdue_score
        )

    def _get_reason(self, pred: RetentionPrediction) -> str:
        """Human-readable reason for scheduling this ayah."""
        if pred.current_retention < ALWAYS_INCLUDE_THRESHOLD:
            return "retention_critically_low"
        elif pred.current_retention < RETENTION_THRESHOLD:
            return "retention_below_threshold"
        elif pred.days_until_threshold < 1:
            return "threshold_approaching"
        elif pred.mastery_level == "new":
            return "new_memorization"
        else:
            return "scheduled_review"

    def _group_consecutive(self, items: list[ScheduleItem]) -> list[ScheduleItem]:
        """Group consecutive ayahs from the same surah into ranges."""
        if not items:
            return []

        # Sort by surah then ayah
        items.sort(key=lambda x: (x.surah_number, x.ayah_start))

        grouped: list[ScheduleItem] = [items[0]]
        for item in items[1:]:
            prev = grouped[-1]
            if (
                item.surah_number == prev.surah_number
                and item.ayah_start == prev.ayah_end + 1
            ):
                # Extend the range
                prev.ayah_end = item.ayah_end
                prev.estimated_seconds += item.estimated_seconds
                prev.predicted_retention = min(
                    prev.predicted_retention, item.predicted_retention
                )
                # Take the highest priority
                if self._priority_rank(item.priority) > self._priority_rank(prev.priority):
                    prev.priority = item.priority
            else:
                grouped.append(item)

        return grouped

    def _priority_rank(self, priority: str) -> int:
        return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(priority, 0)

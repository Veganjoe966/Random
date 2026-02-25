"""
Retention scoring and prediction engine.
Implements the Ebbinghaus forgetting curve with adaptive stability.

Core formula:
    R(t) = e^(-t / S)

Where:
    R = recall probability (0.0 to 1.0)
    t = time since last review (in days)
    S = stability (memory strength in days; higher = slower forgetting)

Stability update after review:
    S_new = S * (1 + a * D^(-b) * (e^(c * (1-R)) - 1) * score_factor)

Where:
    D = difficulty (0.0-1.0)
    a, b, c = model parameters tuned for Qur'an memorization
    score_factor = adjustment based on recitation accuracy
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from structlog import get_logger

logger = get_logger()


# ── Model Parameters ─────────────────────────────────────────────────────
# Tuned for Qur'an memorization patterns (longer texts, repetitive review)

# Stability growth parameters
PARAM_A = 0.5    # Base growth rate
PARAM_B = 0.8    # Difficulty dampening
PARAM_C = 0.4    # Spacing bonus factor

# Retention threshold: below this, ayah needs urgent review
RETENTION_THRESHOLD = 0.85

# Minimum stability (prevents infinite review loops)
MIN_STABILITY = 0.5  # half a day minimum

# Maximum stability cap (even mastered ayahs decay eventually)
MAX_STABILITY = 365.0  # one year

# Initial stability for new memorization
INITIAL_STABILITY = 1.0  # one day

# Difficulty adjustment factors
DIFFICULTY_INCREASE_RATE = 0.05
DIFFICULTY_DECREASE_RATE = 0.03
MIN_DIFFICULTY = 0.1
MAX_DIFFICULTY = 0.9


@dataclass
class RetentionPrediction:
    """Predicted retention state for a single ayah."""
    surah_number: int
    ayah_number: int
    current_retention: float  # R right now
    stability: float  # S
    difficulty: float  # D
    days_since_review: float
    days_until_threshold: float  # days until R < RETENTION_THRESHOLD
    next_review_date: datetime
    mastery_level: str  # new, learning, reviewing, mastered
    urgency: str  # low, medium, high, critical


@dataclass
class StabilityUpdate:
    """Result of updating stability after a review."""
    old_stability: float
    new_stability: float
    old_difficulty: float
    new_difficulty: float
    retention_at_review: float
    new_mastery_level: str
    next_review_date: datetime


class RetentionModel:
    """
    Ebbinghaus-based retention model for spaced repetition of Qur'an ayahs.

    Usage:
        model = RetentionModel()

        # Predict current retention
        prediction = model.predict_retention(
            stability=3.5, difficulty=0.3,
            last_reviewed=datetime(2024, 1, 1),
            surah=2, ayah=255
        )

        # Update after a review
        update = model.update_after_review(
            stability=3.5, difficulty=0.3,
            last_reviewed=datetime(2024, 1, 1),
            accuracy_score=0.92, review_count=5
        )
    """

    def predict_retention(
        self,
        stability: float,
        difficulty: float,
        last_reviewed: datetime | None,
        surah: int = 0,
        ayah: int = 0,
        now: datetime | None = None,
    ) -> RetentionPrediction:
        """
        Predict current retention level for an ayah.

        Args:
            stability: Memory stability S (days)
            difficulty: Difficulty D (0-1)
            last_reviewed: When the ayah was last reviewed
            surah: Surah number (for output)
            ayah: Ayah number (for output)
            now: Current time (defaults to UTC now)

        Returns:
            RetentionPrediction with current R, time until threshold, etc.
        """
        if now is None:
            now = datetime.now(UTC)

        if last_reviewed is None:
            # Never reviewed — treat as new
            return RetentionPrediction(
                surah_number=surah,
                ayah_number=ayah,
                current_retention=0.0,
                stability=INITIAL_STABILITY,
                difficulty=difficulty,
                days_since_review=float("inf"),
                days_until_threshold=0.0,
                next_review_date=now,
                mastery_level="new",
                urgency="critical",
            )

        # Ensure timezone-aware comparison
        if last_reviewed.tzinfo is None:
            last_reviewed = last_reviewed.replace(tzinfo=UTC)

        days_since = (now - last_reviewed).total_seconds() / 86400.0
        current_r = self._calculate_retention(days_since, stability)
        days_until = self._days_until_threshold(stability, current_r)

        mastery = self._determine_mastery(stability, current_r)
        urgency = self._determine_urgency(current_r, days_until)
        next_review = now + timedelta(days=max(days_until, 0))

        return RetentionPrediction(
            surah_number=surah,
            ayah_number=ayah,
            current_retention=round(current_r, 4),
            stability=round(stability, 2),
            difficulty=round(difficulty, 3),
            days_since_review=round(days_since, 2),
            days_until_threshold=round(max(days_until, 0), 2),
            next_review_date=next_review,
            mastery_level=mastery,
            urgency=urgency,
        )

    def update_after_review(
        self,
        stability: float,
        difficulty: float,
        last_reviewed: datetime | None,
        accuracy_score: float,
        review_count: int,
        now: datetime | None = None,
    ) -> StabilityUpdate:
        """
        Update stability and difficulty after a review session.

        Args:
            stability: Current S
            difficulty: Current D
            last_reviewed: When previously reviewed
            accuracy_score: Score from alignment (0-1)
            review_count: Number of times reviewed so far
            now: Current time

        Returns:
            StabilityUpdate with new S, D, and next review date.
        """
        if now is None:
            now = datetime.now(UTC)

        old_stability = stability
        old_difficulty = difficulty

        # Calculate retention at time of review
        if last_reviewed:
            if last_reviewed.tzinfo is None:
                last_reviewed = last_reviewed.replace(tzinfo=UTC)
            days_since = (now - last_reviewed).total_seconds() / 86400.0
            retention_at_review = self._calculate_retention(days_since, stability)
        else:
            retention_at_review = 0.0
            days_since = 0.0

        # ── Update stability ─────────────────────────────────────────
        # Good score + long interval since review = big stability increase
        # Poor score = stability decrease
        score_factor = self._score_factor(accuracy_score)

        if accuracy_score >= 0.8:
            # Successful recall: increase stability
            spacing_bonus = math.exp(PARAM_C * (1 - retention_at_review)) - 1
            difficulty_factor = max(difficulty, 0.1) ** (-PARAM_B)
            growth = PARAM_A * difficulty_factor * spacing_bonus * score_factor
            new_stability = stability * (1 + growth)
        else:
            # Failed recall: decrease stability
            # Penalty is proportional to how badly they did
            penalty = 0.3 + 0.7 * accuracy_score  # range: 0.3 to 1.0
            new_stability = stability * penalty

        new_stability = max(MIN_STABILITY, min(MAX_STABILITY, new_stability))

        # ── Update difficulty ────────────────────────────────────────
        if accuracy_score >= 0.9:
            new_difficulty = difficulty - DIFFICULTY_DECREASE_RATE
        elif accuracy_score < 0.7:
            new_difficulty = difficulty + DIFFICULTY_INCREASE_RATE
        else:
            new_difficulty = difficulty

        new_difficulty = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, new_difficulty))

        # ── Calculate next review ────────────────────────────────────
        new_r = 1.0  # just reviewed, R = 1.0
        days_until = self._days_until_threshold(new_stability, new_r)
        next_review = now + timedelta(days=days_until)

        mastery = self._determine_mastery(new_stability, new_r)

        update = StabilityUpdate(
            old_stability=round(old_stability, 2),
            new_stability=round(new_stability, 2),
            old_difficulty=round(old_difficulty, 3),
            new_difficulty=round(new_difficulty, 3),
            retention_at_review=round(retention_at_review, 4),
            new_mastery_level=mastery,
            next_review_date=next_review,
        )

        logger.info(
            "Retention updated",
            stability=f"{old_stability:.2f} → {new_stability:.2f}",
            difficulty=f"{old_difficulty:.3f} → {new_difficulty:.3f}",
            accuracy=f"{accuracy_score:.2%}",
            next_review=next_review.isoformat(),
        )

        return update

    def _calculate_retention(self, days_elapsed: float, stability: float) -> float:
        """
        R(t) = e^(-t / S)

        Core Ebbinghaus formula.
        """
        if stability <= 0:
            return 0.0
        return math.exp(-days_elapsed / stability)

    def _days_until_threshold(
        self, stability: float, current_r: float
    ) -> float:
        """
        Calculate days until retention drops below threshold.

        Solving: RETENTION_THRESHOLD = e^(-t/S) for t
        t = -S * ln(RETENTION_THRESHOLD)

        But we need days FROM NOW, so subtract elapsed time.
        """
        if current_r <= RETENTION_THRESHOLD:
            return 0.0

        # Total days from last review until threshold
        total_days = -stability * math.log(RETENTION_THRESHOLD)

        # Days already elapsed = -S * ln(current_R)
        days_elapsed = -stability * math.log(max(current_r, 0.001))

        return max(total_days - days_elapsed, 0.0)

    def _score_factor(self, accuracy: float) -> float:
        """
        Convert accuracy score to stability growth factor.
        Maps [0, 1] to a growth multiplier.
        """
        if accuracy >= 0.95:
            return 1.5
        elif accuracy >= 0.9:
            return 1.2
        elif accuracy >= 0.8:
            return 1.0
        elif accuracy >= 0.7:
            return 0.6
        else:
            return 0.3

    def _determine_mastery(self, stability: float, retention: float) -> str:
        """Classify mastery level based on stability and retention."""
        if stability >= 90 and retention >= 0.8:
            return "mastered"
        elif stability >= 14:
            return "reviewing"
        elif stability >= 3:
            return "learning"
        else:
            return "new"

    def _determine_urgency(self, retention: float, days_until: float) -> str:
        """Classify review urgency."""
        if retention < 0.7:
            return "critical"
        elif retention < RETENTION_THRESHOLD:
            return "high"
        elif days_until < 1:
            return "medium"
        else:
            return "low"

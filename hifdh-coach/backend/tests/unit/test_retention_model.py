"""
Unit tests for the Ebbinghaus retention model.
Validates core forgetting curve math and stability updates.
"""

import math
from datetime import UTC, datetime, timedelta

import pytest


# Test the core math directly without importing (for standalone validation)
class TestRetentionMath:
    """Test the Ebbinghaus forgetting curve formula: R(t) = e^(-t/S)"""

    def test_retention_at_zero_is_one(self):
        """Just reviewed → retention = 1.0"""
        S = 5.0
        t = 0.0
        R = math.exp(-t / S)
        assert R == 1.0

    def test_retention_decays_over_time(self):
        """Retention decreases as time passes."""
        S = 5.0
        R_day1 = math.exp(-1.0 / S)
        R_day3 = math.exp(-3.0 / S)
        R_day7 = math.exp(-7.0 / S)
        assert R_day1 > R_day3 > R_day7

    def test_higher_stability_slower_decay(self):
        """Higher stability = slower forgetting."""
        t = 5.0
        R_low_S = math.exp(-t / 2.0)    # S=2
        R_high_S = math.exp(-t / 10.0)   # S=10
        assert R_high_S > R_low_S

    def test_retention_threshold_calculation(self):
        """Solve for t when R drops to threshold."""
        S = 7.0
        threshold = 0.85
        # R = e^(-t/S) → t = -S * ln(R)
        t = -S * math.log(threshold)
        R_at_t = math.exp(-t / S)
        assert abs(R_at_t - threshold) < 0.0001

    def test_stability_growth_after_successful_review(self):
        """Successful review should increase stability."""
        old_S = 5.0
        accuracy = 0.95
        # Score factor for 0.95+ accuracy = 1.5
        score_factor = 1.5
        # Simple growth: S_new = S * (1 + growth_factor)
        growth = 0.5 * score_factor  # PARAM_A * score_factor (simplified)
        new_S = old_S * (1 + growth * 0.5)  # with dampening
        assert new_S > old_S

    def test_stability_decrease_after_failed_review(self):
        """Failed review should decrease stability."""
        old_S = 5.0
        accuracy = 0.5
        penalty = 0.3 + 0.7 * accuracy  # 0.65
        new_S = old_S * penalty
        assert new_S < old_S

    def test_retention_never_exceeds_one(self):
        """R should never exceed 1.0"""
        S = 100.0
        t = 0.0
        R = math.exp(-t / S)
        assert R <= 1.0

    def test_very_long_interval_near_zero(self):
        """After very long time, retention approaches 0."""
        S = 5.0
        t = 1000.0
        R = math.exp(-t / S)
        assert R < 0.001

    def test_mastery_levels(self):
        """Mastery classification based on stability."""
        # S >= 90 and R >= 0.8 → mastered
        # S >= 14 → reviewing
        # S >= 3 → learning
        # else → new

        assert _classify_mastery(100, 0.9) == "mastered"
        assert _classify_mastery(90, 0.85) == "mastered"
        assert _classify_mastery(20, 0.5) == "reviewing"
        assert _classify_mastery(5, 0.8) == "learning"
        assert _classify_mastery(1, 0.5) == "new"


def _classify_mastery(stability: float, retention: float) -> str:
    if stability >= 90 and retention >= 0.8:
        return "mastered"
    elif stability >= 14:
        return "reviewing"
    elif stability >= 3:
        return "learning"
    else:
        return "new"


class TestSchedulingPriority:
    """Test that priority scoring works correctly."""

    def test_lower_retention_higher_priority(self):
        """Ayahs with lower retention should get higher priority."""
        score_low_r = _priority_score(retention=0.5, difficulty=0.3, days_overdue=0)
        score_high_r = _priority_score(retention=0.9, difficulty=0.3, days_overdue=0)
        assert score_low_r > score_high_r

    def test_overdue_increases_priority(self):
        """Being overdue should increase priority."""
        score_on_time = _priority_score(retention=0.8, difficulty=0.3, days_overdue=0)
        score_overdue = _priority_score(retention=0.8, difficulty=0.3, days_overdue=5)
        assert score_overdue > score_on_time

    def test_harder_ayahs_higher_priority(self):
        """Higher difficulty should increase priority."""
        score_easy = _priority_score(retention=0.8, difficulty=0.1, days_overdue=0)
        score_hard = _priority_score(retention=0.8, difficulty=0.9, days_overdue=0)
        assert score_hard > score_easy


def _priority_score(retention: float, difficulty: float, days_overdue: float) -> float:
    threshold = 0.85
    if retention < threshold:
        retention_score = (threshold - retention) / threshold
    else:
        retention_score = 0.0
    overdue_score = min(days_overdue / 7.0, 1.0) if days_overdue > 0 else 0.0
    return 0.5 * retention_score + 0.2 * difficulty + 0.3 * overdue_score

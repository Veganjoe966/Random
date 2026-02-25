"""
Tajweed timing analysis engine.
Measures acoustic durations for tajweed rules (madd, ghunnah, etc.)
and scores adherence based on expected durations.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from structlog import get_logger

from app.services.ai.alignment_engine import AlignedWord, AlignmentResult, WordStatus

logger = get_logger()


class TajweedRule(str, Enum):
    """Tajweed rules that can be detected via timing analysis."""
    MADD_TABII = "madd_tabii"           # Natural prolongation (2 counts)
    MADD_MUTTASIL = "madd_muttasil"     # Connected prolongation (4-5 counts)
    MADD_MUNFASIL = "madd_munfasil"     # Separated prolongation (4-5 counts)
    MADD_LAZIM = "madd_lazim"           # Obligatory prolongation (6 counts)
    MADD_ARID = "madd_arid"             # Presented prolongation (2-4-6 counts)
    GHUNNAH = "ghunnah"                 # Nasalization (2 counts)
    IDGHAM = "idgham"                   # Assimilation
    IKHFA = "ikhfa"                     # Concealment
    QALQALAH = "qalqalah"              # Echoing sound


# Duration expectations in seconds (approximate, based on moderate recitation speed)
# One "count" (haraka) ≈ 0.3-0.5 seconds at moderate pace
HARAKA_DURATION = 0.4  # seconds per count

RULE_DURATIONS: dict[TajweedRule, dict[str, float]] = {
    TajweedRule.MADD_TABII: {
        "min": HARAKA_DURATION * 1.5,
        "expected": HARAKA_DURATION * 2,
        "max": HARAKA_DURATION * 3,
    },
    TajweedRule.MADD_MUTTASIL: {
        "min": HARAKA_DURATION * 3.5,
        "expected": HARAKA_DURATION * 4.5,
        "max": HARAKA_DURATION * 6,
    },
    TajweedRule.MADD_MUNFASIL: {
        "min": HARAKA_DURATION * 3.5,
        "expected": HARAKA_DURATION * 4.5,
        "max": HARAKA_DURATION * 6,
    },
    TajweedRule.MADD_LAZIM: {
        "min": HARAKA_DURATION * 5,
        "expected": HARAKA_DURATION * 6,
        "max": HARAKA_DURATION * 7,
    },
    TajweedRule.MADD_ARID: {
        "min": HARAKA_DURATION * 1.5,
        "expected": HARAKA_DURATION * 4,
        "max": HARAKA_DURATION * 7,
    },
    TajweedRule.GHUNNAH: {
        "min": HARAKA_DURATION * 1.5,
        "expected": HARAKA_DURATION * 2,
        "max": HARAKA_DURATION * 3,
    },
}

# Arabic characters that indicate madd (prolongation) positions
MADD_LETTERS = {"ا", "و", "ي", "ى"}
HAMZA = "ء"
SUKUN = "\u0652"
SHADDA = "\u0651"

# Ghunnah-producing letters
GHUNNAH_LETTERS = {"ن", "م"}

# Qalqalah letters
QALQALAH_LETTERS = {"ق", "ط", "ب", "ج", "د"}


@dataclass
class TajweedDetection:
    """A detected tajweed rule with timing analysis."""
    rule: TajweedRule
    word_position: int
    word_text: str
    expected_duration: float
    actual_duration: float | None
    score: float  # 0.0 - 1.0
    within_tolerance: bool


@dataclass
class TajweedAnalysisResult:
    """Complete tajweed analysis for a recitation."""
    detections: list[TajweedDetection]
    overall_score: float
    total_rules_detected: int
    rules_within_tolerance: int
    rules_outside_tolerance: int
    per_rule_scores: dict[str, float] = field(default_factory=dict)


class TajweedAnalyzer:
    """
    Analyzes tajweed adherence by measuring acoustic durations.

    Approach:
    1. Scan reference words for known tajweed patterns (madd letters, ghunnah positions)
    2. Map patterns to expected acoustic durations
    3. Compare with actual durations from Whisper word timestamps
    4. Score each detection based on proximity to expected duration

    Limitations:
    - This is timing-based analysis only — not a full acoustic tajweed model
    - Best suited for madd duration detection where timing is the primary indicator
    - Teachers should verify and can override all tajweed scores
    """

    def analyze(self, alignment_result: AlignmentResult) -> TajweedAnalysisResult:
        """
        Perform tajweed timing analysis on aligned recitation.

        Args:
            alignment_result: Output from AlignmentEngine.align()

        Returns:
            TajweedAnalysisResult with per-word tajweed scoring.
        """
        detections: list[TajweedDetection] = []

        for ayah in alignment_result.ayahs:
            for word in ayah.words:
                if word.status != WordStatus.CORRECT:
                    continue  # only analyze correctly recited words
                if not word.duration or not word.reference_word:
                    continue

                # Detect tajweed rules in this word
                word_detections = self._detect_rules_in_word(word)
                detections.extend(word_detections)

        # Calculate scores
        total = len(detections)
        within_tolerance = sum(1 for d in detections if d.within_tolerance)
        outside_tolerance = total - within_tolerance

        # Per-rule aggregation
        per_rule: dict[str, list[float]] = {}
        for d in detections:
            per_rule.setdefault(d.rule.value, []).append(d.score)

        per_rule_scores = {
            rule: sum(scores) / len(scores)
            for rule, scores in per_rule.items()
        }

        overall = sum(d.score for d in detections) / max(total, 1)

        result = TajweedAnalysisResult(
            detections=detections,
            overall_score=overall,
            total_rules_detected=total,
            rules_within_tolerance=within_tolerance,
            rules_outside_tolerance=outside_tolerance,
            per_rule_scores=per_rule_scores,
        )

        logger.info(
            "Tajweed analysis complete",
            total_rules=total,
            overall_score=f"{overall:.2%}",
            within_tolerance=within_tolerance,
        )

        return result

    def _detect_rules_in_word(self, word: AlignedWord) -> list[TajweedDetection]:
        """Detect and score tajweed rules in a single word."""
        detections = []
        ref = word.reference_word

        # ── Madd detection ───────────────────────────────────────────
        madd_rule = self._detect_madd_type(ref)
        if madd_rule:
            expected = RULE_DURATIONS[madd_rule]["expected"]
            score = self._calculate_duration_score(
                word.duration, RULE_DURATIONS[madd_rule]
            )
            detections.append(TajweedDetection(
                rule=madd_rule,
                word_position=word.position,
                word_text=ref,
                expected_duration=expected,
                actual_duration=word.duration,
                score=score,
                within_tolerance=score >= 0.6,
            ))

        # ── Ghunnah detection ────────────────────────────────────────
        if self._has_ghunnah(ref):
            rule = TajweedRule.GHUNNAH
            expected = RULE_DURATIONS[rule]["expected"]
            score = self._calculate_duration_score(
                word.duration, RULE_DURATIONS[rule]
            )
            detections.append(TajweedDetection(
                rule=rule,
                word_position=word.position,
                word_text=ref,
                expected_duration=expected,
                actual_duration=word.duration,
                score=score,
                within_tolerance=score >= 0.6,
            ))

        return detections

    def _detect_madd_type(self, word: str) -> TajweedRule | None:
        """
        Detect the type of madd (prolongation) in a word based on letter patterns.
        Returns the most significant madd rule found, or None.
        """
        # Strip diacritics for pattern matching
        stripped = re.sub(r"[\u064B-\u065F\u0670]", "", word)

        # Madd lazim: madd letter followed by sukun on the same letter or shadda
        if any(
            stripped[i] in MADD_LETTERS
            and i + 1 < len(word)
            and (SUKUN in word[i:i+3] or SHADDA in word[i:i+3])
            for i in range(len(stripped) - 1)
        ):
            return TajweedRule.MADD_LAZIM

        # Madd muttasil: madd letter followed by hamza in same word
        if any(
            stripped[i] in MADD_LETTERS
            and HAMZA in stripped[i+1:]
            for i in range(len(stripped) - 1)
        ):
            return TajweedRule.MADD_MUTTASIL

        # Madd tabii: word ends with madd letter (natural prolongation)
        if stripped and stripped[-1] in MADD_LETTERS:
            return TajweedRule.MADD_TABII

        # Check for basic madd letter presence
        if any(c in MADD_LETTERS for c in stripped):
            return TajweedRule.MADD_TABII

        return None

    def _has_ghunnah(self, word: str) -> bool:
        """Check if word contains a ghunnah-producing letter with shadda."""
        stripped = re.sub(r"[\u064B-\u065F\u0670]", "", word)
        for i, char in enumerate(stripped):
            if char in GHUNNAH_LETTERS and SHADDA in word[max(0, i):i+3]:
                return True
        return False

    def _calculate_duration_score(
        self, actual: float | None, expected_range: dict[str, float]
    ) -> float:
        """
        Score duration adherence.
        Returns 1.0 if within expected range, decays linearly outside.
        """
        if actual is None:
            return 0.0

        min_d = expected_range["min"]
        expected = expected_range["expected"]
        max_d = expected_range["max"]

        if min_d <= actual <= max_d:
            # Within tolerance — score based on closeness to expected
            if actual <= expected:
                return 0.8 + 0.2 * (actual - min_d) / max(expected - min_d, 0.01)
            else:
                return 0.8 + 0.2 * (max_d - actual) / max(max_d - expected, 0.01)

        # Outside tolerance — linear decay
        if actual < min_d:
            return max(0.0, 0.8 * (actual / min_d))
        else:
            overshoot = actual - max_d
            return max(0.0, 0.8 - overshoot / max_d)

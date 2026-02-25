"""
Word-level alignment engine.
Aligns Whisper transcription output against the official Qur'an text
using forced alignment + Levenshtein distance for error detection.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

import Levenshtein
from structlog import get_logger

from app.services.ai.whisper_service import TranscriptionResult, WordTimestamp
from app.services.ai.quran_reference import QuranReference

logger = get_logger()


class WordStatus(str, Enum):
    CORRECT = "correct"
    SUBSTITUTED = "substituted"
    MISSING = "missing"
    ADDED = "added"


@dataclass
class AlignedWord:
    """Result of aligning a single word position."""
    position: int
    reference_word: str
    recited_word: str | None
    status: WordStatus
    similarity: float  # 0.0 - 1.0 (1.0 = exact match)
    start_time: float | None = None
    end_time: float | None = None
    duration: float | None = None


@dataclass
class AyahAlignment:
    """Alignment result for a single ayah."""
    surah_number: int
    ayah_number: int
    reference_text: str
    recited_text: str
    words: list[AlignedWord]
    accuracy_score: float
    word_error_rate: float
    total_words: int
    correct_words: int
    missing_words: int
    added_words: int
    substituted_words: int


@dataclass
class AlignmentResult:
    """Complete alignment result for an entire recitation."""
    ayahs: list[AyahAlignment]
    overall_accuracy: float
    overall_word_error_rate: float
    total_words: int
    total_correct: int
    total_errors: int
    error_details: list[dict] = field(default_factory=list)


class AlignmentEngine:
    """
    Aligns transcribed text against Qur'an reference using:
    1. Forced alignment with word-level timestamps from Whisper
    2. Levenshtein distance for fuzzy matching
    3. Dynamic programming for optimal word-to-word mapping

    The engine handles:
    - Missing words (student skipped)
    - Added words (student inserted extra)
    - Substituted words (student said wrong word)
    - Correct matches (exact or near-exact)
    """

    # Similarity threshold: below this = substitution error
    SIMILARITY_THRESHOLD = 0.75

    def __init__(self) -> None:
        self.quran_ref = QuranReference()

    def align(
        self,
        transcription: TranscriptionResult,
        surah_number: int,
        ayah_start: int,
        ayah_end: int,
    ) -> AlignmentResult:
        """
        Align transcription against reference Qur'an text for the given range.

        Args:
            transcription: Output from WhisperService.transcribe()
            surah_number: Surah number (1-114)
            ayah_start: Starting ayah number
            ayah_end: Ending ayah number (inclusive)

        Returns:
            AlignmentResult with per-word and per-ayah scoring.
        """
        recited_words = transcription.all_words
        ayah_results: list[AyahAlignment] = []

        # Track position in recited words across ayahs
        recited_idx = 0

        for ayah_num in range(ayah_start, ayah_end + 1):
            ref_text = self.quran_ref.get_ayah_text(surah_number, ayah_num)
            ref_words = self._normalize_and_tokenize(ref_text)

            # Estimate how many recited words correspond to this ayah
            # Use proportional allocation based on reference word count
            total_ref_words = sum(
                len(self._normalize_and_tokenize(
                    self.quran_ref.get_ayah_text(surah_number, a)
                ))
                for a in range(ayah_start, ayah_end + 1)
            )
            proportion = len(ref_words) / max(total_ref_words, 1)
            estimated_recited = int(len(recited_words) * proportion)

            # Get the slice of recited words for this ayah
            ayah_recited = recited_words[recited_idx:recited_idx + estimated_recited + 5]
            recited_idx += estimated_recited

            # Perform word-level alignment
            aligned_words = self._align_words(ref_words, ayah_recited)

            # Calculate scores
            total = len(ref_words)
            correct = sum(1 for w in aligned_words if w.status == WordStatus.CORRECT)
            missing = sum(1 for w in aligned_words if w.status == WordStatus.MISSING)
            added = sum(1 for w in aligned_words if w.status == WordStatus.ADDED)
            substituted = sum(1 for w in aligned_words if w.status == WordStatus.SUBSTITUTED)
            errors = missing + added + substituted

            accuracy = correct / max(total, 1)
            wer = errors / max(total, 1)

            recited_text = " ".join(
                w.recited_word for w in aligned_words
                if w.recited_word and w.status != WordStatus.MISSING
            )

            ayah_results.append(AyahAlignment(
                surah_number=surah_number,
                ayah_number=ayah_num,
                reference_text=ref_text,
                recited_text=recited_text,
                words=aligned_words,
                accuracy_score=accuracy,
                word_error_rate=wer,
                total_words=total,
                correct_words=correct,
                missing_words=missing,
                added_words=added,
                substituted_words=substituted,
            ))

        # Overall scores
        total_words = sum(a.total_words for a in ayah_results)
        total_correct = sum(a.correct_words for a in ayah_results)
        total_errors = sum(
            a.missing_words + a.added_words + a.substituted_words
            for a in ayah_results
        )

        result = AlignmentResult(
            ayahs=ayah_results,
            overall_accuracy=total_correct / max(total_words, 1),
            overall_word_error_rate=total_errors / max(total_words, 1),
            total_words=total_words,
            total_correct=total_correct,
            total_errors=total_errors,
            error_details=self._build_error_details(ayah_results),
        )

        logger.info(
            "Alignment complete",
            surah=surah_number,
            ayah_range=f"{ayah_start}-{ayah_end}",
            accuracy=f"{result.overall_accuracy:.2%}",
            wer=f"{result.overall_word_error_rate:.2%}",
        )

        return result

    def _align_words(
        self,
        reference: list[str],
        recited: list[WordTimestamp],
    ) -> list[AlignedWord]:
        """
        Align recited words against reference using dynamic programming (edit distance).
        Produces optimal mapping that minimizes total edit distance.
        """
        recited_texts = [self._normalize_word(w.word) for w in recited]
        ref_texts = [self._normalize_word(w) for w in reference]

        n = len(ref_texts)
        m = len(recited_texts)

        # Build cost matrix using Levenshtein similarity
        # dp[i][j] = min cost to align ref[0:i] with recited[0:j]
        INF = float("inf")
        dp = [[INF] * (m + 1) for _ in range(n + 1)]
        dp[0][0] = 0

        # Backtrack operations
        MATCH = 0
        DELETE = 1  # word in ref but not recited (missing)
        INSERT = 2  # word recited but not in ref (added)
        ops = [[None] * (m + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            dp[i][0] = i  # all missing
            ops[i][0] = DELETE

        for j in range(1, m + 1):
            dp[0][j] = j  # all added
            ops[0][j] = INSERT

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                similarity = self._word_similarity(ref_texts[i - 1], recited_texts[j - 1])
                # Match/substitute cost: 0 for perfect match, (1 - similarity) for substitution
                match_cost = dp[i - 1][j - 1] + (0 if similarity >= self.SIMILARITY_THRESHOLD else 1 - similarity)
                delete_cost = dp[i - 1][j] + 1  # missing word
                insert_cost = dp[i][j - 1] + 1  # added word

                if match_cost <= delete_cost and match_cost <= insert_cost:
                    dp[i][j] = match_cost
                    ops[i][j] = MATCH
                elif delete_cost <= insert_cost:
                    dp[i][j] = delete_cost
                    ops[i][j] = DELETE
                else:
                    dp[i][j] = insert_cost
                    ops[i][j] = INSERT

        # Backtrack to build alignment
        aligned: list[AlignedWord] = []
        i, j = n, m

        while i > 0 or j > 0:
            if i > 0 and j > 0 and ops[i][j] == MATCH:
                sim = self._word_similarity(ref_texts[i - 1], recited_texts[j - 1])
                status = WordStatus.CORRECT if sim >= self.SIMILARITY_THRESHOLD else WordStatus.SUBSTITUTED
                word_ts = recited[j - 1]
                aligned.append(AlignedWord(
                    position=i - 1,
                    reference_word=reference[i - 1],
                    recited_word=recited[j - 1].word,
                    status=status,
                    similarity=sim,
                    start_time=word_ts.start,
                    end_time=word_ts.end,
                    duration=word_ts.end - word_ts.start,
                ))
                i -= 1
                j -= 1
            elif i > 0 and (j == 0 or ops[i][j] == DELETE):
                aligned.append(AlignedWord(
                    position=i - 1,
                    reference_word=reference[i - 1],
                    recited_word=None,
                    status=WordStatus.MISSING,
                    similarity=0.0,
                ))
                i -= 1
            else:
                word_ts = recited[j - 1]
                aligned.append(AlignedWord(
                    position=-1,  # no reference position
                    reference_word="",
                    recited_word=recited[j - 1].word,
                    status=WordStatus.ADDED,
                    similarity=0.0,
                    start_time=word_ts.start,
                    end_time=word_ts.end,
                    duration=word_ts.end - word_ts.start,
                ))
                j -= 1

        aligned.reverse()
        return aligned

    def _word_similarity(self, ref: str, recited: str) -> float:
        """
        Calculate similarity between two Arabic words using normalized Levenshtein distance.
        Returns 0.0 (completely different) to 1.0 (identical).
        """
        if not ref or not recited:
            return 0.0
        if ref == recited:
            return 1.0
        distance = Levenshtein.distance(ref, recited)
        max_len = max(len(ref), len(recited))
        return 1.0 - (distance / max_len)

    def _normalize_word(self, word: str) -> str:
        """Normalize Arabic word for comparison (remove diacritics for base matching)."""
        # Remove common Arabic diacritics for comparison
        diacritics = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
        normalized = diacritics.sub("", word)
        return normalized.strip()

    def _normalize_and_tokenize(self, text: str) -> list[str]:
        """Split Arabic text into words."""
        return [w for w in text.split() if w.strip()]

    def _build_error_details(self, ayahs: list[AyahAlignment]) -> list[dict]:
        """Build structured error list for API response and teacher dashboard."""
        errors = []
        for ayah in ayahs:
            for word in ayah.words:
                if word.status != WordStatus.CORRECT:
                    errors.append({
                        "surah": ayah.surah_number,
                        "ayah": ayah.ayah_number,
                        "position": word.position,
                        "type": word.status.value,
                        "reference": word.reference_word,
                        "recited": word.recited_word,
                        "similarity": round(word.similarity, 3),
                        "time": word.start_time,
                    })
        return errors

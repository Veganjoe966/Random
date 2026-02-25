"""
Celery task for processing recitation audio.
Pipeline: Download → Whisper → Align → Tajweed → Score → Retention Update → Notify
"""

import tempfile
from datetime import UTC, datetime
from uuid import UUID

import boto3
from celery import shared_task
from sqlalchemy import select
from structlog import get_logger

from app.core.config import get_settings

logger = get_logger()
settings = get_settings()


@shared_task(
    bind=True,
    name="process_recitation",
    queue="gpu",  # Route to GPU-equipped workers
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=600,  # 10 minute hard limit
    soft_time_limit=540,  # 9 minute soft limit
)
def process_recitation_task(self, recitation_id: str, tenant_id: str) -> dict:
    """
    Full AI processing pipeline for a recitation.

    Steps:
    1. Download audio from S3
    2. Run Whisper transcription (word-level timestamps)
    3. Run forced alignment against reference Qur'an text
    4. Run tajweed timing analysis
    5. Calculate per-ayah scores
    6. Update retention records (spaced repetition)
    7. Update recitation status

    This task runs on GPU workers via Celery routing.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _process_recitation(self, recitation_id, tenant_id)
    )


async def _process_recitation(task, recitation_id: str, tenant_id: str) -> dict:
    """Async implementation of the processing pipeline."""
    from app.core.database import get_tenant_session
    from app.models.recitation import AyahScore, Recitation, WordAnalysis
    from app.models.retention import RetentionRecord
    from app.services.ai.alignment_engine import AlignmentEngine, WordStatus
    from app.services.ai.retention_model import RetentionModel
    from app.services.ai.tajweed_analyzer import TajweedAnalyzer
    from app.services.ai.whisper_service import WhisperService

    async with get_tenant_session(tenant_id) as db:
        try:
            # ── 1. Load recitation record ────────────────────────────
            result = await db.execute(
                select(Recitation).where(Recitation.id == UUID(recitation_id))
            )
            recitation = result.scalar_one_or_none()
            if not recitation:
                logger.error("Recitation not found", recitation_id=recitation_id)
                return {"error": "Recitation not found"}

            recitation.status = "processing"
            recitation.processing_started_at = datetime.now(UTC)
            await db.flush()

            # ── 2. Download audio from S3 ────────────────────────────
            logger.info("Downloading audio", key=recitation.audio_file_key)
            s3 = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
            )

            with tempfile.NamedTemporaryFile(
                suffix=f".{recitation.audio_format}", delete=True
            ) as tmp:
                s3.download_fileobj(
                    settings.s3_bucket_audio, recitation.audio_file_key, tmp
                )
                tmp.flush()

                # ── 3. Whisper transcription ─────────────────────────
                logger.info("Running Whisper transcription")
                whisper_svc = WhisperService()
                transcription = whisper_svc.transcribe(
                    tmp.name, language="ar"
                )

                recitation.audio_duration_seconds = transcription.duration
                recitation.whisper_output = {
                    "text": transcription.text,
                    "language": transcription.language,
                    "segments": [
                        {
                            "id": s.id,
                            "text": s.text,
                            "start": s.start,
                            "end": s.end,
                            "words": [
                                {
                                    "word": w.word,
                                    "start": w.start,
                                    "end": w.end,
                                    "probability": w.probability,
                                }
                                for w in s.words
                            ],
                        }
                        for s in transcription.segments
                    ],
                }

            # ── 4. Word alignment ────────────────────────────────────
            logger.info("Running word alignment")
            aligner = AlignmentEngine()
            alignment = aligner.align(
                transcription=transcription,
                surah_number=recitation.surah_number,
                ayah_start=recitation.ayah_start,
                ayah_end=recitation.ayah_end,
            )

            recitation.alignment_output = {
                "overall_accuracy": alignment.overall_accuracy,
                "overall_wer": alignment.overall_word_error_rate,
                "total_words": alignment.total_words,
                "total_correct": alignment.total_correct,
                "total_errors": alignment.total_errors,
                "error_details": alignment.error_details,
            }

            # ── 5. Tajweed analysis ──────────────────────────────────
            logger.info("Running tajweed analysis")
            tajweed = TajweedAnalyzer()
            tajweed_result = tajweed.analyze(alignment)

            recitation.tajweed_output = {
                "overall_score": tajweed_result.overall_score,
                "total_rules": tajweed_result.total_rules_detected,
                "within_tolerance": tajweed_result.rules_within_tolerance,
                "per_rule_scores": tajweed_result.per_rule_scores,
            }

            # ── 6. Store per-ayah scores ─────────────────────────────
            logger.info("Storing ayah scores")
            for ayah_alignment in alignment.ayahs:
                # Find tajweed score for this ayah
                ayah_tajweed_detections = [
                    d for d in tajweed_result.detections
                    if any(
                        w.position == d.word_position
                        for w in ayah_alignment.words
                        if w.status == WordStatus.CORRECT
                    )
                ]
                ayah_tajweed_score = (
                    sum(d.score for d in ayah_tajweed_detections) / len(ayah_tajweed_detections)
                    if ayah_tajweed_detections
                    else 1.0
                )

                combined = 0.7 * ayah_alignment.accuracy_score + 0.3 * ayah_tajweed_score

                ayah_score = AyahScore(
                    recitation_id=recitation.id,
                    student_id=recitation.student_id,
                    tenant_id=UUID(tenant_id),
                    surah_number=ayah_alignment.surah_number,
                    ayah_number=ayah_alignment.ayah_number,
                    accuracy_score=ayah_alignment.accuracy_score,
                    tajweed_score=ayah_tajweed_score,
                    combined_score=combined,
                    total_words=ayah_alignment.total_words,
                    correct_words=ayah_alignment.correct_words,
                    missing_words=ayah_alignment.missing_words,
                    added_words=ayah_alignment.added_words,
                    substituted_words=ayah_alignment.substituted_words,
                )
                db.add(ayah_score)

                # Store word-level analysis
                for word in ayah_alignment.words:
                    word_analysis = WordAnalysis(
                        recitation_id=recitation.id,
                        tenant_id=UUID(tenant_id),
                        surah_number=ayah_alignment.surah_number,
                        ayah_number=ayah_alignment.ayah_number,
                        word_position=word.position,
                        reference_word=word.reference_word,
                        recited_word=word.recited_word,
                        status=word.status.value,
                        start_time=word.start_time,
                        end_time=word.end_time,
                        duration=word.duration,
                    )
                    db.add(word_analysis)

            # ── 7. Update retention records ──────────────────────────
            logger.info("Updating retention records")
            retention_model = RetentionModel()

            for ayah_alignment in alignment.ayahs:
                # Get or create retention record
                ret_result = await db.execute(
                    select(RetentionRecord).where(
                        RetentionRecord.student_id == recitation.student_id,
                        RetentionRecord.surah_number == ayah_alignment.surah_number,
                        RetentionRecord.ayah_number == ayah_alignment.ayah_number,
                    )
                )
                retention_rec = ret_result.scalar_one_or_none()

                if retention_rec:
                    update = retention_model.update_after_review(
                        stability=retention_rec.stability,
                        difficulty=retention_rec.difficulty,
                        last_reviewed=retention_rec.last_reviewed_at,
                        accuracy_score=ayah_alignment.accuracy_score,
                        review_count=retention_rec.review_count,
                    )
                    retention_rec.stability = update.new_stability
                    retention_rec.difficulty = update.new_difficulty
                    retention_rec.last_retention = update.retention_at_review
                    retention_rec.current_retention = 1.0  # just reviewed
                    retention_rec.review_count += 1
                    retention_rec.last_reviewed_at = datetime.now(UTC)
                    retention_rec.next_review_at = update.next_review_date
                    retention_rec.last_score = ayah_alignment.accuracy_score
                    retention_rec.mastery_level = update.new_mastery_level
                    if ayah_alignment.accuracy_score >= 0.9:
                        retention_rec.consecutive_correct += 1
                    else:
                        retention_rec.consecutive_correct = 0
                else:
                    retention_rec = RetentionRecord(
                        tenant_id=UUID(tenant_id),
                        student_id=recitation.student_id,
                        surah_number=ayah_alignment.surah_number,
                        ayah_number=ayah_alignment.ayah_number,
                        stability=1.0,
                        difficulty=0.3,
                        last_retention=1.0,
                        current_retention=1.0,
                        review_count=1,
                        last_reviewed_at=datetime.now(UTC),
                        last_score=ayah_alignment.accuracy_score,
                        mastery_level="new",
                    )
                    # Compute next review
                    update = retention_model.update_after_review(
                        stability=1.0,
                        difficulty=0.3,
                        last_reviewed=None,
                        accuracy_score=ayah_alignment.accuracy_score,
                        review_count=0,
                    )
                    retention_rec.next_review_at = update.next_review_date
                    retention_rec.stability = update.new_stability
                    db.add(retention_rec)

            # ── 8. Update recitation aggregate scores ────────────────
            recitation.overall_accuracy_score = alignment.overall_accuracy
            recitation.overall_tajweed_score = tajweed_result.overall_score
            recitation.word_error_rate = alignment.overall_word_error_rate
            recitation.total_words = alignment.total_words
            recitation.correct_words = alignment.total_correct
            recitation.error_count = alignment.total_errors
            recitation.status = "completed"
            recitation.processing_completed_at = datetime.now(UTC)

            await db.flush()

            logger.info(
                "Recitation processing complete",
                recitation_id=recitation_id,
                accuracy=f"{alignment.overall_accuracy:.2%}",
                tajweed=f"{tajweed_result.overall_score:.2%}",
                wer=f"{alignment.overall_word_error_rate:.2%}",
            )

            return {
                "recitation_id": recitation_id,
                "status": "completed",
                "accuracy": alignment.overall_accuracy,
                "tajweed_score": tajweed_result.overall_score,
                "word_error_rate": alignment.overall_word_error_rate,
            }

        except Exception as exc:
            logger.error(
                "Recitation processing failed",
                recitation_id=recitation_id,
                error=str(exc),
            )
            recitation.status = "failed"
            recitation.error_message = str(exc)[:1000]
            await db.flush()

            # Retry with exponential backoff
            raise task.retry(exc=exc, countdown=60 * (2 ** task.request.retries))

"""
Whisper transcription service.
Handles audio loading, transcription via Whisper large-v3,
and extraction of word-level timestamps for alignment.
"""

import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
import whisper
from structlog import get_logger

from app.core.config import get_settings

logger = get_logger()
settings = get_settings()


@dataclass
class WordTimestamp:
    """A single word with its timing from Whisper output."""
    word: str
    start: float
    end: float
    probability: float


@dataclass
class TranscriptionSegment:
    """A segment of transcribed text with timing."""
    id: int
    text: str
    start: float
    end: float
    words: list[WordTimestamp] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    """Complete transcription output from Whisper."""
    text: str
    language: str
    segments: list[TranscriptionSegment]
    all_words: list[WordTimestamp]
    duration: float
    model_name: str


class WhisperService:
    """
    Singleton service wrapping OpenAI Whisper for Arabic Qur'an transcription.

    Usage:
        service = WhisperService()
        result = service.transcribe("/path/to/audio.wav")

    The model is loaded once and kept in memory for reuse.
    In production, this runs on a GPU-equipped node via Celery routing.
    """

    _instance: "WhisperService | None" = None
    _model: whisper.Whisper | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "WhisperService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def _load_model(self) -> whisper.Whisper:
        """Load Whisper model (lazy, thread-safe singleton)."""
        if self._model is None:
            with self._lock:
                # Double-check after acquiring lock
                if self._model is None:
                    logger.info(
                        "Loading Whisper model",
                        model=settings.whisper_model_size,
                        device=settings.whisper_device,
                    )
                    self._model = whisper.load_model(
                        settings.whisper_model_size,
                        device=settings.whisper_device,
                    )
                    logger.info("Whisper model loaded successfully")
        return self._model

    def transcribe(
        self,
        audio_path: str | Path,
        language: str = "ar",
    ) -> TranscriptionResult:
        """
        Transcribe an audio file using Whisper large-v3.

        Args:
            audio_path: Path to audio file (wav, mp3, webm, etc.)
            language: ISO 639-1 language code. Defaults to Arabic.

        Returns:
            TranscriptionResult with word-level timestamps.
        """
        model = self._load_model()
        audio_path = str(audio_path)

        logger.info("Starting transcription", audio_path=audio_path, language=language)

        # Transcribe with word-level timestamps enabled
        result = model.transcribe(
            audio_path,
            language=language,
            task="transcribe",
            word_timestamps=True,
            fp16=(settings.whisper_device == "cuda"),
            # Qur'an-specific: no hallucinated repetition
            condition_on_previous_text=False,
            # Beam search for accuracy
            beam_size=5,
            best_of=5,
            # Suppress non-speech tokens
            suppress_blank=True,
        )

        # Extract segments with word timestamps
        segments: list[TranscriptionSegment] = []
        all_words: list[WordTimestamp] = []

        for seg in result.get("segments", []):
            seg_words = []
            for w in seg.get("words", []):
                word_ts = WordTimestamp(
                    word=w["word"].strip(),
                    start=w["start"],
                    end=w["end"],
                    probability=w.get("probability", 0.0),
                )
                seg_words.append(word_ts)
                all_words.append(word_ts)

            segments.append(
                TranscriptionSegment(
                    id=seg["id"],
                    text=seg["text"].strip(),
                    start=seg["start"],
                    end=seg["end"],
                    words=seg_words,
                )
            )

        # Calculate total audio duration from the last segment's end time
        # (avoids loading the audio file a second time)
        if segments:
            duration = segments[-1].end
        elif result.get("segments"):
            duration = result["segments"][-1].get("end", 0.0)
        else:
            # Fallback: load audio to get duration
            audio = whisper.load_audio(audio_path)
            duration = len(audio) / whisper.audio.SAMPLE_RATE

        transcription = TranscriptionResult(
            text=result["text"].strip(),
            language=result.get("language", language),
            segments=segments,
            all_words=all_words,
            duration=duration,
            model_name=settings.whisper_model_size,
        )

        logger.info(
            "Transcription complete",
            total_words=len(all_words),
            total_segments=len(segments),
            duration=f"{duration:.1f}s",
        )

        return transcription

    def transcribe_from_bytes(
        self,
        audio_bytes: bytes,
        file_format: str = "webm",
        language: str = "ar",
    ) -> TranscriptionResult:
        """
        Transcribe from raw bytes (e.g., from S3 download).
        Writes to temp file, transcribes, cleans up.
        """
        with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            return self.transcribe(tmp.name, language=language)

    @staticmethod
    def get_device_info() -> dict:
        """Return GPU/device info for monitoring."""
        if torch.cuda.is_available():
            return {
                "device": "cuda",
                "gpu_name": torch.cuda.get_device_name(0),
                "gpu_memory_total": torch.cuda.get_device_properties(0).total_mem,
                "gpu_memory_allocated": torch.cuda.memory_allocated(0),
            }
        return {"device": "cpu"}

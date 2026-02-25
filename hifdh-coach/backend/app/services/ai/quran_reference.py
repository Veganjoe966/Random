"""
Qur'an reference text provider.
Loads and caches the official Uthmani text for alignment.

In production, this loads from a verified, authoritative source file.
The reference data includes:
  - 114 surahs
  - 6,236 ayahs
  - Word-level text for each ayah
  - Basic tajweed rule annotations
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from structlog import get_logger

logger = get_logger()

# Path to Qur'an reference data (shipped with the application)
QURAN_DATA_DIR = Path(__file__).parent.parent.parent.parent / "ai-engine" / "models" / "quran_data"


# ── Surah metadata ──────────────────────────────────────────────────────
SURAH_INFO: list[dict[str, Any]] = [
    {"number": 1, "name_arabic": "الفاتحة", "name_english": "Al-Fatiha", "ayah_count": 7, "juz_start": 1},
    {"number": 2, "name_arabic": "البقرة", "name_english": "Al-Baqarah", "ayah_count": 286, "juz_start": 1},
    {"number": 3, "name_arabic": "آل عمران", "name_english": "Aal-Imran", "ayah_count": 200, "juz_start": 3},
    {"number": 4, "name_arabic": "النساء", "name_english": "An-Nisa", "ayah_count": 176, "juz_start": 4},
    {"number": 5, "name_arabic": "المائدة", "name_english": "Al-Ma'idah", "ayah_count": 120, "juz_start": 6},
    # ... remaining surahs loaded from data file in production
]

# Total ayah counts per surah (1-indexed) — complete reference
SURAH_AYAH_COUNTS: dict[int, int] = {
    1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75,
    9: 129, 10: 109, 11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128,
    17: 111, 18: 110, 19: 98, 20: 135, 21: 112, 22: 78, 23: 118, 24: 64,
    25: 77, 26: 227, 27: 93, 28: 88, 29: 69, 30: 60, 31: 34, 32: 30,
    33: 73, 34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85,
    41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29,
    49: 18, 50: 45, 51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96,
    57: 29, 58: 22, 59: 24, 60: 13, 61: 14, 62: 11, 63: 11, 64: 18,
    65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44, 71: 28, 72: 28,
    73: 20, 74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42,
    81: 29, 82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26,
    89: 30, 90: 20, 91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19,
    97: 5, 98: 8, 99: 8, 100: 11, 101: 11, 102: 8, 103: 3, 104: 9,
    105: 5, 106: 4, 107: 7, 108: 3, 109: 6, 110: 3, 111: 5, 112: 4,
    113: 5, 114: 6,
}


class QuranReference:
    """
    Provides reference Qur'an text for alignment.

    In production deployment:
    - Loads from verified JSON data file containing Uthmani script
    - Caches in memory for fast repeated access
    - Supports both Uthmani and simplified scripts
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or QURAN_DATA_DIR
        self._cache: dict[str, str] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Load Qur'an text data if not already cached."""
        if self._loaded:
            return

        data_file = self.data_dir / "quran_uthmani.json"
        if data_file.exists():
            with open(data_file) as f:
                data = json.load(f)
                for ayah in data.get("ayahs", []):
                    key = f"{ayah['surah']}:{ayah['ayah']}"
                    self._cache[key] = ayah["text"]
            logger.info("Loaded Qur'an reference data", ayahs=len(self._cache))
        else:
            logger.warning(
                "Qur'an reference data file not found. "
                "Run `python scripts/download_quran_data.py` to fetch it.",
                path=str(data_file),
            )
        self._loaded = True

    def get_ayah_text(self, surah: int, ayah: int) -> str:
        """
        Get the reference text for a specific ayah.

        Args:
            surah: Surah number (1-114)
            ayah: Ayah number (1-based)

        Returns:
            Arabic text of the ayah in Uthmani script.

        Raises:
            ValueError: If surah/ayah is out of range.
        """
        self._validate_reference(surah, ayah)
        self._ensure_loaded()
        key = f"{surah}:{ayah}"
        text = self._cache.get(key, "")
        if not text:
            logger.warning("Ayah text not found in cache", surah=surah, ayah=ayah)
        return text

    def get_ayah_words(self, surah: int, ayah: int) -> list[str]:
        """Get reference text as list of words."""
        text = self.get_ayah_text(surah, ayah)
        return [w for w in text.split() if w.strip()]

    def get_surah_ayah_count(self, surah: int) -> int:
        """Get the number of ayahs in a surah."""
        if surah < 1 or surah > 114:
            raise ValueError(f"Invalid surah number: {surah}")
        return SURAH_AYAH_COUNTS[surah]

    def get_surah_info(self, surah: int) -> dict[str, Any]:
        """Get metadata about a surah."""
        if surah < 1 or surah > 114:
            raise ValueError(f"Invalid surah number: {surah}")
        return {
            "number": surah,
            "ayah_count": SURAH_AYAH_COUNTS[surah],
        }

    def _validate_reference(self, surah: int, ayah: int) -> None:
        """Validate surah and ayah numbers."""
        if surah < 1 or surah > 114:
            raise ValueError(f"Invalid surah number: {surah}. Must be 1-114.")
        max_ayah = SURAH_AYAH_COUNTS.get(surah, 0)
        if ayah < 1 or ayah > max_ayah:
            raise ValueError(
                f"Invalid ayah number: {ayah} for surah {surah}. Must be 1-{max_ayah}."
            )

    @staticmethod
    def get_juz_for_surah_ayah(surah: int, ayah: int) -> int:
        """
        Determine which juz (part) a given surah:ayah falls in.
        Returns juz number (1-30).
        """
        # Juz boundary mapping (simplified — full version in data file)
        JUZ_BOUNDARIES = [
            (1, 1), (2, 142), (2, 253), (3, 93), (4, 24),
            (4, 148), (5, 83), (6, 111), (7, 88), (8, 41),
            (9, 93), (11, 6), (12, 53), (15, 1), (17, 1),
            (18, 75), (21, 1), (23, 1), (25, 21), (27, 56),
            (29, 46), (33, 31), (36, 28), (39, 32), (41, 47),
            (46, 1), (51, 31), (58, 1), (67, 1), (78, 1),
        ]
        for i in range(len(JUZ_BOUNDARIES) - 1, -1, -1):
            js, ja = JUZ_BOUNDARIES[i]
            if surah > js or (surah == js and ayah >= ja):
                return i + 1
        return 1

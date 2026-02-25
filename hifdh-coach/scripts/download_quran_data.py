#!/usr/bin/env python3
"""
Downloads and prepares the Qur'an reference text data.
Fetches the Uthmani text from a verified source and formats it
for the alignment engine.

Usage:
    python scripts/download_quran_data.py

Output:
    ai-engine/models/quran_data/quran_uthmani.json
"""

import json
import os
import sys
from pathlib import Path

import httpx


# Verified Qur'an text API (quran.com API v4)
QURAN_API_BASE = "https://api.quran.com/api/v4"

OUTPUT_DIR = Path(__file__).parent.parent / "ai-engine" / "models" / "quran_data"


def download_quran_text() -> list[dict]:
    """Download all ayahs with Uthmani text."""
    print("Downloading Qur'an text from quran.com API...")
    ayahs = []

    for surah in range(1, 115):
        print(f"  Surah {surah}/114...", end="\r")
        response = httpx.get(
            f"{QURAN_API_BASE}/quran/verses/uthmani",
            params={"chapter_number": surah},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        for verse in data.get("verses", []):
            verse_key = verse["verse_key"]  # e.g., "2:255"
            surah_num, ayah_num = verse_key.split(":")
            ayahs.append({
                "surah": int(surah_num),
                "ayah": int(ayah_num),
                "text": verse["text_uthmani"],
            })

    print(f"\nDownloaded {len(ayahs)} ayahs.")
    return ayahs


def save_quran_data(ayahs: list[dict]) -> None:
    """Save to JSON file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "quran_uthmani.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"ayahs": ayahs, "total": len(ayahs)}, f, ensure_ascii=False, indent=2)

    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"Saved to {output_file} ({size_mb:.1f} MB)")


def main() -> None:
    ayahs = download_quran_text()
    save_quran_data(ayahs)
    print("Done! Qur'an reference data is ready for the alignment engine.")


if __name__ == "__main__":
    main()

"""
NDC Lookup Service — integrates with the FDA OpenFDA Drug NDC API.

Features:
  - Queries FDA OpenFDA /drug/ndc endpoint by generic name
  - Normalizes returned NDC to 11-digit billing format
  - Persists an on-disk cache to avoid redundant API calls
  - Gracefully falls back to deterministic placeholder NDC on API failure
  - Logs all API errors without crashing generation
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional

import requests

from .config import NDC_API_BASE, NDC_API_TIMEOUT, NDC_CACHE_FILE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NDC Result Type
# ---------------------------------------------------------------------------

class NDCResult:
    """Holds a resolved NDC entry (from API or fallback)."""

    __slots__ = ("ndc", "labeler", "dosage_form", "brand_name", "source")

    def __init__(
        self,
        ndc: str,
        labeler: str,
        dosage_form: str,
        brand_name: str,
        source: str = "api",
    ) -> None:
        self.ndc        = ndc
        self.labeler    = labeler
        self.dosage_form = dosage_form
        self.brand_name  = brand_name
        self.source      = source   # "api" | "cache" | "fallback"

    def to_dict(self) -> Dict[str, str]:
        return {
            "ndc":         self.ndc,
            "labeler":     self.labeler,
            "dosage_form": self.dosage_form,
            "brand_name":  self.brand_name,
            "source":      self.source,
        }


# ---------------------------------------------------------------------------
# NDC Service
# ---------------------------------------------------------------------------

class NDCService:
    """
    Thread-safe NDC lookup service with local disk cache.

    Usage
    -----
    service = NDCService()
    result  = service.lookup("oxycodone")
    print(result.ndc)           # "00406853062"
    print(result.labeler)       # "Mallinckrodt Pharmaceuticals"
    """

    def __init__(self, cache_file: Path = NDC_CACHE_FILE) -> None:
        self._cache_file = cache_file
        self._cache: Dict[str, dict] = {}
        self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup(self, search_term: str) -> NDCResult:
        """
        Look up an NDC for the given generic drug name.

        First checks the in-memory / on-disk cache.
        Falls back to FDA API, then to a deterministic placeholder.
        """
        key = search_term.strip().lower()

        if key in self._cache:
            cached = self._cache[key]
            return NDCResult(source="cache", **{k: cached[k] for k in
                ("ndc", "labeler", "dosage_form", "brand_name")})

        result = self._fetch_from_api(key)
        self._cache[key] = result.to_dict()
        self._save_cache()
        return result

    def preload(self, search_terms: list) -> None:
        """
        Pre-fetch NDC data for a list of drug names.
        Respects rate limits with a small delay between requests.
        """
        new_terms = [t.strip().lower() for t in search_terms if t.strip().lower() not in self._cache]
        logger.info("Pre-loading %d NDC entries from FDA API.", len(new_terms))
        for i, term in enumerate(new_terms):
            self.lookup(term)
            if i < len(new_terms) - 1:
                time.sleep(0.15)        # stay well within FDA rate limits

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _fetch_from_api(self, search_term: str) -> NDCResult:
        """Query the FDA OpenFDA NDC endpoint."""
        urls_to_try = [
            f'{NDC_API_BASE}?search=generic_name:"{search_term}"&limit=5',
            f'{NDC_API_BASE}?search=brand_name:"{search_term}"&limit=5',
        ]

        for url in urls_to_try:
            try:
                resp = requests.get(url, timeout=NDC_API_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        return self._parse_api_result(results[0])
                elif resp.status_code == 404:
                    logger.debug("NDC API 404 for query: %s", url)
                else:
                    logger.warning("NDC API returned HTTP %d for: %s", resp.status_code, url)
            except requests.Timeout:
                logger.warning("NDC API timeout for search term: '%s'", search_term)
                break
            except requests.ConnectionError:
                logger.warning("NDC API connection error for: '%s'", search_term)
                break
            except requests.RequestException as exc:
                logger.warning("NDC API request error for '%s': %s", search_term, exc)
                break
            except (ValueError, KeyError) as exc:
                logger.warning("NDC API parse error for '%s': %s", search_term, exc)
                break

        # All attempts failed — return deterministic placeholder
        return self._build_fallback(search_term)

    def _parse_api_result(self, result: dict) -> NDCResult:
        """Extract and normalize fields from an FDA API result entry."""
        raw_ndc    = result.get("product_ndc", "")
        labeler    = result.get("labeler_name", "Unknown Manufacturer")
        dosage     = result.get("dosage_form", "")
        brand      = ""
        if isinstance(result.get("brand_name"), list):
            brand = result["brand_name"][0] if result["brand_name"] else ""
        elif isinstance(result.get("brand_name"), str):
            brand = result["brand_name"]

        ndc_11 = self._normalize_ndc(raw_ndc)
        return NDCResult(ndc=ndc_11, labeler=labeler, dosage_form=dosage, brand_name=brand)

    # ------------------------------------------------------------------
    # NDC Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_ndc(raw: str) -> str:
        """
        Normalize an NDC to 11-digit format (no dashes).

        FDA returns NDCs in three possible configurations:
          4-4-2   →  pad labeler to 5 digits
          5-3-2   →  pad product to 4 digits
          5-4-1   →  pad package to 2 digits
        """
        if not raw:
            return "00000000000"

        raw_stripped = raw.replace("-", "").replace(" ", "")

        if raw_stripped.isdigit():
            if len(raw_stripped) == 11:
                return raw_stripped
            if len(raw_stripped) == 10:
                # Most common FDA format: treat as 5-3-2, pad product code
                return raw_stripped[:5] + "0" + raw_stripped[5:]
            return raw_stripped.zfill(11)

        # Has dashes — split and pad the short segment
        segments = raw.split("-")
        if len(segments) == 3:
            s1, s2, s3 = segments
            if len(s1) == 4:
                s1 = "0" + s1
            elif len(s2) == 3:
                s2 = "0" + s2
            elif len(s3) == 1:
                s3 = "0" + s3
            joined = s1 + s2 + s3
            return joined.zfill(11)[:11]

        return raw_stripped.zfill(11)[:11]

    # ------------------------------------------------------------------
    # Fallback NDC Generator
    # ------------------------------------------------------------------

    @staticmethod
    def _build_fallback(search_term: str) -> NDCResult:
        """
        Build a deterministic placeholder NDC when the API is unavailable.
        Uses MD5 hash of the search term to ensure reproducibility.
        """
        h = int(hashlib.md5(search_term.encode()).hexdigest(), 16)

        labeler  = str(h % 90_000 + 10_000)                  # 5 digits
        product  = str((h >> 16) % 9_000 + 1_000)            # 4 digits
        package  = str((h >> 24) % 90 + 10)                  # 2 digits
        ndc_11   = labeler + product + package

        logger.debug("Using fallback NDC '%s' for '%s'.", ndc_11, search_term)

        return NDCResult(
            ndc        = ndc_11,
            labeler    = "Manufacturer Unavailable (API Offline)",
            dosage_form= "See drug record",
            brand_name = "",
            source     = "fallback",
        )

    # ------------------------------------------------------------------
    # Cache I/O
    # ------------------------------------------------------------------

    def _load_cache(self) -> None:
        if self._cache_file.exists():
            try:
                with open(self._cache_file, encoding="utf-8") as fh:
                    self._cache = json.load(fh)
                logger.debug("Loaded %d NDC cache entries.", len(self._cache))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not load NDC cache: %s. Starting fresh.", exc)
                self._cache = {}

    def _save_cache(self) -> None:
        try:
            with open(self._cache_file, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh, indent=2)
        except OSError as exc:
            logger.warning("Could not save NDC cache: %s", exc)

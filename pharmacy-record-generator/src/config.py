"""
Configuration constants for the Pharmacy Record Generator.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Base Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / "cache"

# Ensure runtime directories exist
LOG_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Generation Defaults
# ---------------------------------------------------------------------------
DEFAULT_RECORD_COUNT = 2000
MIN_RECORD_COUNT = 100
MAX_RECORD_COUNT = 5000

# ---------------------------------------------------------------------------
# Controlled vs Non-Controlled Distribution
# ---------------------------------------------------------------------------
CONTROLLED_RATIO = 0.28        # 28% of fills are controlled substances
NON_CONTROLLED_RATIO = 0.72    # 72% of fills are non-controlled

# Within controlled substances
CII_RATIO = 0.38               # 38% of controlled are Schedule II
CIII_RATIO = 0.12              # 12% are Schedule III
CIV_RATIO = 0.42               # 42% are Schedule IV
CV_RATIO = 0.08                # 8%  are Schedule V

# ---------------------------------------------------------------------------
# Payment Distribution
# ---------------------------------------------------------------------------
CASH_RATIO_CONTROLLED = 0.24       # 24% cash for controlled
CASH_RATIO_NON_CONTROLLED = 0.13   # 13% cash for non-controlled

INSURANCE_PLANS = [
    "Medicare Part D",
    "Medicaid",
    "Blue Cross Blue Shield",
    "Aetna",
    "Cigna",
    "United Healthcare",
    "Humana",
    "CVS Caremark",
    "Express Scripts",
    "OptumRx",
    "Anthem",
    "Molina Healthcare",
    "WellCare",
    "Centene",
]

# ---------------------------------------------------------------------------
# FDA NDC API
# ---------------------------------------------------------------------------
NDC_API_BASE = "https://api.fda.gov/drug/ndc.json"
NDC_API_TIMEOUT = 10          # seconds
NDC_CACHE_FILE = CACHE_DIR / "ndc_cache.json"

# ---------------------------------------------------------------------------
# DEA Registrant Type Codes (first letter of DEA number)
# ---------------------------------------------------------------------------
DEA_VALID_FIRST_LETTERS = set("ABCDEFGMPRSTUX")

# ---------------------------------------------------------------------------
# Rx Numbering
# ---------------------------------------------------------------------------
RX_BASE_MIN = 1_000_000
RX_BASE_MAX = 4_999_999

# ---------------------------------------------------------------------------
# Schedule Labels
# ---------------------------------------------------------------------------
SCHEDULE_LABELS = {
    "CII":         "Schedule II",
    "CIII":        "Schedule III",
    "CIV":         "Schedule IV",
    "CV":          "Schedule V",
    "Non-Control": "Non-Controlled",
}

# ---------------------------------------------------------------------------
# Prescriber Specialty → Drug Schedule affinity (used for auto-assignment)
# ---------------------------------------------------------------------------
SPECIALTY_SCHEDULE_AFFINITY = {
    "Pain Management":    ["CII", "CIII", "CIV", "Non-Control"],
    "Oncology":           ["CII", "CIII", "Non-Control"],
    "Orthopedics":        ["CII", "CIV", "Non-Control"],
    "Psychiatry":         ["CII", "CIV", "CV", "Non-Control"],
    "Neurology":          ["CII", "CIV", "CV", "Non-Control"],
    "Primary Care":       ["CII", "CIII", "CIV", "CV", "Non-Control"],
    "Internal Medicine":  ["CIV", "CV", "Non-Control"],
    "Endocrinology":      ["CIII", "Non-Control"],
    "Cardiology":         ["Non-Control"],
    "Pulmonology":        ["Non-Control"],
    "Gastroenterology":   ["Non-Control"],
    "Nephrology":         ["Non-Control"],
    "Addiction Medicine": ["CIII", "CIV"],
    "Urology":            ["CIII", "Non-Control"],
    "Rheumatology":       ["CV", "Non-Control"],
    "Dermatology":        ["Non-Control"],
    "Palliative Care":    ["CII", "CIII", "CIV", "Non-Control"],
    "Dentistry":          ["CII", "CIII", "Non-Control"],
    "Emergency Medicine": ["CII", "CIII", "CIV", "Non-Control"],
    "Pediatrics":         ["CII", "Non-Control"],
}

# ---------------------------------------------------------------------------
# Logging Format
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE = LOG_DIR / "generator.log"

"""
DEA / Prescriber file parser.

Supports CSV and Excel (.xlsx / .xls) uploads.
Performs:
  - Dynamic column detection via fuzzy header matching
  - DEA format validation with checksum
  - Duplicate removal
  - ZIP code extraction
  - Specialty detection
  - Returns a validated prescriber pool + a validation report
"""

import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .validators import validate_dea, normalize_dea, generate_valid_dea, generate_valid_npi

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Column Synonym Maps (fuzzy matching)
# ---------------------------------------------------------------------------

_COL_SYNONYMS: Dict[str, List[str]] = {
    "prescriber_name": [
        "prescriber name", "provider name", "name", "prescriber",
        "physician name", "doctor name", "clinician name",
    ],
    "first_name": [
        "first name", "firstname", "first", "given name",
    ],
    "last_name": [
        "last name", "lastname", "last", "surname", "family name",
    ],
    "dea_number": [
        "dea number", "dea#", "dea no", "dea num", "dea",
        "dea registration", "dea reg",
    ],
    "npi": [
        "npi", "npi number", "npi#", "national provider identifier",
        "provider id", "provider identifier",
    ],
    "address": [
        "address", "street address", "address line 1", "addr",
        "office address", "practice address",
    ],
    "zip": [
        "zip", "zip code", "zipcode", "postal code", "zip/postal",
    ],
    "specialty": [
        "specialty", "speciality", "provider type", "practice type",
        "physician type", "discipline",
    ],
    "state": [
        "state", "st", "state code",
    ],
    "city": [
        "city", "town", "municipality",
    ],
}


def _match_column(df_cols: List[str], field: str) -> Optional[str]:
    """Return the first df column that matches any synonym for `field`."""
    synonyms = _COL_SYNONYMS.get(field, [])
    lower_cols = {c.strip().lower(): c for c in df_cols}
    for syn in synonyms:
        if syn.lower() in lower_cols:
            return lower_cols[syn.lower()]
    return None


# ---------------------------------------------------------------------------
# Simulated Prescriber Pool (used when no file is uploaded)
# ---------------------------------------------------------------------------

_SPECIALTIES = [
    "Pain Management", "Psychiatry", "Primary Care", "Neurology",
    "Orthopedics", "Cardiology", "Internal Medicine", "Oncology",
    "Addiction Medicine", "Endocrinology", "Pulmonology", "Palliative Care",
    "Urology", "Rheumatology", "Gastroenterology", "Dentistry",
    "Emergency Medicine", "Pediatrics",
]

_FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard",
    "Joseph", "Thomas", "Charles", "Christopher", "Daniel", "Matthew",
    "Anthony", "Andrew", "Joshua", "Kevin", "Steven", "Brian", "Edward",
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth",
    "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Margaret",
    "Betty", "Dorothy", "Sandra", "Ashley", "Emily", "Stephanie", "Rachel",
]

_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson",
    "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee",
    "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez",
    "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright",
    "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
]

_REGISTRANT_TYPES = list("ABMPS")   # Common for practitioners


def generate_prescriber_pool(
    count: int = 60,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Generate a realistic simulated prescriber pool.

    Parameters
    ----------
    count : int   — number of prescribers to generate
    seed  : int   — optional random seed for reproducibility
    """
    import random

    if seed is not None:
        random.seed(seed)

    prescribers = []
    used_deas = set()

    zip_pool = [
        "10001", "90210", "60601", "77001", "85001", "30301", "98101",
        "02101", "19101", "33101", "75201", "48201", "97201", "80201",
        "55401", "70112", "94102", "89101", "37201", "35203",
    ]

    for _ in range(count):
        first = random.choice(_FIRST_NAMES)
        last  = random.choice(_LAST_NAMES)
        spec  = random.choice(_SPECIALTIES)
        reg_type = random.choice(_REGISTRANT_TYPES)

        # Generate unique DEA
        for _ in range(20):
            dea = generate_valid_dea(reg_type, last[0])
            if dea not in used_deas:
                used_deas.add(dea)
                break

        npi = generate_valid_npi()
        zip_code = random.choice(zip_pool)
        city = "Anytown"
        state = "XX"

        prescribers.append({
            "prescriber_name": f"Dr. {first} {last}",
            "first_name":      first,
            "last_name":       last,
            "dea_number":      dea,
            "npi":             npi,
            "address":         f"{random.randint(100,9999)} Medical Drive",
            "city":            city,
            "state":           state,
            "zip":             zip_code,
            "specialty":       spec,
            "source":          "simulated",
        })

    logger.info("Generated %d simulated prescribers.", len(prescribers))
    return prescribers


# ---------------------------------------------------------------------------
# File Parser
# ---------------------------------------------------------------------------

class DEAParser:
    """Parse uploaded CSV or Excel prescriber/DEA files."""

    def __init__(self) -> None:
        self.prescribers: List[Dict[str, Any]] = []
        self.validation_report: List[Dict[str, Any]] = []
        self.parse_errors: List[str] = []

    # ------------------------------------------------------------------
    def parse(self, file_bytes: bytes, filename: str) -> bool:
        """
        Parse the uploaded file.

        Returns True on success (even if some rows are invalid).
        Returns False on catastrophic parse failure.
        """
        self.prescribers = []
        self.validation_report = []
        self.parse_errors = []

        try:
            df = self._load_file(file_bytes, filename)
        except Exception as exc:
            msg = f"Could not read file '{filename}': {exc}"
            self.parse_errors.append(msg)
            logger.error(msg)
            return False

        if df.empty:
            self.parse_errors.append("File is empty or has no parseable rows.")
            return False

        # Normalize column names
        df.columns = [str(c).strip() for c in df.columns]

        # Map standard field names to actual column names
        col_map = {field: _match_column(list(df.columns), field) for field in _COL_SYNONYMS}
        logger.debug("Column mapping: %s", col_map)

        prescribers_raw: List[Dict[str, Any]] = []
        seen_deas: set = set()

        for idx, row in df.iterrows():
            row_num = idx + 2   # 1-based, header is row 1

            record: Dict[str, Any] = {"source": "uploaded"}

            # ---- Prescriber name ----
            name_col = col_map.get("prescriber_name")
            fn_col   = col_map.get("first_name")
            ln_col   = col_map.get("last_name")

            if name_col and pd.notna(row.get(name_col)):
                record["prescriber_name"] = str(row[name_col]).strip()
            elif fn_col and ln_col and pd.notna(row.get(fn_col)) and pd.notna(row.get(ln_col)):
                fn = str(row[fn_col]).strip()
                ln = str(row[ln_col]).strip()
                record["prescriber_name"] = f"{fn} {ln}"
                record["first_name"] = fn
                record["last_name"]  = ln
            else:
                record["prescriber_name"] = f"Provider_{row_num}"

            # ---- DEA ----
            dea_raw = ""
            dea_col = col_map.get("dea_number")
            if dea_col and pd.notna(row.get(dea_col)):
                dea_raw = str(row[dea_col]).strip()

            dea_norm = normalize_dea(dea_raw)

            if dea_norm in seen_deas:
                self.validation_report.append({
                    "row":    row_num,
                    "name":   record["prescriber_name"],
                    "dea":    dea_norm,
                    "status": "DUPLICATE — skipped",
                })
                continue

            from .validators import validate_dea as _vdea
            ok, msg = _vdea(dea_norm) if dea_norm else (False, "Missing DEA")

            if not ok:
                self.validation_report.append({
                    "row":    row_num,
                    "name":   record["prescriber_name"],
                    "dea":    dea_raw,
                    "status": f"INVALID — {msg}",
                })
                # Still include the prescriber but flag them
                record["dea_number"] = dea_norm or "INVALID"
                record["dea_valid"]  = False
            else:
                record["dea_number"] = dea_norm
                record["dea_valid"]  = True
                seen_deas.add(dea_norm)

            # ---- NPI ----
            npi_col = col_map.get("npi")
            record["npi"] = (
                str(row[npi_col]).strip()
                if npi_col and pd.notna(row.get(npi_col))
                else generate_valid_npi()
            )

            # ---- Address fields ----
            for field in ("address", "city", "state", "zip"):
                col = col_map.get(field)
                record[field] = (
                    str(row[col]).strip()
                    if col and pd.notna(row.get(col))
                    else ""
                )

            # ---- Specialty ----
            spec_col = col_map.get("specialty")
            record["specialty"] = (
                str(row[spec_col]).strip()
                if spec_col and pd.notna(row.get(spec_col))
                else "Primary Care"
            )

            prescribers_raw.append(record)

        self.prescribers = prescribers_raw
        logger.info(
            "Parsed %d prescribers from '%s'. %d validation issues.",
            len(self.prescribers),
            filename,
            len(self.validation_report),
        )
        return True

    # ------------------------------------------------------------------
    def _load_file(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        """Load CSV or Excel file into a DataFrame."""
        lower = filename.lower()
        buf   = io.BytesIO(file_bytes)

        if lower.endswith(".csv"):
            # Try multiple encodings
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    buf.seek(0)
                    return pd.read_csv(buf, dtype=str, encoding=enc)
                except UnicodeDecodeError:
                    continue
            buf.seek(0)
            return pd.read_csv(buf, dtype=str, encoding="utf-8", errors="replace")

        elif lower.endswith((".xlsx", ".xls")):
            buf.seek(0)
            engine = "openpyxl" if lower.endswith(".xlsx") else "xlrd"
            return pd.read_excel(buf, dtype=str, engine=engine)

        else:
            raise ValueError(
                f"Unsupported file type: '{filename}'. "
                "Please upload a .csv, .xlsx, or .xls file."
            )

    # ------------------------------------------------------------------
    def get_zip_pool(self) -> List[str]:
        """Return unique non-empty ZIP codes extracted from parsed prescribers."""
        zips = [p["zip"] for p in self.prescribers if p.get("zip", "").strip()]
        return list(set(zips)) or ["00000"]

    # ------------------------------------------------------------------
    def get_validation_report_df(self) -> pd.DataFrame:
        """Return validation issues as a DataFrame."""
        if not self.validation_report:
            return pd.DataFrame(columns=["row", "name", "dea", "status"])
        return pd.DataFrame(self.validation_report)

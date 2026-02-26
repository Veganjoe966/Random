"""
DEA / Prescriber file parser.

Supports CSV, Excel (.xlsx / .xls), and JSON uploads.
Performs:
  - Dynamic column detection via fuzzy header matching
  - DEA format validation with checksum
  - Duplicate removal
  - ZIP code extraction
  - Specialty detection
  - Returns a validated prescriber pool + a validation report
"""

import io
import json
import logging
import re
from datetime import date
from typing import Any, Dict, IO, List, Optional, Tuple, Union

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
        "dea registration number", "dea reg number", "dea reg no",
    ],
    "npi": [
        "npi", "npi number", "npi#", "national provider identifier",
        "provider id", "provider identifier",
    ],
    "address": [
        "address", "street address", "address line 1", "address 1",
        "addr", "office address", "practice address",
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
    "expiration_date": [
        "expiration date", "expiration", "exp date", "exp", "expires",
        "expiry date", "expiry",
    ],
}


def _match_column(df_cols: List[str], field: str) -> Optional[str]:
    """Return the first df column that matches any synonym for `field`."""
    synonyms = _COL_SYNONYMS.get(field, [])
    # Normalize: lowercase and treat underscores as spaces so that
    # columns like DEA_Registration_Number match "dea registration number"
    lower_cols = {c.strip().lower().replace("_", " "): c for c in df_cols}
    for syn in synonyms:
        if syn.lower() in lower_cols:
            return lower_cols[syn.lower()]
    return None


def _is_pharmacy_name(name: str) -> bool:
    """Return True if the name belongs to a pharmacy / institution, not a practitioner."""
    lower = name.lower()
    return any(kw in lower for kw in _PHARMACY_KEYWORDS)


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

# Keywords that identify a pharmacy / institution rather than a practitioner.
# Checked case-insensitively against the full name string.
_PHARMACY_KEYWORDS = {
    "pharmacy", "phcy", "drug store", "drugstore", "apothecary",
    "compounding", "dispensary", "rx center", "drug co",
    "drugs", "chemist", "medicaid pharmacy", "mail order",
}

# One representative (city, zip) per state for auto-generated prescribers
_STATE_CITY_ZIP: Dict[str, tuple] = {
    "AL": ("Birmingham",      "35201"), "AK": ("Anchorage",      "99501"),
    "AZ": ("Phoenix",         "85001"), "AR": ("Little Rock",    "72201"),
    "CA": ("Los Angeles",     "90001"), "CO": ("Denver",         "80201"),
    "CT": ("Hartford",        "06101"), "DE": ("Wilmington",     "19801"),
    "FL": ("Miami",           "33101"), "GA": ("Atlanta",        "30301"),
    "HI": ("Honolulu",        "96801"), "ID": ("Boise",          "83701"),
    "IL": ("Chicago",         "60601"), "IN": ("Indianapolis",   "46201"),
    "IA": ("Des Moines",      "50301"), "KS": ("Wichita",        "67201"),
    "KY": ("Louisville",      "40201"), "LA": ("New Orleans",    "70112"),
    "ME": ("Portland",        "04101"), "MD": ("Baltimore",      "21201"),
    "MA": ("Boston",          "02101"), "MI": ("Detroit",        "48201"),
    "MN": ("Minneapolis",     "55401"), "MS": ("Jackson",        "39201"),
    "MO": ("Kansas City",     "64101"), "MT": ("Billings",       "59101"),
    "NE": ("Omaha",           "68101"), "NV": ("Las Vegas",      "89101"),
    "NH": ("Manchester",      "03101"), "NJ": ("Newark",         "07101"),
    "NM": ("Albuquerque",     "87101"), "NY": ("New York",       "10001"),
    "NC": ("Charlotte",       "28201"), "ND": ("Fargo",          "58101"),
    "OH": ("Columbus",        "43201"), "OK": ("Oklahoma City",  "73101"),
    "OR": ("Portland",        "97201"), "PA": ("Philadelphia",   "19101"),
    "RI": ("Providence",      "02901"), "SC": ("Columbia",       "29201"),
    "SD": ("Sioux Falls",     "57101"), "TN": ("Nashville",      "37201"),
    "TX": ("Houston",         "77001"), "UT": ("Salt Lake City", "84101"),
    "VT": ("Burlington",      "05401"), "VA": ("Richmond",       "23220"),
    "WA": ("Seattle",         "98101"), "WV": ("Charleston",     "25301"),
    "WI": ("Milwaukee",       "53201"), "WY": ("Cheyenne",       "82001"),
}


def generate_prescriber_pool(
    count: int = 60,
    seed: Optional[int] = None,
    target_state: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generate a realistic simulated prescriber pool.

    Parameters
    ----------
    count        : int — number of prescribers to generate
    seed         : int — optional random seed for reproducibility
    target_state : str — 2-letter state code; if set, all prescribers are
                         placed in that state
    """
    import random

    if seed is not None:
        random.seed(seed)

    prescribers = []
    used_deas = set()

    # Build city/zip pool for this call
    if target_state and target_state.upper() in _STATE_CITY_ZIP:
        st = target_state.upper()
        city_zip_pool = [(_STATE_CITY_ZIP[st][0], st, _STATE_CITY_ZIP[st][1])]
    else:
        city_zip_pool = [(city, st, zp) for st, (city, zp) in _STATE_CITY_ZIP.items()]

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
        city, state, zip_code = random.choice(city_zip_pool)

        prescribers.append({
            "prescriber_name": f"Dr. {first} {last}",
            "first_name":      first,
            "last_name":       last,
            "dea_number":      dea,
            "npi":             npi,
            "address":         f"{random.randint(100, 9999)} Medical Drive",
            "city":            city,
            "state":           state,
            "zip":             zip_code,
            "specialty":       spec,
            "source":          "simulated",
        })

    logger.info("Generated %d simulated prescribers (state=%s).", len(prescribers), target_state or "any")
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
    def parse(
        self,
        file_source: Union[bytes, bytearray, "IO[bytes]"],
        filename: str,
    ) -> bool:
        """
        Parse the uploaded file.

        file_source can be raw bytes **or** any seekable binary file-like
        object (e.g. Streamlit's UploadedFile).  Passing a file-like object
        avoids loading the entire file into memory before parsing.

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

            # ---- Filter out pharmacies / institutions ----
            if _is_pharmacy_name(record["prescriber_name"]):
                logger.debug("Row %d skipped — pharmacy/institution name: %s", row_num, record["prescriber_name"])
                continue

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

            ok, msg = validate_dea(dea_norm) if dea_norm else (False, "Missing DEA")

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

            # ---- Expiration date — auto-renew expired registrations ----
            exp_col = col_map.get("expiration_date")
            if exp_col and pd.notna(row.get(exp_col)):
                exp_raw = str(row[exp_col]).strip().replace("-", "").replace("/", "")
                exp_date = None
                # Try YYYYMMDD (e.g. 20240430) or MMDDYYYY
                for fmt_len, y_slice, m_slice, d_slice in [
                    (8, slice(0, 4), slice(4, 6), slice(6, 8)),    # YYYYMMDD
                    (8, slice(4, 8), slice(0, 2), slice(2, 4)),    # MMDDYYYY
                ]:
                    if len(exp_raw) == fmt_len:
                        try:
                            exp_date = date(
                                int(exp_raw[y_slice]),
                                int(exp_raw[m_slice]),
                                int(exp_raw[d_slice]),
                            )
                            break
                        except ValueError:
                            continue
                if exp_date:
                    today = date.today()
                    if exp_date < today:
                        exp_date = exp_date.replace(year=exp_date.year + 3)
                    record["expiration_date"] = exp_date.strftime("%m/%d/%Y")

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
    def _load_file(self, file_source, filename: str) -> pd.DataFrame:
        """
        Load CSV, Excel, or JSON into a DataFrame.

        file_source may be raw bytes/bytearray **or** any seekable binary
        file-like object (e.g. Streamlit's UploadedFile).  Accepting a
        file-like object avoids a full in-memory copy for large uploads.
        """
        lower = filename.lower()

        # Normalise: always work with a seekable binary stream.
        # If we already have bytes we wrap once; otherwise use the object
        # directly so we never make a second full copy.
        if isinstance(file_source, (bytes, bytearray)):
            buf: Any = io.BytesIO(file_source)
        else:
            buf = file_source

        if lower.endswith(".csv"):
            return self._load_csv(buf)
        elif lower.endswith((".xlsx", ".xls")):
            return self._load_excel(buf, lower)
        elif lower.endswith(".json"):
            return self._load_json(buf)
        else:
            raise ValueError(
                f"Unsupported file type: '{filename}'. "
                "Please upload a .csv, .xlsx, .xls, or .json file."
            )

    # ------------------------------------------------------------------
    _CSV_CHUNK = 50_000   # rows per chunk for large CSVs

    def _load_csv(self, buf) -> pd.DataFrame:
        """
        Read CSV with encoding auto-detection and chunked I/O.

        Using chunksize means pandas never holds more than _CSV_CHUNK rows
        decoded at once; the concat only stores the final result.
        """
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                buf.seek(0)
                chunks = pd.read_csv(
                    buf, dtype=str, encoding=enc,
                    chunksize=self._CSV_CHUNK, low_memory=False,
                )
                return pd.concat(chunks, ignore_index=True)
            except UnicodeDecodeError:
                continue
        # Last-resort: replace undecodable bytes rather than crash
        buf.seek(0)
        chunks = pd.read_csv(
            buf, dtype=str, encoding="utf-8", errors="replace",
            chunksize=self._CSV_CHUNK, low_memory=False,
        )
        return pd.concat(chunks, ignore_index=True)

    # ------------------------------------------------------------------
    def _load_excel(self, buf, lower: str) -> pd.DataFrame:
        """
        Read Excel files.

        .xls  — legacy format; uses xlrd (no streaming available).
        .xlsx — uses openpyxl in read-only / streaming mode so the entire
                workbook is never decompressed into RAM at once.  Peak
                memory is proportional to one row rather than the whole file.
        """
        buf.seek(0)
        if lower.endswith(".xls"):
            return pd.read_excel(buf, dtype=str, engine="xlrd")

        # XLSX — openpyxl read_only streams rows directly from the zip
        try:
            from openpyxl import load_workbook as _lw
        except ImportError:
            buf.seek(0)
            return pd.read_excel(buf, dtype=str, engine="openpyxl")

        buf.seek(0)
        wb = _lw(buf, read_only=True, data_only=True)
        ws = wb.active

        rows_iter = ws.iter_rows(values_only=True)
        try:
            raw_headers = next(rows_iter)
        except StopIteration:
            wb.close()
            return pd.DataFrame()

        headers = [
            str(h).strip() if h is not None else f"_col{i}"
            for i, h in enumerate(raw_headers)
        ]

        data = [
            [("" if v is None else str(v)) for v in row]
            for row in rows_iter
        ]
        wb.close()
        return pd.DataFrame(data, columns=headers, dtype=str)

    # ------------------------------------------------------------------
    def _load_json(self, buf) -> pd.DataFrame:
        """
        Read JSON or NDJSON from a binary stream.

        Standard JSON  — decoded in one pass (unavoidable for random-access
                         formats), then normalised to a list of objects.
        NDJSON         — decoded line-by-line; only one parsed object lives
                         in memory at a time before being appended.
        """
        # Decode bytes from the stream
        raw = buf.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        del raw   # release the raw bytes as soon as possible

        # Try standard JSON (array or object-wrapping-array)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fall back to NDJSON (one JSON object per line)
            rows: List[Dict] = []
            for line_num, line in enumerate(text.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append(obj)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON on line {line_num}: {exc}"
                    ) from exc
            if not rows:
                raise ValueError("JSON file is empty or contains no valid objects.")
            return pd.DataFrame(rows, dtype=str)

        # Normalise standard JSON to a list of dicts
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = next(
                (v for v in data.values() if isinstance(v, list)),
                None,
            )
            if rows is None:
                raise ValueError(
                    "JSON object must contain a key whose value is an array "
                    "of prescriber objects."
                )
        else:
            raise ValueError(
                "JSON must be an array of prescriber objects or an object "
                "containing one."
            )

        if not rows:
            raise ValueError("JSON prescriber list is empty.")

        return pd.DataFrame(rows, dtype=str)

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
